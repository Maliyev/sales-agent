import base64
import os
import time

from app_logging import get_logger
from database import DatabaseError, record_api_call
from gemini import generate_content, get_text_response, get_usage_metadata
from prompts import load_prompt_file


MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
IMAGE_DESCRIPTION_PROMPT = "prompts/07_image_describer.md"

logger = get_logger("image")


class ImageReadError(RuntimeError):
    pass


def is_image_file(filename):
    if not isinstance(filename, str):
        return False
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def is_image(mime_type=None, filename=None):
    if isinstance(mime_type, str) and mime_type.strip().lower().startswith("image/"):
        return True
    return is_image_file(filename)


def resolve_mime_type(filename, mime_type=None):
    if isinstance(mime_type, str) and mime_type.strip():
        return mime_type.strip().lower()
    if isinstance(filename, str):
        return IMAGE_MIME_TYPES.get(os.path.splitext(filename)[1].lower(), "")
    return ""


def build_image_user_text(description, caption=None):
    parts = [
        "The customer sent an image. The system sent the image to a vision "
        "model, which returned the description below. The description may "
        "contain inaccuracies.",
        "--- Image description ---",
        description,
        "--- End of image description ---",
    ]
    if isinstance(caption, str) and caption.strip():
        parts.append(f"Customer's message with the image: {caption.strip()}")
    return "\n".join(parts)


def describe_image(
    image_bytes,
    mime_type,
    model,
    api_key,
    database_path,
    session_id,
    instruction=None,
    generate_fn=generate_content,
    usage_fn=None,
):
    if not isinstance(image_bytes, (bytes, bytearray)) or not image_bytes:
        raise ImageReadError("The image is empty.")
    if not isinstance(mime_type, str) or not mime_type.strip():
        raise ImageReadError("The image MIME type is missing.")

    if instruction is None:
        instruction = load_prompt_file(IMAGE_DESCRIPTION_PROMPT)

    encoded = base64.b64encode(bytes(image_bytes)).decode("ascii")
    contents = [
        {
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": mime_type, "data": encoded}},
                {"text": "Describe the attached image."},
            ],
        }
    ]

    started_at = time.monotonic()
    try:
        data = generate_fn(contents, model, api_key, instruction)
        description = get_text_response(data).strip()
        if not description:
            raise RuntimeError("The vision model returned an empty description.")
    except Exception as error:
        _record_call(
            database_path,
            session_id,
            model,
            started_at,
            "failed",
            _describe_error(error),
        )
        raise ImageReadError(
            f"Image description failed: {_describe_error(error)}"
        ) from error

    usage = _read_usage(usage_fn, data)
    _record_call(
        database_path,
        session_id,
        model,
        started_at,
        "ok",
        None,
        prompt_tokens=usage["prompt_tokens"],
        completion_tokens=usage["completion_tokens"],
    )
    return description


def _record_call(
    database_path,
    session_id,
    model,
    started_at,
    status,
    error,
    prompt_tokens=0,
    completion_tokens=0,
):
    try:
        record_api_call(
            database_path,
            session_id,
            None,
            "vision",
            model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=round((time.monotonic() - started_at) * 1000),
            status=status,
            error=error,
        )
    except DatabaseError as record_error:
        logger.warning(
            "⚠️ Could not record the vision call | session=%s error=%s",
            session_id,
            record_error,
        )


def _read_usage(usage_fn, data):
    if usage_fn is None:
        usage_fn = get_usage_metadata
    try:
        usage = usage_fn(data)
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0}

    return {
        "prompt_tokens": _safe_int(usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(usage.get("completion_tokens")),
    }


def _safe_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _describe_error(error):
    return f"{type(error).__name__}: {error}"[:300]
