from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from compaction import (
    MAX_SUMMARY_CHARACTERS,
    SUMMARY_PREFIX,
    CompactionError,
    compact_history,
)
from database import initialize_database, insert_incoming_message, save_exchange


class CompactionTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)
        save_exchange(self.database_path, "telegram:1", "Hello", "Hi")

    def tearDown(self):
        self.temp_folder.cleanup()

    def read_api_calls(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                """
                SELECT purpose, status, prompt_tokens, completion_tokens, error
                FROM api_calls
                """
            ).fetchall()

    def test_compacts_the_history_into_a_summary_row(self):
        def fake_generate(history, model, api_key, system_instruction, **kwargs):
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["role"], "user")
            transcript = history[0]["parts"][0]["text"]
            self.assertIn("Customer: Hello", transcript)
            self.assertIn("Seller: Hi", transcript)
            self.assertRegex(transcript, r"^\[\d{4}-\d{2}-\d{2} .+\] Customer:")
            self.assertEqual(model, "compactor-model")
            self.assertEqual(api_key, "secret-key")
            self.assertEqual(system_instruction, "Summarize this")
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "- Wants a laptop"}]}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 40,
                },
            }

        compact_history(
            self.database_path,
            "telegram:1",
            model="compactor-model",
            api_key="secret-key",
            compaction_instruction="Summarize this",
            generate_fn=fake_generate,
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                "SELECT role, text, archived FROM messages ORDER BY id"
            ).fetchall()
        self.assertEqual(
            rows,
            [
                ("user", "Hello", 1),
                ("model", "Hi", 1),
                ("tool", f"{SUMMARY_PREFIX}\n- Wants a laptop", 0),
            ],
        )
        self.assertEqual(
            self.read_api_calls(),
            [("compaction", "ok", 120, 40, None)],
        )

    def test_includes_the_pending_message_in_the_transcript(self):
        insert_incoming_message(
            self.database_path,
            "telegram:1",
            "Pending giant message",
        )
        captured = []

        def fake_generate(history, model, api_key, system_instruction, **kwargs):
            captured.append(history[0]["parts"][0]["text"])
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "- Wants a laptop"}]}}
                ]
            }

        compact_history(
            self.database_path,
            "telegram:1",
            model="compactor-model",
            api_key="secret-key",
            compaction_instruction="Summarize this",
            generate_fn=fake_generate,
        )

        self.assertIn("Customer: Pending giant message", captured[0])

    def test_reads_the_instruction_from_the_prompt_file_by_default(self):
        with patch(
            "compaction.load_compaction_instruction",
            return_value="Default instruction",
        ) as load_instruction:
            compact_history(
                self.database_path,
                "telegram:1",
                model="compactor-model",
                api_key="secret-key",
                generate_fn=lambda history, model, key, instruction, **kwargs: {
                    "candidates": [{"content": {"parts": [{"text": "S"}]}}]
                },
            )

        load_instruction.assert_called_once_with()

    def test_fails_fast_when_the_history_is_empty(self):
        def failing_generate(*args, **kwargs):
            raise AssertionError("The model must not be called.")

        with self.assertRaisesRegex(CompactionError, "nothing to compact"):
            compact_history(
                self.database_path,
                "telegram:unknown",
                model="compactor-model",
                api_key="secret-key",
                generate_fn=failing_generate,
            )

        self.assertEqual(self.read_api_calls(), [])

    def test_records_a_failed_call_when_the_model_fails(self):
        def failing_generate(*args, **kwargs):
            raise RuntimeError("Gemini down")

        with self.assertRaises(CompactionError):
            compact_history(
                self.database_path,
                "telegram:1",
                model="compactor-model",
                api_key="secret-key",
                compaction_instruction="Summarize this",
                generate_fn=failing_generate,
            )

        self.assertEqual(
            self.read_api_calls(),
            [("compaction", "failed", 0, 0, "RuntimeError: Gemini down")],
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            archived = connection.execute(
                "SELECT COUNT(*) FROM messages WHERE archived = 1"
            ).fetchone()[0]
        self.assertEqual(archived, 0)

    def test_fails_when_the_summary_is_empty(self):
        def empty_generate(*args, **kwargs):
            return {"candidates": [{"content": {"parts": [{"text": "  "}]}}]}

        with self.assertRaisesRegex(CompactionError, "empty summary"):
            compact_history(
                self.database_path,
                "telegram:1",
                model="compactor-model",
                api_key="secret-key",
                compaction_instruction="Summarize this",
                generate_fn=empty_generate,
            )

        self.assertEqual(
            self.read_api_calls()[0][1],
            "failed",
        )

    def test_truncates_an_overlong_summary(self):
        def verbose_generate(*args, **kwargs):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "x" * 9000}]}}
                ]
            }

        compact_history(
            self.database_path,
            "telegram:1",
            model="compactor-model",
            api_key="secret-key",
            compaction_instruction="Summarize this",
            generate_fn=verbose_generate,
        )

        with closing(sqlite3.connect(self.database_path)) as connection:
            text = connection.execute(
                "SELECT text FROM messages WHERE role = 'tool'"
            ).fetchone()[0]
        self.assertEqual(len(text), len(SUMMARY_PREFIX) + 1 + MAX_SUMMARY_CHARACTERS)

    def test_records_zero_tokens_when_usage_is_unreadable(self):
        def generate_ok(*args, **kwargs):
            return {"candidates": [{"content": {"parts": [{"text": "S"}]}}]}

        def broken_usage_fn(data):
            raise ValueError("no usage")

        compact_history(
            self.database_path,
            "telegram:1",
            model="compactor-model",
            api_key="secret-key",
            compaction_instruction="Summarize this",
            generate_fn=generate_ok,
            usage_fn=broken_usage_fn,
        )

        self.assertEqual(
            self.read_api_calls(),
            [("compaction", "ok", 0, 0, None)],
        )


if __name__ == "__main__":
    unittest.main()
