from database import DatabaseError, run_database_operation


MAX_MESSAGE_ID_LENGTH = 500
MAX_SENDER_ID_LENGTH = 50


def claim_incoming_message(database_path, message_id, sender_id):
    message_id = _validate_identifier(
        message_id,
        "WhatsApp message ID",
        MAX_MESSAGE_ID_LENGTH,
    )
    sender_id = _validate_identifier(
        sender_id,
        "WhatsApp sender ID",
        MAX_SENDER_ID_LENGTH,
    )

    def insert_message(connection):
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO whatsapp_inbound_messages (
                message_id,
                sender_id
            )
            VALUES (?, ?)
            """,
            (message_id, sender_id),
        )
        return cursor.rowcount == 1

    return run_database_operation(database_path, insert_message)


def release_incoming_message(database_path, message_id):
    message_id = _validate_identifier(
        message_id,
        "WhatsApp message ID",
        MAX_MESSAGE_ID_LENGTH,
    )

    def delete_message(connection):
        connection.execute(
            "DELETE FROM whatsapp_inbound_messages WHERE message_id = ?",
            (message_id,),
        )

    run_database_operation(database_path, delete_message)


def _validate_identifier(value, name, max_length):
    if not isinstance(value, str) or not value.strip():
        raise DatabaseError(f"{name} must not be empty.")
    if len(value) > max_length:
        raise DatabaseError(f"{name} is too long.")
    return value.strip()
