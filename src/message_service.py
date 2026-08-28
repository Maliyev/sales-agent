from agent import get_agent_reply
from agent_reply import AgentReply
from app_config import get_context_overflow_auto_reset
from app_logging import flatten_text, get_logger, log_conversation
from database import (
    insert_incoming_message,
    load_history,
    reset_history,
    save_model_message,
    update_messages_status,
)
from token_limiter import SessionContextTooLargeError


logger = get_logger("messages")

CONTEXT_RESET_NOTICE = (
    "Your conversation became too long, so we had to reset it."
)


def reply_to_customer(
    database_path,
    session_id,
    user_text,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
):
    message_id = insert_incoming_message(database_path, session_id, user_text)
    try:
        reply = generate_customer_reply(
            database_path,
            session_id,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
            in_reply_to_message_id=message_id,
        )
    except Exception:
        update_messages_status(database_path, [message_id], "FAILED_LLM_API")
        raise
    model_message_id = save_model_message(
        database_path,
        session_id,
        reply.customer_reply,
        status="RESPONSE_READY",
    )
    return reply, [message_id, model_message_id]


def generate_customer_reply(
    database_path,
    session_id,
    user_text,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
    in_reply_to_message_id=None,
):
    history = load_history(database_path, session_id)
    log_conversation(session_id, "USER", flatten_text(user_text))
    try:
        return get_agent_reply(
            history,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
            session_id=session_id,
            database_path=database_path,
            in_reply_to_message_id=in_reply_to_message_id,
        )
    except SessionContextTooLargeError:
        if not get_context_overflow_auto_reset():
            raise
        _reset_oversized_context(database_path, session_id)
        history = load_history(database_path, session_id)
        reply = get_agent_reply(
            history,
            user_text,
            model,
            api_key,
            system_instruction,
            selection_instruction,
            response_instruction,
            session_id=session_id,
            database_path=database_path,
            in_reply_to_message_id=in_reply_to_message_id,
        )
        return AgentReply(
            f"{CONTEXT_RESET_NOTICE}\n\n{reply.customer_reply}",
            reply.operator_message,
        )


def _reset_oversized_context(database_path, session_id):
    reset_history(database_path, session_id)
    logger.warning(
        "🧹 Context auto-reset | session=%s reason=context exceeds the TPM limit",
        session_id,
    )
    log_conversation(
        session_id,
        "SYSTEM",
        "Context auto-reset: the conversation became too long.",
    )
