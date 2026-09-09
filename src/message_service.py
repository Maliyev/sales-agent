from agent import get_agent_reply
from agent_reply import AgentReply
from app_config import (
    get_compaction_model,
    get_context_overflow_auto_compaction,
    get_context_overflow_auto_reset,
)
from app_logging import flatten_text, get_logger, log_conversation
from compaction import CompactionError, compact_history
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
    list_start_notify_fn=None,
):
    history = load_history(database_path, session_id)
    log_conversation(session_id, "USER", flatten_text(user_text))

    def run_agent(history):
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
            list_start_notify_fn=list_start_notify_fn,
        )

    try:
        return run_agent(history)
    except SessionContextTooLargeError as error:
        overflow_error = error

    if get_context_overflow_auto_compaction() and _try_compaction(
        database_path,
        session_id,
        api_key,
        in_reply_to_message_id,
    ):
        history = load_history(database_path, session_id)
        notice = None
    elif get_context_overflow_auto_reset():
        _reset_oversized_context(database_path, session_id)
        history = load_history(database_path, session_id)
        notice = CONTEXT_RESET_NOTICE
    else:
        raise overflow_error

    try:
        reply = run_agent(history)
    except SessionContextTooLargeError:
        if notice is not None or not get_context_overflow_auto_reset():
            raise
        _reset_oversized_context(database_path, session_id)
        history = load_history(database_path, session_id)
        reply = run_agent(history)
        return AgentReply(
            f"{CONTEXT_RESET_NOTICE}\n\n{reply.customer_reply}",
            reply.operator_message,
        )

    if notice is not None:
        return AgentReply(
            f"{notice}\n\n{reply.customer_reply}",
            reply.operator_message,
        )
    return reply


def _try_compaction(database_path, session_id, api_key, in_reply_to_message_id):
    try:
        compact_history(
            database_path,
            session_id,
            model=get_compaction_model(),
            api_key=api_key,
            in_reply_to_message_id=in_reply_to_message_id,
        )
    except CompactionError as error:
        logger.warning(
            "🧹 Context compaction failed | session=%s error=%s",
            session_id,
            error,
        )
        return False
    return True


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
