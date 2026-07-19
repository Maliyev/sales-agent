from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parents[1]
PROMPT_FILES = (
    "prompts/01_role.md",
    "prompts/02_response_rules.md",
    "prompts/03_security_rules.md",
    "prompts/04_product_tools.md",
    "knowledge/store.md",
)


def load_system_instruction(project_path=PROJECT_PATH):
    return "\n\n".join(
        load_prompt_file(relative_path, project_path)
        for relative_path in PROMPT_FILES
    )


def load_prompt_file(relative_path, project_path=PROJECT_PATH):
    path = Path(project_path) / relative_path

    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError(f"Could not read prompt file: {path}") from error

    if not text:
        raise RuntimeError(f"Prompt file is empty: {path}")

    return text
