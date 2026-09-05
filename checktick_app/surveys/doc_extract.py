"""Document text extraction and upload validation for "Import from document".

This module is the first stage of the document-import pipeline: it turns an
uploaded ``.docx`` / ``.txt`` / ``.md`` file into plain text for the LLM
conversion step. It deliberately uses only the standard library — the ZIP and
XML parsing surfaces are small, auditable, and guarded here rather than
trusted to a third-party parser.

Security posture (see docs/llm-security.md once the feature ships):

* The browser-supplied content type is ignored entirely; the file extension
  selects a parser and **magic bytes verify it** (files masquerading as
  ``.docx`` or text are rejected).
* ZIP archives are bounded by entry count and total uncompressed size before
  any extraction work (zip-bomb guard). ``defusedxml.ElementTree`` is used
  for parsing, which refuses entity expansion and does not fetch external
  entities.
* Legacy binary ``.doc`` (OLE2) is rejected with guidance to save as
  ``.docx`` — no OLE parser is attempted.
* Nothing here logs or persists document content.
"""

from __future__ import annotations

import io
from pathlib import Path
import zipfile

import defusedxml.ElementTree as ET
from django.conf import settings

# OOXML main document namespace (wordprocessingml).
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ALLOWED_EXTENSIONS = {".docx", ".txt", ".md"}
_DOC_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

_DEFAULT_MAX_BYTES = 2 * 1024 * 1024
_DEFAULT_MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
_DEFAULT_MAX_ZIP_ENTRIES = 500
_DEFAULT_MAX_CHARS = 20_000


class DocImportError(Exception):
    """Raised for any rejected upload.

    Carries a stable ``code``; the user-facing text always comes from
    :data:`MESSAGE_BY_CODE` (static strings) so no exception content is
    ever reflected into an HTTP response.
    """

    def __init__(self, code: str):
        self.code = code
        super().__init__(MESSAGE_BY_CODE.get(code, code))


MESSAGE_BY_CODE = {
    "legacy_doc": "Legacy .doc files are not supported. Please open the "
    "document in Word and save it as .docx, or paste the text instead.",
    "unsupported_type": "Unsupported file type. Upload a .docx file, or "
    "paste the text (.txt and .md are also accepted).",
    "too_large": "File is too large.",
    "invalid_docx": "This file is not a valid .docx document. Re-save it "
    "from Word, or paste the text instead.",
    "too_many_entries": "This document contains too many internal entries "
    "and cannot be processed.",
    "uncompressed_too_large": "This document is too large to process. Split "
    "it into smaller documents or paste the relevant text.",
    "no_document_body": "This file does not contain a Word document body. "
    "Re-save it as .docx from Word.",
    "unreadable_docx": "This document could not be opened. It may be "
    "password-protected or corrupted.",
    "unsupported_xml": "This document contains unsupported XML constructs "
    "and cannot be processed.",
    "unparseable_docx": "This document's content could not be parsed. "
    "Re-save it from Word, or paste the text instead.",
    "no_text": "No text could be extracted from this document.",
    "not_utf8": "The file is not valid UTF-8 text. Save it as UTF-8, upload "
    "a .docx file, or paste the text instead.",
    "binary_text": "The file contains binary data and cannot be processed " "as text.",
    "empty_text": "The pasted text or file appears to be empty.",
}


def _max_bytes() -> int:
    return int(getattr(settings, "LLM_DOC_IMPORT_MAX_BYTES", _DEFAULT_MAX_BYTES))


def _max_uncompressed() -> int:
    return int(
        getattr(
            settings,
            "LLM_DOC_IMPORT_MAX_UNCOMPRESSED_BYTES",
            _DEFAULT_MAX_UNCOMPRESSED_BYTES,
        )
    )


def _max_zip_entries() -> int:
    return int(
        getattr(settings, "LLM_DOC_IMPORT_MAX_ZIP_ENTRIES", _DEFAULT_MAX_ZIP_ENTRIES)
    )


def _max_chars() -> int:
    return int(getattr(settings, "LLM_DOC_IMPORT_MAX_CHARS", _DEFAULT_MAX_CHARS))


