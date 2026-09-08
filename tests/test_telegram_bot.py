from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import requests

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from telegram_bot import (
    MAX_MESSAGE_LENGTH,
    TelegramError,
    _download_document,
    deliver_agent_reply,
    get_updates,
    handle_update,
    send_message,
    split_message,
)
from agent_reply import AgentReply
from document_reader import DocumentReadError, build_document_user_text
from image_reader import ImageReadError, build_image_user_text


class TelegramBotTests(unittest.TestCase):
    def test_delivers_customer_and_operator_messages_separately(self):
        customer_messages = []
        operator_messages = []

        deliver_agent_reply(
            123,
            "telegram:123",
            AgentReply("Customer text", "Operator summary"),
            lambda chat_id, text: customer_messages.append((chat_id, text)),
            lambda session_id, text: operator_messages.append((session_id, text)),
        )

        self.assertEqual(customer_messages, [(123, "Customer text")])
        self.assertEqual(
            operator_messages,
            [("telegram:123", "Operator summary")],
        )

    def test_regular_message_uses_a_separate_telegram_session(self):
        submissions = []
        sent = []

        handle_update(
            {"message": {"chat": {"id": 123}, "text": "Arduino Uno"}},
            lambda session_id, text, chat_id: submissions.append(
                (session_id, text, chat_id)
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(submissions, [("telegram:123", "Arduino Uno", 123)])
        self.assertEqual(sent, [])

    def test_reset_clears_only_the_current_telegram_session(self):
        resets = []
        sent = []

        handle_update(
            {"message": {"chat": {"id": 456}, "text": "/reset@demo_bot"}},
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            resets.append,
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(resets, ["telegram:456"])
        self.assertEqual(sent[0][0], 456)
        self.assertIn("silindi", sent[0][1])

    def test_blocked_session_is_ignored_before_commands_or_agent(self):
        handle_update(
            {"message": {"chat": {"id": 456}, "text": "/start"}},
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: self.fail("A blocked session should get no reply"),
            lambda session_id: False,
        )

    def test_non_text_message_does_not_call_the_agent(self):
        sent = []

        handle_update(
            {"message": {"chat": {"id": 7}, "photo": []}},
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(sent[0][0], 7)

    def test_document_message_submits_the_converted_text(self):
        submissions = []
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 123},
                    "document": {
                        "file_id": "file-1",
                        "file_name": "bom.xlsx",
                        "file_size": 1024,
                    },
                    "caption": "Check these please",
                }
            },
            lambda session_id, text, chat_id: submissions.append(
                (session_id, text, chat_id)
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: b"data",
            read_document_fn=lambda filename, data: "Component\tQty",
        )

        expected = build_document_user_text(
            "bom.xlsx",
            "Component\tQty",
            caption="Check these please",
        )
        self.assertEqual(
            submissions,
            [("telegram:123", expected, 123)],
        )
        self.assertEqual(sent, [])

    def test_unsupported_document_gets_a_reply_without_a_download(self):
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "document": {"file_id": "file-1", "file_name": "scan.pdf"},
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: self.fail(
                "Download should not be called"
            ),
            read_document_fn=lambda filename, data: "text",
        )

        self.assertEqual(len(sent), 1)
        self.assertIn(".xlsx", sent[0][1])

    def test_oversized_document_is_rejected_before_the_download(self):
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "document": {
                        "file_id": "file-1",
                        "file_name": "bom.xlsx",
                        "file_size": 6 * 1024 * 1024,
                    },
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: self.fail(
                "Download should not be called"
            ),
            read_document_fn=lambda filename, data: "text",
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("5 MB", sent[0][1])

    def test_unreadable_document_gets_a_friendly_reply(self):
        sent = []

        def broken_reader(filename, data):
            raise DocumentReadError("The Excel file could not be parsed.")

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "document": {"file_id": "file-1", "file_name": "bom.xlsx"},
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: b"data",
            read_document_fn=broken_reader,
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("oxuya bilmirəm", sent[0][1])

    def test_failed_document_download_gets_the_generic_error_reply(self):
        sent = []

        def broken_downloader(file_id):
            raise TelegramError("Telegram document download failed.")

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "document": {"file_id": "file-1", "file_name": "bom.xlsx"},
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=broken_downloader,
            read_document_fn=lambda filename, data: "text",
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("cavab verə bilmirəm", sent[0][1])

    def test_blocked_session_documents_are_ignored(self):
        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "document": {"file_id": "file-1", "file_name": "bom.xlsx"},
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: self.fail("A blocked session should get no reply"),
            lambda session_id: False,
            download_document_fn=lambda file_id: self.fail(
                "Download should not be called"
            ),
            read_document_fn=lambda filename, data: "text",
        )

    def test_photo_message_submits_the_vision_description(self):
        submissions = []
        sent = []
        downloads = []
        described = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 123},
                    "photo": [
                        {"file_id": "small", "width": 90, "height": 90},
                        {"file_id": "big", "width": 1280, "height": 720},
                    ],
                    "caption": "What is this?",
                }
            },
            lambda session_id, text, chat_id: submissions.append(
                (session_id, text, chat_id)
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: downloads.append(file_id) or b"IMG",
            describe_image_fn=lambda data, mime, session_id: described.append(
                (data, mime, session_id)
            )
            or "A red LED.",
        )

        self.assertEqual(downloads, ["big"])
        self.assertEqual(
            described,
            [(b"IMG", "image/jpeg", "telegram:123")],
        )
        self.assertEqual(
            submissions,
            [
                (
                    "telegram:123",
                    build_image_user_text("A red LED.", "What is this?"),
                    123,
                )
            ],
        )
        self.assertEqual(sent, [])

    def test_photo_without_readable_sizes_falls_back_to_the_text_reply(self):
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [{"width": 90, "height": 90}],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
        )

        self.assertEqual(len(sent), 1)

    def test_oversized_photo_is_rejected_before_the_download(self):
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [
                        {
                            "file_id": "big",
                            "width": 4000,
                            "height": 3000,
                            "file_size": 6 * 1024 * 1024,
                        }
                    ],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: self.fail(
                "Download should not be called"
            ),
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("5 MB", sent[0][1])

    def test_oversized_photo_data_is_rejected_after_the_download(self):
        sent = []

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [{"file_id": "big", "width": 4000, "height": 3000}],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: b"x" * (6 * 1024 * 1024),
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("5 MB", sent[0][1])

    def test_failed_photo_download_gets_the_generic_error_reply(self):
        sent = []

        def broken_downloader(file_id):
            raise TelegramError("Telegram document download failed.")

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [{"file_id": "file-1", "width": 90, "height": 90}],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=broken_downloader,
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("cavab verə bilmirəm", sent[0][1])

    def test_failed_image_description_gets_a_text_hint(self):
        sent = []

        def broken_describer(data, mime, session_id):
            raise ImageReadError("Image description failed.")

        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [{"file_id": "file-1", "width": 90, "height": 90}],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: b"IMG",
            describe_image_fn=broken_describer,
        )

        self.assertEqual(len(sent), 1)
        self.assertIn("emal edə bilmirəm", sent[0][1])

    def test_blocked_session_photos_are_ignored(self):
        handle_update(
            {
                "message": {
                    "chat": {"id": 7},
                    "photo": [{"file_id": "file-1", "width": 90, "height": 90}],
                }
            },
            lambda session_id, text, chat_id: self.fail(
                "Agent should not be called"
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: self.fail("A blocked session should get no reply"),
            lambda session_id: False,
            download_document_fn=lambda file_id: self.fail(
                "Download should not be called"
            ),
        )

    def test_an_image_sent_as_a_document_is_routed_to_the_vision_path(self):
        submissions = []
        sent = []

        def broken_reader(filename, data):
            self.fail("Document reader should not be called for images")

        handle_update(
            {
                "message": {
                    "chat": {"id": 123},
                    "document": {
                        "file_id": "file-1",
                        "file_name": "photo.png",
                        "mime_type": "image/png",
                        "file_size": 1024,
                    },
                    "caption": "Check this part",
                }
            },
            lambda session_id, text, chat_id: submissions.append(
                (session_id, text, chat_id)
            ),
            lambda session_id: self.fail("Reset should not be called"),
            lambda chat_id, text: sent.append((chat_id, text)),
            lambda session_id: True,
            download_document_fn=lambda file_id: b"IMG",
            read_document_fn=broken_reader,
            describe_image_fn=lambda data, mime, session_id: (
                self.assertEqual((data, mime), (b"IMG", "image/png")) or "A resistor"
            ),
        )

        self.assertEqual(
            submissions,
            [
                (
                    "telegram:123",
                    build_image_user_text("A resistor", "Check this part"),
                    123,
                )
            ],
        )
        self.assertEqual(sent, [])

    def test_download_document_uses_the_file_api(self):
        file_info = Mock()
        file_info.json.return_value = {
            "ok": True,
            "result": {"file_path": "documents/file_1.xlsx"},
        }
        file_response = Mock()
        file_response.content = b"DATA"
        session = Mock()
        session.get.side_effect = [file_info, file_response]

        data = _download_document("secret-token", "file-1", session=session)

        self.assertEqual(data, b"DATA")
        first_url = session.get.call_args_list[0].args[0]
        second_url = session.get.call_args_list[1].args[0]
        self.assertEqual(
            first_url,
            "https://api.telegram.org/botsecret-token/getFile",
        )
        self.assertEqual(
            second_url,
            "https://api.telegram.org/file/botsecret-token/documents/file_1.xlsx",
        )

    def test_splits_long_replies_before_sending(self):
        text = "a" * (MAX_MESSAGE_LENGTH * 2 + 1)

        chunks = split_message(text)

        self.assertEqual([len(chunk) for chunk in chunks], [4000, 4000, 1])

    def test_get_updates_uses_offset_and_long_polling(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": []}
        session = Mock()
        session.get.return_value = response

        updates = get_updates("secret-token", offset=12, session=session)

        self.assertEqual(updates, [])
        request = session.get.call_args
        self.assertEqual(request.kwargs["params"]["offset"], 12)
        self.assertGreater(request.kwargs["timeout"], 25)

    def test_send_message_sends_every_chunk(self):
        response = Mock()
        response.json.return_value = {"ok": True, "result": {}}
        session = Mock()
        session.post.return_value = response

        send_message(
            "secret-token",
            42,
            "a" * (MAX_MESSAGE_LENGTH + 1),
            session=session,
        )

        self.assertEqual(session.post.call_count, 2)

    def test_request_error_does_not_put_the_token_in_the_message(self):
        session = Mock()
        session.get.side_effect = requests.ConnectionError("network down")

        with self.assertRaises(TelegramError) as result:
            get_updates("very-secret-token", session=session)

        self.assertNotIn("very-secret-token", str(result.exception))


if __name__ == "__main__":
    unittest.main()
