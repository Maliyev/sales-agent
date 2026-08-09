from agent_reply import AgentReply
from app_logging import get_logger, session_reference


logger = get_logger("delivery")


class ReplyDeliveryError(RuntimeError):
    pass


def deliver_agent_reply(destination, session_id, reply, send_fn, operator_fn):
    if not isinstance(reply, AgentReply):
        raise ReplyDeliveryError("Agent returned an invalid reply.")
    if not callable(send_fn) or not callable(operator_fn):
        raise ReplyDeliveryError("Reply callbacks must be callable.")

    send_fn(destination, reply.customer_reply)
    logger.info(
        "Customer reply delivered | session=%s chars=%d",
        session_reference(session_id),
        len(reply.customer_reply),
    )
    if reply.operator_message is not None:
        operator_fn(session_id, reply.operator_message)
        logger.warning(
            "Operator requested | session=%s",
            session_reference(session_id),
        )
