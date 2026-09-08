import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from database import create_session, initialize_database
from image_reader import (
    ImageReadError,
    build_image_user_text,
    describe_image,
    is_image,
    resolve_mime_type,
)
from prompts import load_prompt_file


class FakeVision:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or {
            "candidates": [
                {"content": {"parts": [{"text": "  A red LED.  "}]}},
            ],
            "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 8},
        }
        self.error = error

    def __call__(self, contents, model, api_key, system_instruction, **kwargs):
        self.calls.append(
            {
                "contents": contents,
                "model": model,
                "api_key": api_key,
                "system_instruction": system_instruction,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


class ImageReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_folder = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_folder.name) / "sales_agent.db"
        initialize_database(self.database_path)
        create_session(self.database_path, "telegram:1")

    def tearDown(self):
        self.temp_folder.cleanup()

    def read_api_calls(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute(
                """
                SELECT purpose, prompt_tokens, completion_tokens, status, error
                FROM api_calls
                """
            ).fetchall()

    def test_describes_an_image_and_records_the_call(self):
        vision = FakeVision()

        description = describe_image(
            b"IMG",
            "image/jpeg",
            "test-model",
            "api-key",
            self.database_path,
            "telegram:1",
            instruction="Describe it.",
            generate_fn=vision,
        )

        self.assertEqual(description, "A red LED.")
        self.assertEqual(len(vision.calls), 1)
        call = vision.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["api_key"], "api-key")
        self.assertEqual(call["system_instruction"], "Describe it.")
        self.assertEqual(
            call["contents"],
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": "SU1H",
                            }
                        },
                        {"text": "Describe the attached image."},
                    ],
                }
            ],
        )
        self.assertEqual(
            self.read_api_calls(),
            [("vision", 120, 8, "ok", None)],
        )

    def test_uses_the_prompt_file_by_default(self):
        vision = FakeVision()

        describe_image(
            b"IMG",
            "image/jpeg",
            "test-model",
            "api-key",
            self.database_path,
            "telegram:1",
            generate_fn=vision,
        )

        self.assertEqual(
            vision.calls[0]["system_instruction"],
            load_prompt_file("prompts/07_image_describer.md"),
        )

    def test_records_a_failed_call_when_the_model_fails(self):
        vision = FakeVision(error=RuntimeError("HTTP 503"))

        with self.assertRaisesRegex(ImageReadError, "Image description failed"):
            describe_image(
                b"IMG",
                "image/jpeg",
                "test-model",
                "api-key",
                self.database_path,
                "telegram:1",
                instruction="Describe it.",
                generate_fn=vision,
            )

        rows = self.read_api_calls()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][:4], ("vision", 0, 0, "failed"))
        self.assertIn("RuntimeError: HTTP 503", rows[0][4])

    def test_rejects_an_empty_model_description(self):
        vision = FakeVision(
            response={"candidates": [{"content": {"parts": [{"text": "   "}]}}]},
        )

        with self.assertRaises(ImageReadError):
            describe_image(
                b"IMG",
                "image/jpeg",
                "test-model",
                "api-key",
                self.database_path,
                "telegram:1",
                instruction="Describe it.",
                generate_fn=vision,
            )

        self.assertEqual(self.read_api_calls()[0][3], "failed")

    def test_counts_tokens_as_zero_when_usage_is_broken(self):
        vision = FakeVision()
        vision.response.pop("usageMetadata")

        describe_image(
            b"IMG",
            "image/jpeg",
            "test-model",
            "api-key",
            self.database_path,
            "telegram:1",
            instruction="Describe it.",
            generate_fn=vision,
        )

        self.assertEqual(
            self.read_api_calls(),
            [("vision", 0, 0, "ok", None)],
        )

    def test_rejects_empty_data_or_mime_without_calling_the_model(self):
        vision = FakeVision()

        for args in ((b"", "image/jpeg"), (b"IMG", "  ")):
            with self.assertRaises(ImageReadError):
                describe_image(
                    args[0],
                    args[1],
                    "test-model",
                    "api-key",
                    self.database_path,
                    "telegram:1",
                    instruction="Describe it.",
                    generate_fn=vision,
                )

        self.assertEqual(vision.calls, [])
        self.assertEqual(self.read_api_calls(), [])


class ImageHelpersTests(unittest.TestCase):
    def test_detects_images_by_mime_or_extension(self):
        self.assertIs(is_image("image/png"), True)
        self.assertIs(is_image(" IMAGE/JPEG "), True)
        self.assertIs(is_image(None, "photo.jpg"), True)
        self.assertIs(is_image(None, "photo.WEBP"), True)
        self.assertIs(is_image(None, "scan.pdf"), False)
        self.assertIs(is_image("application/pdf", "scan.pdf"), False)
        self.assertIs(is_image(None, None), False)
        self.assertIs(is_image(None, "archive"), False)

    def test_resolves_the_mime_type(self):
        self.assertEqual(
            resolve_mime_type("photo.png", " image/jpeg "), "image/jpeg"
        )
        self.assertEqual(resolve_mime_type("photo.png"), "image/png")
        self.assertEqual(resolve_mime_type("photo.jpeg"), "image/jpeg")
        self.assertEqual(resolve_mime_type("photo.webp"), "image/webp")
        self.assertEqual(resolve_mime_type("photo"), "")
        self.assertEqual(resolve_mime_type(None), "")

    def test_builds_the_user_text_with_a_caption(self):
        user_text = build_image_user_text("A red LED.", "What is this?")

        self.assertIn("may contain inaccuracies", user_text)
        self.assertIn("--- Image description ---", user_text)
        self.assertIn("A red LED.", user_text)
        self.assertIn(
            "Customer's message with the image: What is this?",
            user_text,
        )

    def test_builds_the_user_text_without_a_caption(self):
        user_text = build_image_user_text("A red LED.")

        self.assertNotIn("Customer's message", user_text)


if __name__ == "__main__":
    unittest.main()
