from pathlib import Path
import sys
import tempfile
import unittest

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from chat import send_message
from database import (
    create_session,
    initialize_database,
    list_session_ids,
    load_history,
    reset_history,
    save_exchange,
)


class ChatTests(unittest.TestCase):
    def test_send_message_keeps_user_and_model_messages(self):
        history = []

        reply = send_message(history, "Hello", lambda messages: "Hi there")

        self.assertEqual(reply, "Hi there")
        self.assertEqual(
            history,
            [
                {"role": "user", "parts": [{"text": "Hello"}]},
                {"role": "model", "parts": [{"text": "Hi there"}]},
            ],
        )


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_folder.cleanup()

    def test_history_is_loaded_after_a_new_database_connection(self):
        save_exchange(
            self.database_path,
            "terminal:magerram",
            "My name is Magerram.",
            "Nice to meet you, Magerram.",
        )

        history = load_history(self.database_path, "terminal:magerram")

        self.assertEqual(history[0]["parts"][0]["text"], "My name is Magerram.")
        self.assertEqual(
            history[1]["parts"][0]["text"], "Nice to meet you, Magerram."
        )

    def test_sessions_do_not_share_history(self):
        save_exchange(
            self.database_path,
            "terminal:magerram",
            "Hello",
            "Hi",
        )
        save_exchange(
            self.database_path,
            "whatsapp:magerram",
            "Salam",
            "Salam",
        )

        terminal_history = load_history(self.database_path, "terminal:magerram")
        whatsapp_history = load_history(self.database_path, "whatsapp:magerram")

        self.assertEqual(terminal_history[0]["parts"][0]["text"], "Hello")
        self.assertEqual(whatsapp_history[0]["parts"][0]["text"], "Salam")

    def test_reset_only_clears_the_selected_session(self):
        save_exchange(self.database_path, "terminal:magerram", "Hello", "Hi")
        save_exchange(self.database_path, "terminal:test_client", "Salam", "Salam")

        reset_history(self.database_path, "terminal:magerram")

        self.assertEqual(load_history(self.database_path, "terminal:magerram"), [])
        self.assertEqual(len(load_history(self.database_path, "terminal:test_client")), 2)

    def test_session_can_be_created_without_messages(self):
        create_session(self.database_path, "terminal:new_client")

        self.assertEqual(list_session_ids(self.database_path), ["terminal:new_client"])
