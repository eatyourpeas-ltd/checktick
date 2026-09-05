"""
Tests for the document-import LLM prompt loading from documentation.

Ensures load_doc_import_prompt_from_docs() reads the prompt from the
llm-security.md documentation file and that the "treat document as data"
injection-deterrent instruction is present.
"""

from pathlib import Path

from django.conf import settings

from checktick_app.surveys.llm_client import (
    _FALLBACK_DOC_IMPORT_PROMPT,
    load_doc_import_prompt_from_docs,
)

START_MARKER = "<!-- DOC_IMPORT_PROMPT_START -->"
END_MARKER = "<!-- DOC_IMPORT_PROMPT_END -->"


class TestDocImportPromptLoading:
    """Test suite for document-import prompt loading from documentation."""

    def test_load_doc_import_prompt_from_docs_succeeds(self):
        prompt = load_doc_import_prompt_from_docs()

        assert prompt, "Document-import prompt should not be empty"
        assert isinstance(prompt, str)

    def test_prompt_contains_untrusted_data_instruction(self):
        """The prompt must treat the document as data, never instructions."""
        prompt = load_doc_import_prompt_from_docs()

        assert "untrusted" in prompt.lower(), (
            "Prompt must describe the document as untrusted data "
            "(injection deterrent)"
        )
        assert "ignore" in prompt.lower(), (
            "Prompt must instruct the model to ignore instructions "
            "found inside the document"
        )

    def test_prompt_contains_fidelity_instructions(self):
        prompt = load_doc_import_prompt_from_docs()

        assert "preserve" in prompt.lower(), "Prompt must require preserving wording"
        assert "infer" in prompt.lower(), "Prompt must require inferring types"
        assert "markdown" in prompt.lower(), "Prompt must require markdown output"

    def test_prompt_accepts_reasoning_but_requires_final_block(self):
        """Reasoning models (e.g. qwen) think before answering — forbidding it
        outright causes meta-anxiety loops. The prompt must allow working
        through the conversion but require the markdown block at the end."""
        prompt = load_doc_import_prompt_from_docs()

        assert "must end with" in prompt.lower()
        assert "code block" in prompt.lower()
        assert "do not show" not in prompt.lower()

    def test_prompt_removes_ambiguity_to_avoid_loops(self):
        """The model loops when the format leaves decisions open — the prompt
        must demand immediate output and forbid optional extras."""
        prompt = load_doc_import_prompt_from_docs()

        assert "immediately" in prompt.lower()
        assert "do not add description lines" in prompt.lower()
        assert "simplest option" in prompt.lower()

    def test_prompt_teaches_format_with_worked_example(self):
        """Small/medium models follow worked examples, so the prompt must
        contain one — guard against it being removed or diluted."""
        prompt = load_doc_import_prompt_from_docs()

        assert "EXAMPLE CONVERSION" in prompt
        # The example must show questions with types, ids, and a likert mapping
        assert "## Tell us your name" in prompt
        assert "(text)" in prompt
        assert "(likert number)" in prompt
        assert "min: 1" in prompt
        assert "# About you {about-you}" in prompt
        # Numbered items must be described as questions
        assert "numbered or bulleted item" in prompt.lower()

    def test_fallback_prompt_exists(self):
        assert _FALLBACK_DOC_IMPORT_PROMPT
        assert isinstance(_FALLBACK_DOC_IMPORT_PROMPT, str)
        assert "untrusted" in _FALLBACK_DOC_IMPORT_PROMPT.lower()

    def test_documentation_contains_markers(self):
        docs_path = Path(settings.BASE_DIR) / "docs" / "llm-security.md"
        content = docs_path.read_text(encoding="utf-8")

        assert START_MARKER in content
        assert END_MARKER in content

        start_idx = content.find(START_MARKER)
        end_idx = content.find(END_MARKER)
        assert start_idx < end_idx, "START marker must come before END marker"

        between = content[start_idx + len(START_MARKER) : end_idx].strip()
        assert between, "There should be content between the markers"

    def test_loaded_prompt_matches_doc_content(self):
        docs_path = Path(settings.BASE_DIR) / "docs" / "llm-security.md"
        content = docs_path.read_text(encoding="utf-8")

        start_idx = content.find(START_MARKER)
        end_idx = content.find(END_MARKER)
        expected = content[start_idx + len(START_MARKER) : end_idx].strip()

        # Mirror the loader's fence-stripping cleanup
        if expected.startswith("```"):
            lines = expected.split("\n")
            if lines[-1].strip() == "```":
                expected = "\n".join(lines[1:-1])

        assert load_doc_import_prompt_from_docs() == expected

    def test_fallback_used_when_file_missing(self, tmp_path, monkeypatch):
        fake_base_dir = tmp_path / "fake_checktick_app"
        fake_base_dir.mkdir()
        monkeypatch.setattr(settings, "BASE_DIR", fake_base_dir)

        assert load_doc_import_prompt_from_docs() == _FALLBACK_DOC_IMPORT_PROMPT

    def test_fallback_used_when_markers_missing(self, tmp_path, monkeypatch):
        fake_base_dir = tmp_path / "fake_checktick_app"
        fake_docs_dir = fake_base_dir / "docs"
        fake_docs_dir.mkdir(parents=True)
        (fake_docs_dir / "llm-security.md").write_text(
            "# AI Security\n\nNo markers here."
        )
        monkeypatch.setattr(settings, "BASE_DIR", fake_base_dir)

        assert load_doc_import_prompt_from_docs() == _FALLBACK_DOC_IMPORT_PROMPT
