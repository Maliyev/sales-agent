from pathlib import Path
import os
import tempfile
from threading import Lock


PROJECT_PATH = Path(__file__).resolve().parents[1]
PROMPT_FILES = (
    "prompts/01_role.md",
    "prompts/02_response_rules.md",
    "prompts/03_security_rules.md",
    "prompts/04_product_tools.md",
    "prompts/05_operator.md",
    "knowledge/store.md",
)
FINAL_PROMPT_FILES = tuple(
    path for path in PROMPT_FILES if path != "prompts/04_product_tools.md"
)
COMPACTION_PROMPT_FILE = "prompts/06_compaction.md"
LIST_ADDENDUM_FILES = {
    "decision": "prompts/product_list_decision.md",
    "selection": "prompts/product_list_selection.md",
    "item_response": "prompts/product_list_item_response.md",
    "report": "prompts/product_list_report.md",
}

EDITABLE_PROMPTS = (
    ("role", "Роль агента", "prompts/01_role.md"),
    ("response_rules", "Правила ответа", "prompts/02_response_rules.md"),
    ("security_rules", "Правила безопасности", "prompts/03_security_rules.md"),
    ("product_tools", "Инструменты и поиск товаров", "prompts/04_product_tools.md"),
    ("operator", "Передача оператору", "prompts/05_operator.md"),
    ("compaction", "Сжатие истории", COMPACTION_PROMPT_FILE),
    ("image_describer", "Описание изображений", "prompts/07_image_describer.md"),
    ("admin_report", "Отчёт dashboard", "prompts/admin_report.md"),
    ("list_decision", "Список · выбор поиска", LIST_ADDENDUM_FILES["decision"]),
    ("list_selection", "Список · выбор товаров", LIST_ADDENDUM_FILES["selection"]),
    ("list_item_response", "Список · ответ по товару", LIST_ADDENDUM_FILES["item_response"]),
    ("list_report", "Список · итоговый отчёт", LIST_ADDENDUM_FILES["report"]),
    ("product_response", "Ответ по товарам", "prompts/product_response.md"),
    ("product_selection", "Поиск товаров", "prompts/product_selection.md"),
    ("store", "Каталог и правила магазина", "knowledge/store.md"),
)
MAX_EDITABLE_PROMPT_CHARACTERS = 150_000
_prompt_write_lock = Lock()


class PromptError(RuntimeError):
    pass


class PromptValidationError(PromptError):
    pass


class PromptNotFoundError(PromptError):
    pass


def load_system_instruction(project_path=PROJECT_PATH):
    return "\n\n".join(
        load_prompt_file(relative_path, project_path)
        for relative_path in PROMPT_FILES
    )


def load_agent_instructions(project_path=PROJECT_PATH):
    return (
        load_system_instruction(project_path),
        load_prompt_file("prompts/product_selection.md", project_path),
        load_prompt_file("prompts/product_response.md", project_path),
    )


def load_final_system_instruction(project_path=PROJECT_PATH):
    return "\n\n".join(
        load_prompt_file(relative_path, project_path)
        for relative_path in FINAL_PROMPT_FILES
    )


def load_compaction_instruction(project_path=PROJECT_PATH):
    return load_prompt_file(COMPACTION_PROMPT_FILE, project_path)


def load_list_mode_addenda(project_path=PROJECT_PATH):
    return {
        stage: load_prompt_file(relative_path, project_path)
        for stage, relative_path in LIST_ADDENDUM_FILES.items()
    }


def load_prompt_file(relative_path, project_path=PROJECT_PATH):
    path = _prompt_file_path(relative_path, project_path)

    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"Could not read prompt file: {path}") from error

    if not text:
        raise RuntimeError(f"Prompt file is empty: {path}")

    return text


def list_editable_prompts():
    return [
        {"id": prompt_id, "title": title, "path": path}
        for prompt_id, title, path in EDITABLE_PROMPTS
    ]


def read_editable_prompt(prompt_id, project_path=PROJECT_PATH):
    metadata = _editable_prompt(prompt_id)
    path = _prompt_file_path(metadata["path"], project_path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PromptError(f"Не удалось прочитать файл {metadata['path']}.") from error
    if not content.strip():
        raise PromptError(f"Файл {metadata['path']} пуст.")
    return {**metadata, "content": content}


def save_editable_prompt(prompt_id, content, project_path=PROJECT_PATH):
    metadata = _editable_prompt(prompt_id)
    if not isinstance(content, str) or not content.strip():
        raise PromptValidationError("Текст промпта не может быть пустым.")
    if len(content) > MAX_EDITABLE_PROMPT_CHARACTERS:
        raise PromptValidationError(
            f"Промпт не должен превышать {MAX_EDITABLE_PROMPT_CHARACTERS:,} символов."
        )
    if "\x00" in content:
        raise PromptValidationError("Промпт содержит недопустимый нулевой символ.")

    path = _prompt_file_path(metadata["path"], project_path, for_write=True)
    temporary = None
    with _prompt_write_lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                prefix=f".{path.name}-", suffix=".tmp", delete=False,
            ) as file:
                temporary = Path(file.name)
                file.write(content.replace("\r\n", "\n").replace("\r", "\n"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        except OSError as error:
            raise PromptError(f"Не удалось сохранить файл {metadata['path']}.") from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    return read_editable_prompt(prompt_id, project_path)


def _editable_prompt(prompt_id):
    for item_id, title, path in EDITABLE_PROMPTS:
        if item_id == prompt_id:
            return {"id": item_id, "title": title, "path": path}
    raise PromptNotFoundError("Промпт не найден.")


def _prompt_file_path(relative_path, project_path, for_write=False):
    project_path = Path(project_path)
    volume_path = os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    if project_path == PROJECT_PATH and volume_path:
        persistent_path = Path(volume_path) / "prompt-overrides" / relative_path
        if for_write or persistent_path.is_file():
            return persistent_path
    return project_path / relative_path
