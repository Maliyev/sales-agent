from dataclasses import dataclass


@dataclass(frozen=True)
class AgentReply:
    customer_reply: str
    operator_message: str | None = None
