"""Regression tests for the August 2026 security review documentation findings.

* F5  (Info) — ``email_utils.py`` must document the convention that
  cross-user email content goes through ``.md`` templates (autoescaped)
  rather than f-string interpolation, so future contributors do not
  reintroduce an F2-class HTML-injection finding.
* F15 (Low) — ``docs/llm-security.md`` must not overclaim instruction-based
  prompt-injection defences as a security control. The real boundary is
  output validation + manual review + no tool access; role enforcement in
  the system prompt is a deterrent only.
"""

from pathlib import Path

from django.conf import settings

import checktick_app.core.email_utils as email_utils

REPO_ROOT = Path(settings.BASE_DIR).resolve()


# ---------------------------------------------------------------------------
# F5 — email_utils convention note
# ---------------------------------------------------------------------------


def test_email_utils_documents_f_string_convention():
    """F5: the ``email_utils`` module docstring must warn contributors that
    cross-user email content must go through ``.md`` templates (which
    autoescape) rather than f-string interpolation.

    The split between escaped ``.md``-template paths (safe) and unescaped
    f-string paths (fragile) is the structural pattern that produced F2.
    Documenting the convention here is the recommended remediation for F5.
    """
    docstring = email_utils.__doc__ or ""
    assert (
        "template" in docstring.lower()
    ), "email_utils module docstring must reference .md templates"
    assert (
        "autoescape" in docstring.lower()
        or "auto-escape" in docstring.lower()
        or "autoescaping" in docstring.lower()
    ), "email_utils module docstring must mention autoescaping"
    # Must explicitly call out the f-string risk so the F2 class is not
    # reintroduced by a future contributor.
    assert "f-string" in docstring.lower() or "f string" in docstring.lower(), (
        "email_utils module docstring must warn about f-string interpolation "
        "of cross-user content (F5/F2 class)"
    )


# ---------------------------------------------------------------------------
# F15 — llm-security.md must not overclaim prompt-injection defence
# ---------------------------------------------------------------------------


def test_llm_security_docs_do_not_overclaim_instruction_defence():
    """F15: ``docs/llm-security.md`` §4 must frame instruction-based role
    enforcement as a *deterrent*, not a security *control*, and must state
    that the real boundary is output validation + manual review + no tool
    access.

    Before the fix the docs claimed "Strict role enforcement" as a
    protection mechanism and implied the model "reliably" refuses injection
    — which is misleading for a DSPT audit record.
    """
    llm_security_path = REPO_ROOT / "docs" / "llm-security.md"
    text = llm_security_path.read_text(encoding="utf-8")

    # The docs must explicitly position output validation as the boundary.
    assert (
        "output validation" in text.lower() or "output sanit" in text.lower()
    ), "llm-security.md must state that output validation is the security boundary"
    # The docs must NOT claim instruction-based enforcement is a control.
    # The old framing was "Strict role enforcement" as a protection mechanism.
    assert "strict role enforcement" not in text.lower(), (
        "llm-security.md must not overclaim 'strict role enforcement' as a "
        "protection mechanism (F15)"
    )
    # The docs must clarify instruction-based enforcement is a deterrent.
    assert "deterrent" in text.lower(), (
        "llm-security.md must frame instruction-based role enforcement as a "
        "deterrent, not a control (F15)"
    )
