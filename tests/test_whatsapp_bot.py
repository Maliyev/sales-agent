import sys
import unittest
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from document_reader import DocumentReadError, build_document_user_text
from image_reader import ImageReadError, build_image_user_text
from whatsapp_bot import handle_incoming_message
from whatsapp_client import WhatsAppError
from whatsapp_webhook import (
    WhatsAppDocumentMessage,
    WhatsAppImageMessage,
    WhatsAppTextMessage,
)


class WhatsAppBotTests(unittest.TestCase):
    def setUp(self):
        self.message = WhatsAppTextMessage(
            message_id="wamid.123",
            sender_id="994501234567",
            text="Arduino Uno",
            phone_number_id="1242528055613330",
        )

    def test_submits_a_new_message_to_a_separate_whatsapp_session(self):
        claim = Mock(return_value=True)
        release = Mock()
        allow = Mock(return_value=True)
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            claim,
            release,
            allow,
            submit,
        )

        self.assertTrue(handled)
        claim.assert_called_once_with("wamid.123", "994501234567")
        allow.assert_called_once_with("whatsapp:994501234567")
        submit.assert_called_once_with(
            "whatsapp:994501234567",
            "Arduino Uno",
            "994501234567",
        )
        release.assert_not_called()

    def test_ignores_a_repeated_message(self):
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            Mock(return_value=False),
            Mock(),
            Mock(),
            submit,
        )

        self.assertFalse(handled)
        submit.assert_not_called()

    def test_ignores_an_event_for_another_phone_number(self):
        claim = Mock()

        handled = handle_incoming_message(
            self.message,
            "different-phone-id",
            claim,
            Mock(),
            Mock(),
            Mock(),
        )

        self.assertFalse(handled)
        claim.assert_not_called()

    def test_blocked_session_is_not_submitted(self):
        submit = Mock()

        handled = handle_incoming_message(
            self.message,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=False),
            submit,
        )

        self.assertFalse(handled)
        submit.assert_not_called()

    def test_releases_the_message_if_submission_fails(self):
        release = Mock()

        with self.assertRaisesRegex(RuntimeError, "queue failed"):
            handle_incoming_message(
                self.message,
                "1242528055613330",
                Mock(return_value=True),
                release,
                Mock(return_value=True),
                Mock(side_effect=RuntimeError("queue failed")),
            )

        release.assert_called_once_with("wamid.123")

    def test_rejects_an_invalid_incoming_message(self):
        with self.assertRaisesRegex(WhatsAppError, "invalid incoming message"):
            handle_incoming_message(
                object(),
                "1242528055613330",
                Mock(),
                Mock(),
                Mock(),
                Mock(),
            )

    def test_submits_a_document_as_the_converted_text(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="bom.xlsx",
            caption="Check these",
            phone_number_id="1242528055613330",
        )
        claim = Mock(return_value=True)
        release = Mock()
        allow = Mock(return_value=True)
        submit = Mock()
        send = Mock()
        downloads = Mock(return_value=b"data")
        readers = Mock(return_value="Component\tQty")

        handled = handle_incoming_message(
            document,
            "1242528055613330",
            claim,
            release,
            allow,
            submit,
            read_document_fn=readers,
            download_media_fn=downloads,
            send_fn=send,
        )

        self.assertTrue(handled)
        downloads.assert_called_once_with("media-9")
        readers.assert_called_once_with("bom.xlsx", b"data")
        submit.assert_called_once_with(
            "whatsapp:994501234567",
            build_document_user_text("bom.xlsx", "Component\tQty", "Check these"),
            "994501234567",
        )
        send.assert_not_called()
        release.assert_not_called()

    def test_replies_to_an_unsupported_document_without_a_download(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="scan.pdf",
            phone_number_id="1242528055613330",
        )
        submit = Mock()
        send = Mock()
        downloads = lambda media_id: self.fail("Download should not be called")

        handled = handle_incoming_message(
            document,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            submit,
            read_document_fn=lambda filename, data: "text",
            download_media_fn=downloads,
            send_fn=send,
        )

        self.assertTrue(handled)
        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn(".xlsx", send.call_args.args[1])
        submit.assert_not_called()

    def test_replies_to_an_unreadable_document(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="bom.xlsx",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        def broken_reader(filename, data):
            raise DocumentReadError("The Excel file could not be parsed.")

        handle_incoming_message(
            document,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            read_document_fn=broken_reader,
            download_media_fn=lambda media_id: b"data",
            send_fn=send,
        )

        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("oxuya bilmirəm", send.call_args.args[1])

    def test_replies_to_an_oversized_document(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="bom.xlsx",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        handle_incoming_message(
            document,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            read_document_fn=lambda filename, data: "text",
            download_media_fn=lambda media_id: b"x" * (6 * 1024 * 1024),
            send_fn=send,
        )

        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("5 MB", send.call_args.args[1])

    def test_replies_to_a_failed_document_download(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="bom.xlsx",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        def broken_downloader(media_id):
            raise WhatsAppError("WhatsApp media download failed.")

        handle_incoming_message(
            document,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            read_document_fn=lambda filename, data: "text",
            download_media_fn=broken_downloader,
            send_fn=send,
        )

        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("cavab verə bilmirəm", send.call_args.args[1])

    def test_submits_an_image_as_the_vision_description(self):
        image = WhatsAppImageMessage(
            message_id="wamid.img",
            sender_id="994501234567",
            media_id="media-5",
            mime_type="image/jpeg",
            caption="What is this?",
            phone_number_id="1242528055613330",
        )
        claim = Mock(return_value=True)
        release = Mock()
        submit = Mock()
        send = Mock()
        downloads = Mock(return_value=b"IMG")
        described = Mock(return_value="A red LED.")

        handled = handle_incoming_message(
            image,
            "1242528055613330",
            claim,
            release,
            Mock(return_value=True),
            submit,
            download_media_fn=downloads,
            describe_image_fn=described,
            send_fn=send,
        )

        self.assertTrue(handled)
        downloads.assert_called_once_with("media-5")
        described.assert_called_once_with(
            b"IMG",
            "image/jpeg",
            "whatsapp:994501234567",
        )
        submit.assert_called_once_with(
            "whatsapp:994501234567",
            build_image_user_text("A red LED.", "What is this?"),
            "994501234567",
        )
        send.assert_not_called()
        release.assert_not_called()

    def test_an_image_document_is_routed_to_the_vision_path(self):
        document = WhatsAppDocumentMessage(
            message_id="wamid.doc",
            sender_id="994501234567",
            media_id="media-9",
            filename="photo.png",
            mime_type="image/png",
            phone_number_id="1242528055613330",
        )
        submit = Mock()
        described = Mock(return_value="A resistor")

        def broken_reader(filename, data):
            self.fail("Document reader should not be called for images")

        handle_incoming_message(
            document,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            submit,
            read_document_fn=broken_reader,
            download_media_fn=lambda media_id: b"IMG",
            describe_image_fn=described,
            send_fn=Mock(),
        )

        described.assert_called_once_with(
            b"IMG",
            "image/png",
            "whatsapp:994501234567",
        )
        submit.assert_called_once_with(
            "whatsapp:994501234567",
            build_image_user_text("A resistor"),
            "994501234567",
        )

    def test_replies_when_the_image_cannot_be_described(self):
        image = WhatsAppImageMessage(
            message_id="wamid.img",
            sender_id="994501234567",
            media_id="media-5",
            mime_type="image/jpeg",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        def broken_describer(data, mime, session_id):
            raise ImageReadError("Image description failed.")

        handled = handle_incoming_message(
            image,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            download_media_fn=lambda media_id: b"IMG",
            describe_image_fn=broken_describer,
            send_fn=send,
        )

        self.assertTrue(handled)
        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("emal edə bilmirəm", send.call_args.args[1])

    def test_replies_to_an_oversized_image(self):
        image = WhatsAppImageMessage(
            message_id="wamid.img",
            sender_id="994501234567",
            media_id="media-5",
            mime_type="image/jpeg",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        handle_incoming_message(
            image,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            download_media_fn=lambda media_id: b"x" * (6 * 1024 * 1024),
            describe_image_fn=Mock(),
            send_fn=send,
        )

        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("5 MB", send.call_args.args[1])

    def test_replies_to_a_failed_image_download(self):
        image = WhatsAppImageMessage(
            message_id="wamid.img",
            sender_id="994501234567",
            media_id="media-5",
            mime_type="image/jpeg",
            phone_number_id="1242528055613330",
        )
        send = Mock()

        def broken_downloader(media_id):
            raise WhatsAppError("WhatsApp media download failed.")

        handle_incoming_message(
            image,
            "1242528055613330",
            Mock(return_value=True),
            Mock(),
            Mock(return_value=True),
            Mock(),
            download_media_fn=broken_downloader,
            describe_image_fn=Mock(),
            send_fn=send,
        )

        self.assertEqual(len(send.call_args_list), 1)
        self.assertIn("cavab verə bilmirəm", send.call_args.args[1])

    def test_raises_when_image_handlers_are_not_configured(self):
        image = WhatsAppImageMessage(
            message_id="wamid.img",
            sender_id="994501234567",
            media_id="media-5",
            mime_type="image/jpeg",
            phone_number_id="1242528055613330",
        )
        release = Mock()

        with self.assertRaisesRegex(WhatsAppError, "not configured"):
            handle_incoming_message(
                image,
                "1242528055613330",
                Mock(return_value=True),
                release,
                Mock(return_value=True),
                Mock(),
            )

        release.assert_called_once_with("wamid.img")


if __name__ == "__main__":
    unittest.main()
