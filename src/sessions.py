def get_history(sessions, session_id):
    if session_id not in sessions:
        sessions[session_id] = []

    return sessions[session_id]


def reset_history(sessions, session_id):
    sessions[session_id] = []


def list_session_ids(sessions):
    return list(sessions)
