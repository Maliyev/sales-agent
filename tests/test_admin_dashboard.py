from pathlib import Path
import sys
import unittest
import uuid


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from admin_dashboard import AdminDashboardError, create_admin_app
from database import (
    initialize_database,
    list_sessions,
    load_session_messages,
    save_exchange,
    save_model_message,
)


class AdminDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database_path = create_test_database_path()
        initialize_database(self.database_path)

    def tearDown(self):
        remove_test_database(self.database_path)

    def test_lists_latest_session_first(self):
        save_exchange(self.database_path, "whatsapp:1", "First", "Reply")
        save_exchange(self.database_path, "telegram:2", "Latest", "Answer")

        sessions = list_sessions(self.database_path)

        self.assertEqual(sessions[0]["session_id"], "telegram:2")
        self.assertEqual(sessions[0]["message_count"], 2)
        self.assertEqual(sessions[0]["last_text"], "Answer")

    def test_saves_a_manual_model_message(self):
        save_exchange(self.database_path, "whatsapp:1", "Hello", "Hi")

        message_id = save_model_message(
            self.database_path,
            "whatsapp:1",
            "Manual answer",
        )

        messages = load_session_messages(self.database_path, "whatsapp:1")
        self.assertEqual(messages[-1], {
            "id": message_id,
            "role": "model",
            "text": "Manual answer",
        })


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.database_path = create_test_database_path()
        initialize_database(self.database_path)
        save_exchange(self.database_path, "whatsapp:994", "Salam", "Salam!")
        self.sent = []
        app = create_admin_app(
            self.database_path,
            lambda session_id, text: self.sent.append((session_id, text)),
        )
        app.testing = True
        self.client = app.test_client()

    def tearDown(self):
        remove_test_database(self.database_path)

    def test_returns_sessions_and_messages(self):
        sessions = self.client.get("/api/sessions")
        messages = self.client.get("/api/sessions/whatsapp:994/messages")

        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.get_json()["sessions"][0]["session_id"], "whatsapp:994")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(len(messages.get_json()["messages"]), 2)

    def test_sends_and_saves_a_manual_message(self):
        response = self.client.post(
            "/api/sessions/whatsapp:994/messages",
            json={"text": "Operator answer"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.sent, [("whatsapp:994", "Operator answer")])
        messages = load_session_messages(self.database_path, "whatsapp:994")
        self.assertEqual(messages[-1]["text"], "Operator answer")

    def test_does_not_save_when_delivery_fails(self):
        app = create_admin_app(
            self.database_path,
            lambda _session_id, _text: (_ for _ in ()).throw(
                AdminDashboardError("Unsupported")
            ),
        )
        app.testing = True

        response = app.test_client().post(
            "/api/sessions/terminal:demo/messages",
            json={"text": "Hello"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(load_session_messages(self.database_path, "terminal:demo")), 0)


def create_test_database_path():
    data_folder = Path(__file__).resolve().parents[1] / "data"
    return data_folder / f"test_admin_{uuid.uuid4().hex}.db"


def remove_test_database(database_path):
    for suffix in ("", "-wal", "-shm"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
