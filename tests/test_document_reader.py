import datetime
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from document_reader import (
    MAX_EXTRACTED_CHARS,
    DocumentReadError,
    build_document_user_text,
    extract_document_text,
    is_supported_document,
)
from openpyxl import Workbook


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def build_xlsx(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in sheets.items():
        sheet = workbook.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_docx(body_xml):
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{WORD_NAMESPACE}">'
        f"<w:body>{body_xml}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def word_paragraph(text):
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def word_table(rows):
    body = ""
    for row in rows:
        cells = "".join(
            "<w:tc>" + word_paragraph(cell) + "</w:tc>" for cell in row
        )
        body += f"<w:tr>{cells}</w:tr>"
    return f"<w:tbl>{body}</w:tbl>"


class DocumentReaderTests(unittest.TestCase):
    def test_reads_an_excel_sheet_as_tab_separated_rows(self):
        data = build_xlsx(
            {
                "Sheet": [
                    ["Component", "Qty", None],
                    ["L7805CV", 5, ""],
                    ["C1", 2.5, ""],
                    [None, None, None],
                ]
            }
        )

        text = extract_document_text("bom.xlsx", data)

        self.assertIn("Component\tQty", text)
        self.assertIn("L7805CV\t5", text)
        self.assertIn("C1\t2.5", text)

    def test_reads_every_excel_sheet_with_a_header(self):
        data = build_xlsx(
            {
                "Stock": [["Resistor", 10]],
                "Prices": [["Capacitor", "0.02"]],
            }
        )

        text = extract_document_text("bom.xlsx", data)

        self.assertIn("--- Sheet: Stock ---", text)
        self.assertIn("--- Sheet: Prices ---", text)
        stock_index = text.index("--- Sheet: Stock ---")
        prices_index = text.index("--- Sheet: Prices ---")
        self.assertLess(stock_index, prices_index)

    def test_formats_excel_booleans_floats_and_dates(self):
        data = build_xlsx(
            {
                "Sheet": [
                    [
                        True,
                        False,
                        2.0,
                        datetime.datetime(2026, 1, 2, 3, 4),
                    ]
                ]
            }
        )

        text = extract_document_text("bom.xlsx", data)

        self.assertIn("TRUE\tFALSE\t2\t2026-01-02 03:04:00", text)

    def test_collapses_line_breaks_inside_excel_cells(self):
        data = build_xlsx({"Sheet": [["line one\nline two"]]})

        text = extract_document_text("bom.xlsx", data)

        self.assertIn("line one line two", text)
        self.assertNotIn("\nline", text.replace("line one line two", ""))

    def test_reads_word_paragraphs_and_tables_in_order(self):
        body = (
            word_paragraph("Header line")
            + word_table([["Component", "Qty"], ["L7805CV", "5"]])
            + word_paragraph("Footer line")
        )

        text = extract_document_text("bom.docx", build_docx(body))

        self.assertLess(
            text.index("Header line"),
            text.index("Component\tQty"),
        )
        self.assertLess(
            text.index("Component\tQty"),
            text.index("L7805CV\t5"),
        )
        self.assertLess(
            text.index("L7805CV\t5"),
            text.index("Footer line"),
        )

    def test_keeps_tabs_and_line_breaks_in_word_paragraphs(self):
        body = (
            "<w:p><w:r><w:t>a</w:t></w:r><w:r><w:tab/></w:r>"
            "<w:r><w:t>b</w:t></w:r><w:r><w:br/></w:r>"
            "<w:r><w:t>c</w:t></w:r></w:p>"
        )

        text = extract_document_text("bom.docx", build_docx(body))

        self.assertIn("a\tb\nc", text)

    def test_reads_word_content_controls(self):
        body = (
            "<w:sdt><w:sdtPr><w:alias w:val=\"block\"/></w:sdtPr>"
            "<w:sdtContent>" + word_paragraph("Inside control") + "</w:sdtContent></w:sdt>"
        )

        text = extract_document_text("bom.docx", build_docx(body))

        self.assertIn("Inside control", text)

    def test_rejects_unsupported_document_types(self):
        for filename in ("scan.pdf", "legacy.doc", "legacy.xls", "archive"):
            with self.subTest(filename=filename):
                with self.assertRaises(DocumentReadError):
                    extract_document_text(filename, b"some data")

    def test_rejects_corrupt_or_empty_data(self):
        with self.assertRaises(DocumentReadError):
            extract_document_text("bom.xlsx", b"not a zip file")
        with self.assertRaises(DocumentReadError):
            extract_document_text("bom.docx", b"\x00\x01\x02")
        with self.assertRaises(DocumentReadError):
            extract_document_text("bom.xlsx", b"")

    def test_rejects_documents_without_text_content(self):
        with self.assertRaisesRegex(DocumentReadError, "no text content"):
            extract_document_text("bom.xlsx", build_xlsx({"Sheet": [[None]]}))
        with self.assertRaisesRegex(DocumentReadError, "no text content"):
            extract_document_text("bom.docx", build_docx(""))

    def test_truncates_a_very_long_document(self):
        data = build_xlsx(
            {"Sheet": [["x" * 1000] for _ in range(MAX_EXTRACTED_CHARS // 500 + 10)]}
        )

        text = extract_document_text("bom.xlsx", data)

        self.assertLess(len(text), MAX_EXTRACTED_CHARS + 200)
        self.assertTrue(text.endswith("[The document content was truncated]"))

    def test_reports_the_supported_document_extensions(self):
        self.assertTrue(is_supported_document("bom.xlsx"))
        self.assertTrue(is_supported_document("BOM.DOCX"))
        self.assertFalse(is_supported_document("bom.pdf"))
        self.assertFalse(is_supported_document("bom"))
        self.assertFalse(is_supported_document(None))

    def test_builds_the_model_wrapping_with_a_caption(self):
        text = build_document_user_text(
            "bom.xlsx",
            "Component\tQty",
            caption="Check these please",
        )

        self.assertIn('The customer sent a document "bom.xlsx".', text)
        self.assertIn("--- Converted document content ---", text)
        self.assertIn("Component\tQty", text)
        self.assertIn("--- End of document content ---", text)
        self.assertIn(
            "Customer's message with the document: Check these please",
            text,
        )

    def test_builds_the_model_wrapping_without_a_caption(self):
        text = build_document_user_text("bom.xlsx", "Component\tQty")

        self.assertNotIn("Customer's message", text)


if __name__ == "__main__":
    unittest.main()
