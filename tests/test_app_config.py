import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from app_config import (
    ConfigError,
    get_context_overflow_auto_reset,
    get_gemini_model,
    get_gemini_retry_settings,
    get_message_rate_limits,
    get_token_abuse_settings,
    get_tpm_limit,
    load_config,
    set_config,
)


class LoadConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_folder.name) / "config.json"

    def tearDown(self):
        self.temp_folder.cleanup()

    def write_config(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_returns_defaults_when_the_file_is_missing(self):
        config = load_config(self.path)

        self.assertEqual(config["limits"]["message_rate"]["max_messages"], 15)
        self.assertEqual(config["limits"]["message_rate"]["window_seconds"], 60)
        self.assertEqual(config["gemini"]["tpm_limit"], 0)
        self.assertIs(config["limits"]["context_overflow"]["auto_reset"], True)

    def test_merges_a_partial_config_over_the_defaults(self):
        self.write_config({"gemini": {"tpm_limit": 250000}})

        config = load_config(self.path)

        self.assertEqual(config["gemini"]["tpm_limit"], 250000)
        self.assertEqual(config["gemini"]["model"], "gemini-2.5-flash-lite")
        self.assertEqual(config["limits"]["message_rate"]["max_messages"], 15)

    def test_rejects_invalid_json(self):
        self.path.write_text("{not json", encoding="utf-8")

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_non_object_config(self):
        self.path.write_text("[1, 2]", encoding="utf-8")

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_zero_message_rate(self):
        self.write_config({"limits": {"message_rate": {"max_messages": 0}}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_negative_tpm_limit(self):
        self.write_config({"gemini": {"tpm_limit": -5}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_zero_token_abuse_window(self):
        self.write_config({"limits": {"token_abuse": {"window_seconds": 0}}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_non_boolean_auto_reset(self):
        self.write_config({"limits": {"context_overflow": {"auto_reset": "yes"}}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_empty_retry_delays(self):
        self.write_config({"gemini": {"retry": {"delays": []}}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_non_positive_retry_delays(self):
        self.write_config({"gemini": {"retry": {"delays": [15, 0]}}})

        self.assertRaises(ConfigError, load_config, self.path)

    def test_rejects_a_zero_retry_max_wait(self):
        self.write_config({"gemini": {"retry": {"max_wait_seconds": 0}}})

        self.assertRaises(ConfigError, load_config, self.path)


class ConfigAccessorsTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_folder.name) / "config.json"

    def tearDown(self):
        set_config(None)
        self.temp_folder.cleanup()

    def test_accessors_read_the_active_config(self):
        set_config(
            {
                "gemini": {
                    "model": "test-model",
                    "tpm_limit": 1000,
                    "retry": {"delays": [5, 10], "max_wait_seconds": 60},
                },
                "limits": {
                    "message_rate": {"max_messages": 7, "window_seconds": 30},
                    "token_abuse": {"limit": 900, "window_seconds": 45},
                    "context_overflow": {"auto_reset": False},
                },
            }
        )

        self.assertEqual(get_gemini_model(), "test-model")
        self.assertEqual(get_tpm_limit(), 1000)
        self.assertEqual(get_gemini_retry_settings(), ([5, 10], 60))
        self.assertEqual(get_message_rate_limits(), (7, 30))
        self.assertEqual(get_token_abuse_settings(), (900, 45))
        self.assertIs(get_context_overflow_auto_reset(), False)

    def test_resetting_the_config_reloads_it_from_disk(self):
        self.path.write_text(json.dumps({"gemini": {"model": "temp"}}), encoding="utf-8")
        set_config(
            {
                "gemini": {"model": "temp", "tpm_limit": 1},
                "limits": {
                    "message_rate": {"max_messages": 1, "window_seconds": 1},
                    "token_abuse": {"limit": 0, "window_seconds": 1},
                },
            }
        )

        with patch("app_config.CONFIG_PATH", self.path):
            set_config(None)

            self.assertEqual(get_gemini_model(), "temp")


if __name__ == "__main__":
    unittest.main()