def extract_text(filename: str, data: bytes) -> str:
    """Validate an uploaded file and return its extracted plain text.

    Raises :class:`DocImportError` with a user-facing message for any
    rejected file.
    """
    ext = Path(filename or "").suffix.lower()

    if ext == ".doc" or data.startswith(_OLE2_MAGIC):
        raise DocImportError("legacy_doc")
    if ext not in ALLOWED_EXTENSIONS:
        raise DocImportError("unsupported_type")
    if len(data) > _max_bytes():
        raise DocImportError("too_large")

    if ext == ".docx":
        return _extract_docx(data)
    return _extract_plain_text(data)


# ---------------------------------------------------------------------------
# .docx (OOXML) extraction
# ---------------------------------------------------------------------------


def _extract_docx(data: bytes) -> str:
    if not data.startswith(_DOC_MAGIC):
        raise DocImportError("invalid_docx")

    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        raise DocImportError("invalid_docx") from None

    with zf:
        names = zf.namelist()
        if len(names) > _max_zip_entries():
            raise DocImportError("too_many_entries")
        try:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
        except (zipfile.BadZipFile, OSError, ValueError):
            raise DocImportError("invalid_docx") from None
        if total_uncompressed > _max_uncompressed():
            raise DocImportError("uncompressed_too_large")
        if "word/document.xml" not in names:
            raise DocImportError("no_document_body")
        try:
            document_xml = zf.read("word/document.xml")
        except (zipfile.BadZipFile, OSError, RuntimeError, KeyError):
            # RuntimeError covers password-protected archives.
            raise DocImportError("unreadable_docx") from None

    return _parse_document_xml(document_xml)


def _parse_document_xml(document_xml: bytes) -> str:
    # Entity/DOCTYPE declarations enable expansion attacks at parse time;
    # reject them before ElementTree ever sees them.
    head = document_xml[:4096].lstrip()
    if head.startswith(b"<?xml"):
        # Skip a leading XML declaration so the DOCTYPE check still sees it.
        end = head.find(b"?>")
        head = head[end + 2 :] if end != -1 else head
    if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
        raise DocImportError("unsupported_xml")

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError:
        raise DocImportError("unparseable_docx") from None

    body = root.find(f"{_W_NS}body")
    if body is None:
        raise DocImportError("unparseable_docx")

    lines: list[str] = []
    for child in body:
        if child.tag == f"{_W_NS}p":
            lines.append(_paragraph_text(child))
        elif child.tag == f"{_W_NS}tbl":
            lines.extend(_table_lines(child))

    return _clean_lines(lines)


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_W_NS}t":
            parts.append(node.text or "")
        elif node.tag == f"{_W_NS}tab":
            parts.append(" ")
        elif node.tag == f"{_W_NS}br":
            parts.append(" ")
    return "".join(parts).strip()


def _table_lines(table: ET.Element) -> list[str]:
    lines = []
    for row in table.findall(f"{_W_NS}tr"):
        cells = []
        for cell in row.findall(f"{_W_NS}tc"):
            cell_parts = [_paragraph_text(p) for p in cell.findall(f"{_W_NS}p")]
            cells.append(" ".join(part for part in cell_parts if part))
        lines.append(" | ".join(cells))
    return lines


def _clean_lines(lines: list[str]) -> str:
    cleaned: list[str] = []
    previous_blank = True  # swallow leading blanks
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        cleaned.append(line)
        previous_blank = blank
    text = "\n".join(cleaned).strip()
    if not text:
        raise DocImportError("no_text")
    return text


# ---------------------------------------------------------------------------
# Plain-text extraction (.txt / .md)
# ---------------------------------------------------------------------------


def _extract_plain_text(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DocImportError("not_utf8") from None

    if "\x00" in text:
        raise DocImportError("binary_text")

    lines = text.splitlines()
    try:
        return _clean_lines(lines)
    except DocImportError:
        raise DocImportError("empty_text") from None


# ---------------------------------------------------------------------------
# Truncation for the LLM payload
# ---------------------------------------------------------------------------


def truncate_for_llm(text: str, max_chars: int | None = None) -> tuple[str, bool]:
    """Truncate extracted text to the LLM payload cap.

    Returns ``(text, truncated)``. Cuts at a line boundary where possible so
    the LLM never sees a half-finished question.
    """
    limit = max_chars if max_chars is not None else _max_chars()
    if len(text) <= limit:
        return text, False

    cut = text.rfind("\n", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut].rstrip(), True
