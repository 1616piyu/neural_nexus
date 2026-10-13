import pytest

from pypdf import PdfWriter

from services.document_service import (
    validate_document,
    extract_document_text,
    clean_text,
    chunk_text,
)


def test_validate_supported_files():
    assert validate_document("notes.txt") is True
    assert validate_document("report.PDF") is True


def test_reject_unsupported_extension():
    with pytest.raises(
        ValueError,
        match="Only PDF, DOCX, and TXT files are supported",
    ):
        validate_document("script.exe")


def test_reject_empty_filename():
    with pytest.raises(ValueError, match="filename"):
        validate_document("")


def test_reject_empty_file_size():
    with pytest.raises(ValueError, match="empty"):
        validate_document("notes.txt", 0)


def test_reject_file_over_size_limit():
    with pytest.raises(ValueError, match="10 MB"):
        validate_document("notes.txt", 10 * 1024 * 1024 + 1)


def test_extract_txt_file(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("Neural Nexus document processing.", encoding="utf-8")

    text = extract_document_text(file_path)

    assert text == "Neural Nexus document processing."


def test_reject_missing_document(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        extract_document_text(tmp_path / "missing.txt")


def test_reject_empty_text_file(tmp_path):
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="empty"):
        extract_document_text(file_path)


def test_clean_text():
    result = clean_text("  Hello   world \r\n\r\n Next line  ")

    assert result == "Hello world\n\nNext line"


def test_chunk_text_with_overlap():
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_text(text, chunk_size=10, overlap=3)

    assert chunks == [
        "abcdefghij",
        "hijklmnopq",
        "opqrstuvwx",
        "vwxyz",
    ]


def test_chunk_empty_text():
    assert chunk_text("   ") == []


def test_chunk_invalid_parameters():
    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=0)

    with pytest.raises(ValueError):
        chunk_text("hello", chunk_size=10, overlap=10)


def test_extract_pdf_text(tmp_path):
    pdf_path = tmp_path / "sample.pdf"

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)

    with pdf_path.open("wb") as pdf_file:
        writer.write(pdf_file)

    with pytest.raises(ValueError, match="No readable text"):
        extract_document_text(pdf_path)