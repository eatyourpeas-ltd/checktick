"""Tests for document text extraction and upload validation.

Covers the "Import from document" feature's first stage: turning an uploaded
.docx / .txt / .md file into plain text, with hard guards against files
masquerading as those types (magic-byte checks, zip-bomb caps, binary text).
"""

import io
import zipfile

from django.test import override_settings
import pytest

from checktick_app.surveys.doc_extract import (
    DocImportError,
    extract_text,
    truncate_for_llm,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _paragraph(text: str) -> str:
    return f'<w:p xmlns:w="{W_NS}"><w:r><w:t>{text}</w:t></w:r></w:p>'


def _table(rows: list[list[str]]) -> str:
    trs = []
    for row in rows:
        tcs = "".join(
            f'<w:tc><w:p xmlns:w="{W_NS}"><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>'
            for cell in row
        )
        trs.append(f'<w:tr xmlns:w="{W_NS}">{tcs}</w:tr>')
    return f'<w:tbl xmlns:w="{W_NS}">{"".join(trs)}</w:tbl>'


def build_docx(body_xml: str, *, include_document_xml: bool = True) -> bytes:
    """Build a minimal in-memory .docx (ZIP) with the given document body."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("_rels/.rels", "<Relationships/>")
        if include_document_xml:
            zf.writestr(
                "word/document.xml",
                f'<?xml version="1.0"?>'
                f'<w:document xmlns:w="{W_NS}"><w:body>{body_xml}</w:body>'
                f"</w:document>",
            )
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_docx_paragraphs_extracted_in_order():
    data = build_docx(
        _paragraph("Patient experience survey")
        + _paragraph("How would you rate your visit?")
    )
    text = extract_text("survey.docx", data)
    assert "Patient experience survey" in text
    assert "How would you rate your visit?" in text
    assert text.index("Patient experience") < text.index("How would you rate")


def test_docx_table_cells_extracted_in_order():
    data = build_docx(
        _paragraph("Section one")
        + _table([["Question", "Type"], ["Overall rating", "likert"]])
    )
    text = extract_text("survey.docx", data)
    assert "Section one" in text
    assert "Overall rating" in text
    assert text.index("Question") < text.index("Overall rating")


def test_docx_runs_split_across_elements_are_joined():
    # Words split across runs must not gain or lose spaces.
    data = build_docx(
        f'<w:p xmlns:w="{W_NS}"><w:r><w:t>Over</w:t></w:r>'
        f"<w:r><w:t>all rating</w:t></w:r></w:p>"
    )
    text = extract_text("survey.docx", data)
    assert "Overall rating" in text


def test_docx_blank_runs_are_collapsed():
    data = build_docx(
        _paragraph("One")
        + _paragraph("")
        + _paragraph("")
        + _paragraph("")
        + _paragraph("Two")
    )
    text = extract_text("survey.docx", data)
    lines = [line for line in text.splitlines()]
    assert "One" in lines
    assert "Two" in lines
    # No more than one consecutive blank line survives.
    for i in range(1, len(lines)):
        assert not (lines[i] == "" and lines[i - 1] == "")


def test_txt_upload_extracts_text():
    text = extract_text("survey.txt", "## Question one\n(text)\n".encode("utf-8"))
    assert "## Question one" in text


def test_md_upload_extracts_text_and_strips_bom():
    text = extract_text("notes.md", "\ufeff# Title\n".encode("utf-8"))
    assert text.startswith("# Title")


# ---------------------------------------------------------------------------
# Masquerading / malformed files
# ---------------------------------------------------------------------------


def test_legacy_doc_ole2_file_rejected_with_guidance():
    # Real .doc files start with the OLE2 compound-document magic.
    ole2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
    with pytest.raises(DocImportError) as excinfo:
        extract_text("survey.doc", ole2)
    assert ".docx" in str(excinfo.value)


def test_docx_extension_with_non_zip_bytes_rejected():
    with pytest.raises(DocImportError):
        extract_text("fake.docx", b"this is not a zip file at all")


def test_docx_zip_without_document_xml_rejected():
    data = build_docx("", include_document_xml=False)
    with pytest.raises(DocImportError):
        extract_text("no-doc.docx", data)


def test_truncated_zip_rejected():
    data = build_docx(_paragraph("hello"))
    with pytest.raises(DocImportError):
        extract_text("truncated.docx", data[: len(data) // 2])


def test_txt_with_binary_content_rejected():
    with pytest.raises(DocImportError):
        extract_text("binary.txt", b"ok\x00\x01\x02binary")


def test_invalid_utf8_text_rejected():
    with pytest.raises(DocImportError):
        extract_text("bad.txt", b"\xff\xfe\xfa\x01")


def test_disallowed_extension_rejected():
    with pytest.raises(DocImportError):
        extract_text("scan.pdf", b"%PDF-1.4 fake")
    with pytest.raises(DocImportError):
        extract_text("prog.exe", b"MZ\x90\x00")


def test_docx_with_dtd_entities_rejected():
    # Internal entity declarations enable billion-laughs expansion at parse
    # time; the XML is rejected outright rather than parsed.
    evil = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE lolz [<!ENTITY lol "lol">]>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{_paragraph("&lol;")}</w:body>'
        "</w:document>"
    )
    data = build_docx("", include_document_xml=False)
    buf = io.BytesIO(data)
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("word/document.xml", evil)
    with pytest.raises(DocImportError):
        extract_text("evil.docx", buf.getvalue())


def test_docx_with_no_extractable_text_rejected():
    data = build_docx("")
    with pytest.raises(DocImportError):
        extract_text("empty.docx", data)


# ---------------------------------------------------------------------------
# Resource caps
# ---------------------------------------------------------------------------


@override_settings(LLM_DOC_IMPORT_MAX_BYTES=100)
def test_oversized_upload_rejected():
    with pytest.raises(DocImportError):
        extract_text("big.txt", b"a" * 101)


@override_settings(LLM_DOC_IMPORT_MAX_UNCOMPRESSED_BYTES=1000)
def test_zip_bomb_uncompressed_size_cap():
    # Highly compressible content: tiny on disk, huge uncompressed.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/junk.bin", "0" * 100_000)
    with pytest.raises(DocImportError):
        extract_text("bomb.docx", buf.getvalue())


@override_settings(LLM_DOC_IMPORT_MAX_ZIP_ENTRIES=2)
def test_zip_entry_count_cap():
    data = build_docx(_paragraph("hi"))
    # build_docx writes 3 entries; cap of 2 must reject it.
    with pytest.raises(DocImportError):
        extract_text("many.docx", data)


# ---------------------------------------------------------------------------
# Truncation for the LLM
# ---------------------------------------------------------------------------


def test_truncate_under_limit_is_noop():
    text = "line one\nline two"
    out, truncated = truncate_for_llm(text, max_chars=1000)
    assert out == text
    assert truncated is False


def test_truncate_cuts_at_line_boundary_and_flags():
    text = "\n".join(f"line {i} with some content" for i in range(100))
    out, truncated = truncate_for_llm(text, max_chars=100)
    assert truncated is True
    assert len(out) <= 100
    assert out.endswith("content") or out.endswith("\n")
    assert "\nline 0" in "\n" + out  # early lines preserved
