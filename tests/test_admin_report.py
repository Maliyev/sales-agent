from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import admin_report


BAKU = timezone(timedelta(hours=4))


class AdminReportTests(unittest.TestCase):
    def test_calendar_day_switches_at_five_in_baku(self):
        before = datetime(2026, 9, 25, 4, 10, tzinfo=BAKU)
        after = datetime(2026, 9, 25, 5, 10, tzinfo=BAKU)
        self.assertEqual(admin_report.calendar_window(1, before)[0].isoformat(),
                         "2026-09-24T00:00:00+04:00")
        self.assertEqual(admin_report.calendar_window(1, after)[0].isoformat(),
                         "2026-09-25T00:00:00+04:00")
        self.assertEqual(admin_report.calendar_window(3, before)[0].isoformat(),
                         "2026-09-22T00:00:00+04:00")

    def test_reads_rotated_logs_with_baku_calendar_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "conversations.log"
            Path(f"{path}.1").write_text(
                "26-09-23 19:59:00 | whatsapp:old | 💬 USER | outside\n"
                "26-09-23 20:00:00 | whatsapp:one | 💬 USER | midnight\n",
                encoding="utf-8",
            )
            path.write_text(
                "26-09-24 20:05:00 | telegram:two | 💬 USER | after midnight\n"
                "26-09-25 00:15:00 | telegram:late | 💬 USER | too late\n",
                encoding="utf-8",
            )
            now = datetime(2026, 9, 25, 4, 10, tzinfo=BAKU)
            start, end = admin_report.calendar_window(1, now)
            result = admin_report.read_conversation_window(
                path, start, end, log_timezone=timezone.utc,
            )
            self.assertEqual(len(result["lines"]), 2)
            self.assertEqual(result["customer_sessions"], 2)

    def test_only_manual_generation_calls_openrouter_with_low_reasoning(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "conversations.log"
            path.write_text(
                "26-09-24 08:00:00 | whatsapp:one | 💬 USER | Salam\n",
                encoding="utf-8",
            )
            calls = []

            def fake_generate(history, model, key, prompt, **kwargs):
                calls.append((history, model, key, prompt, kwargs))
                return {"candidates": [{"content": {"parts": [{"text": "Краткий отчёт"}]}}],
                        "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20}}

            with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = admin_report.generate_report(
                    1, path, generate_fn=fake_generate,
                    now=datetime(2026, 9, 24, 16, tzinfo=BAKU),
                    log_timezone=timezone.utc,
                )
            self.assertEqual(result["report"], "Краткий отчёт")
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1], "z-ai/glm-5.3-flash")
            self.assertEqual(calls[0][4]["reasoning_effort"], "low")
            self.assertIn("Salam", calls[0][0][0]["parts"][0]["text"])

    def test_oversized_log_is_rejected_before_api_call(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "conversations.log"
            path.write_text(
                "26-09-24 08:00:00 | whatsapp:one | 💬 USER | long text\n",
                encoding="utf-8",
            )
            generate = mock.Mock()
            with mock.patch.object(admin_report, "MAX_LOG_CHARACTERS", 10):
                with self.assertRaises(admin_report.ReportError):
                    admin_report.generate_report(
                        1, path, generate_fn=generate,
                        now=datetime(2026, 9, 24, 16, tzinfo=BAKU),
                        log_timezone=timezone.utc,
                    )
            generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
