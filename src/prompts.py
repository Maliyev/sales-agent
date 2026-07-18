from pathlib import Path


PROJECT_PATH = Path(__file__).resolve().parents[1]
PROMPT_FILES = (
    "prompts/01_role.md",
    "prompts/02_response_rules.md",
    "prompts/03_security_rules.md",
    "knowledge/store.md",
)


def load_system_instruction(project_path=PROJECT_PATH):
    blocks = []

    for relative_path in PROMPT_FILES:
        path = Path(project_path) / relative_path

        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise RuntimeError(f"Could not read prompt file: {path}") from error

        if not text:
            raise RuntimeError(f"Prompt file is empty: {path}")

        blocks.append(text)

    return "\n\n".join(blocks)
