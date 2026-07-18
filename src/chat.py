def add_message(history, role, text):
    history.append(
        {
            "role": role,
            "parts": [{"text": text}],
        }
    )


def send_message(history, user_text, get_model_reply):
    add_message(history, "user", user_text)

    model_reply = get_model_reply(history)
    add_message(history, "model", model_reply)

    return model_reply

