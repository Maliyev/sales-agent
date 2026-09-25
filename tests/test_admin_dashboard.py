from pathlib import Path
import json
import os
import re
import sys
import unittest
import uuid
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app_config
from admin_dashboard import AdminDashboardError, create_admin_app, register_admin_routes
from database import (
    create_session,
    dashboard_overview,
    initialize_database,
    list_sessions,
    load_session_messages,
    record_agent_turn,
    record_api_call,
    save_exchange,
    save_model_message,
)
from whatsapp_server import create_webhook_app


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

    def test_overview_separates_messages_turns_and_api_calls(self):
        user_id, _ = save_exchange(self.database_path, "whatsapp:994", "Hello", "Hi")
        record_agent_turn(self.database_path, "whatsapp:994")
        record_api_call(self.database_path, "whatsapp:994", user_id, "decision",
                        "gemini-3.1-flash-lite", prompt_tokens=8000,
                        completion_tokens=300)
        record_api_call(self.database_path, "whatsapp:994", user_id, "final",
                        "openrouter:z-ai/glm-5.3-flash", prompt_tokens=9000,
                        completion_tokens=500, cost_usd=0.0025)

        overview = dashboard_overview(self.database_path, 24)

        self.assertEqual(overview["totals"]["customer_messages"], 1)
        self.assertEqual(overview["totals"]["agent_turns"], 1)
        self.assertEqual(overview["totals"]["llm_api_calls"], 2)
        self.assertEqual(overview["totals"]["input"], 17000)
        self.assertEqual(overview["openrouter"]["total"], 9500)
        self.assertEqual(overview["openrouter"]["cost_usd"], 0.0025)
        self.assertEqual(overview["openrouter"]["priced_calls"], 1)

    def test_report_api_usage_counts_without_appearing_as_customer_chat(self):
        create_session(self.database_path, "admin:report")
        record_api_call(self.database_path, "admin:report", None, "final",
                        "openrouter:z-ai/glm-5.3-flash", prompt_tokens=500,
                        completion_tokens=50)
        self.assertEqual(list_sessions(self.database_path), [])
        overview = dashboard_overview(self.database_path, 24)
        self.assertEqual(overview["totals"]["llm_api_calls"], 1)
        self.assertEqual(overview["openrouter"]["total"], 550)
        self.assertEqual(overview["openrouter"]["priced_calls"], 0)
        self.assertEqual(overview["top_sessions"], [])


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.old_password = os.environ.get("ADMIN_PASSWORD")
        self.old_secret = os.environ.get("ADMIN_SESSION_SECRET")
        os.environ["ADMIN_PASSWORD"] = "test-password"
        os.environ["ADMIN_SESSION_SECRET"] = "test-session-secret-longer-than-thirty-two-characters"
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
        self.login(self.client)

    def tearDown(self):
        remove_test_database(self.database_path)
        for name, value in (("ADMIN_PASSWORD", self.old_password),
                            ("ADMIN_SESSION_SECRET", self.old_secret)):
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def login(self, client):
        page = client.get("/admin/login")
        token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
        response = client.post("/admin/login", data={"password": "test-password", "csrf_token": token})
        self.assertEqual(response.status_code, 302)
        with client.session_transaction() as session:
            return session["csrf_token"]

    def test_returns_sessions_and_messages(self):
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        static_response = self.client.get("/admin/static/admin.js")
        self.assertEqual(static_response.status_code, 200)
        static_response.close()
        sessions = self.client.get("/admin/api/sessions")
        messages = self.client.get("/admin/api/sessions/whatsapp:994/messages")

        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(sessions.get_json()["sessions"][0]["session_id"], "whatsapp:994")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(len(messages.get_json()["messages"]), 2)

    def test_sends_and_saves_a_manual_message(self):
        response = self.client.post(
            "/admin/api/sessions/whatsapp:994/messages",
            json={"text": "Operator answer"},
            headers={"X-CSRF-Token": self.csrf()},
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
        client = app.test_client()
        token = self.login(client)

        response = client.post(
            "/admin/api/sessions/whatsapp:994/messages",
            json={"text": "Hello"},
            headers={"X-CSRF-Token": token},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(load_session_messages(self.database_path, "whatsapp:994")), 2)

    def test_requires_login_and_csrf(self):
        app = create_admin_app(self.database_path, lambda _id, _text: None)
        anonymous = app.test_client()
        self.assertEqual(anonymous.get("/admin/api/sessions").status_code, 401)
        self.assertEqual(anonymous.get("/admin/").status_code, 302)
        self.assertEqual(self.client.post(
            "/admin/api/sessions/whatsapp:994/reset"
        ).status_code, 403)

    def test_settings_validate_before_replacing_file(self):
        path = self.database_path.with_suffix(".json")
        original = json.loads(json.dumps(app_config.DEFAULT_CONFIG))
        path.write_text(json.dumps(original), encoding="utf-8")
        try:
            with mock.patch.object(app_config, "CONFIG_PATH", path):
                app_config.set_config(None)
                config = self.client.get("/admin/api/settings").get_json()["config"]
                config["limits"]["max_search_rounds"] = 0
                rejected = self.client.put("/admin/api/settings", json={"config": config},
                                           headers={"X-CSRF-Token": self.csrf()})
                self.assertEqual(rejected.status_code, 400)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), original)
                config["limits"]["max_search_rounds"] = 4
                saved = self.client.put("/admin/api/settings", json={"config": config},
                                        headers={"X-CSRF-Token": self.csrf()})
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(app_config.get_max_search_rounds(), 4)
        finally:
            app_config.set_config(None)
            path.unlink(missing_ok=True)

    def test_webhook_and_admin_share_one_app(self):
        app = create_webhook_app("verify", "secret", lambda _message: None)
        register_admin_routes(app, self.database_path, lambda _id, _text: None)
        client = app.test_client()
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.post("/webhooks/whatsapp", data=b"{}").status_code, 401)
        self.assertEqual(client.get("/admin/api/sessions").status_code, 401)
        self.assertEqual(client.get("/admin/static/admin.js").status_code, 302)

    def test_logs_cursor_reads_only_new_content(self):
        path = self.database_path.with_suffix(".log")
        path.write_text("first line\n", encoding="utf-8")
        try:
            app = create_webhook_app("verify", "secret", lambda _message: None)
            register_admin_routes(app, self.database_path, lambda _id, _text: None,
                                  log_path=path)
            client = app.test_client()
            self.login(client)
            first = client.get("/admin/api/logs").get_json()
            with path.open("a", encoding="utf-8") as file:
                file.write("second line\n")
            second = client.get(f"/admin/api/logs?offset={first['offset']}").get_json()
            self.assertEqual(first["lines"], ["first line"])
            self.assertEqual(second["lines"], ["second line"])
        finally:
            path.unlink(missing_ok=True)

    def test_report_runs_only_on_authenticated_post(self):
        fake_result = {"report": "OK", "model_called": True}
        with mock.patch("admin_dashboard.generate_report", return_value=fake_result) as generate:
            self.assertEqual(self.client.get("/admin/api/report").status_code, 405)
            self.assertEqual(self.client.post("/admin/api/report", json={"days": 1}).status_code, 403)
            self.assertEqual(self.client.post(
                "/admin/api/report", json={"days": 1},
                headers={"X-CSRF-Token": self.csrf()},
            ).get_json(), fake_result)
            generate.assert_called_once()

    def csrf(self):
        with self.client.session_transaction() as session:
            return session["csrf_token"]


def create_test_database_path():
    data_folder = Path(__file__).resolve().parents[1] / "data"
    return data_folder / f"test_admin_{uuid.uuid4().hex}.db"


def remove_test_database(database_path):
    for suffix in ("", "-wal", "-shm"):
        Path(f"{database_path}{suffix}").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
