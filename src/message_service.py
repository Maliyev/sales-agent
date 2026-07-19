from agent import get_agent_reply
from database import load_history, save_exchange


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
    history = load_history(database_path, session_id)
    reply = get_agent_reply(
        history,
        user_text,
        model,
        api_key,
        system_instruction,
        selection_instruction,
        response_instruction,
    )
    save_exchange(database_path, session_id, user_text, reply)
    return reply
