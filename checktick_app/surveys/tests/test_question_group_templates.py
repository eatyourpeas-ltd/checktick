"""Question bank template files — validation, grid battery, and import.

Guards the markdown files in ``docs/question-group-templates/`` the same
way ``sync_global_question_group_templates`` does (frontmatter + parse),
so a broken template fails CI instead of failing the deployment sync.

The 360° Colleague Feedback Battery is the first template to use the
grid of sub-questions question type — its battery sections are grids
whose rows share one scale, which is what 360° forms call "tick one box
on each line".
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth.models import User
from django.urls import reverse
import pytest
import yaml

from checktick_app.surveys.markdown_import import parse_bulk_markdown_with_collections
from checktick_app.surveys.models import (
    PublishedQuestionGroup,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "docs"
    / "question-group-templates"
)

TEMPLATE_360 = TEMPLATE_DIR / "question-group-templates-360-assessment.md"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


def _template_files():
    """Every template file except the index (same rule as the sync command)."""
    return sorted(
        f
        for f in TEMPLATE_DIR.glob("*.md")
        if f.stem != "question-group-templates-index"
    )


def _split_frontmatter(content: str):
    """Split a template file the same way the sync command does."""
    assert content.startswith("---\n"), "template must start with YAML frontmatter"
    parts = content.split("---\n", 2)
    assert len(parts) >= 3, "template must close its frontmatter"
    return yaml.safe_load(parts[1]), parts[2].strip()


# --- All template files: frontmatter + parse (the sync command's checks) ---


def test_template_directory_exists():
    assert TEMPLATE_DIR.is_dir(), f"missing template dir: {TEMPLATE_DIR}"


def test_all_global_templates_have_frontmatter_and_parse():
    files = _template_files()
    assert len(files) >= 2, "expected at least the PHQ-9 and 360 templates"
    for f in files:
        content = f.read_text(encoding="utf-8")
        metadata, markdown = _split_frontmatter(content)
        assert isinstance(metadata, dict), f"{f.name}: invalid YAML frontmatter"
        for field in ("title", "description", "attribution"):
            assert field in metadata, f"{f.name}: missing required field {field}"
        # Same parse the sync command runs before creating the record.
        parsed = parse_bulk_markdown_with_collections(markdown)
        assert parsed and parsed.get("groups"), f"{f.name}: no groups parsed"
        questions = [q for g in parsed["groups"] for q in g.get("questions", [])]
        assert questions, f"{f.name}: no questions parsed"


# --- The 360° battery template ---


def test_360_template_grid_structure():
    metadata, markdown = _split_frontmatter(TEMPLATE_360.read_text(encoding="utf-8"))
    assert metadata["title"] == "360° Colleague Feedback Battery"
    parsed = parse_bulk_markdown_with_collections(markdown)
    groups = parsed["groups"]
    # Template import takes the first group — the battery is one section.
    assert len(groups) == 1
    questions = groups[0]["questions"]

    grids = [q for q in questions if q["final_type"] == "grid"]
    assert len(grids) == 3, "expected the 3 rating grids"
    for q in grids:
        assert q["required"] is False, "stems are never required (rows carry it)"
        scale = q["final_options"]["scale"]
        assert scale["type"] == "number-scale"
        assert scale["min"] == 1
        assert scale["max"] == 5
        assert scale["render"] == "radio"
        assert scale["na_label"] == "Does not apply"
        # The `*` on each stem marks every row required.
        assert q["grid_rows"], "grid has no rows"
        assert all(r["required"] for r in q["grid_rows"])

    # The user's 360° example items are in the communication grid;
    # courtesy sits in the professionalism grid.
    by_ref = {q["ref"]: q for q in questions}
    comm_rows = [r["title"] for r in by_ref["quality-communication"]["grid_rows"]]
    assert {
        "Listening to you",
        "Making you feel at ease",
        "Explaining things clearly",
    } <= set(comm_rows)
    prof_rows = [r["title"] for r in by_ref["quality-professionalism"]["grid_rows"]]
    assert "Being polite and courteous" in prof_rows

    # Supporting questions around the grids.
    types = [q["final_type"] for q in questions]
    assert types.count("mc_single") == 2
    assert types.count("long_text") == 2
    assert types.count("likert") == 1


# --- Import through the question bank view ---


@pytest.mark.django_db
class Test360TemplateImport:
    def test_import_creates_group_grids_and_rows(self, client):
        user = User.objects.create_user(username="t360", password="x")
        survey = Survey.objects.create(
            owner=user,
            name="360 Import",
            slug=f"t360-{user.id}",
        )
        _, markdown = _split_frontmatter(TEMPLATE_360.read_text(encoding="utf-8"))
        template = PublishedQuestionGroup.objects.create(
            name="360° Colleague Feedback Battery",
            description="test copy",
            publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
            publisher=user,
            markdown=markdown,
        )

        client.force_login(user)
        res = client.post(
            reverse(
                "surveys:published_template_import",
                kwargs={"template_id": template.id, "slug": survey.slug},
            )
        )
        assert res.status_code == 302

        group = QuestionGroup.objects.get(imported_from=template)
        survey_questions = SurveyQuestion.objects.filter(survey=survey, group=group)
        stems = survey_questions.filter(type=SurveyQuestion.Types.GRID).order_by(
            "order"
        )
        assert stems.count() == 3

        rows = SurveyQuestion.objects.filter(
            survey=survey, group=group, parent__isnull=False
        ).order_by("order", "id")
        # 4 + 4 + 5 grid rows from the battery.
        assert rows.count() == 13
        for row in rows:
            assert row.parent_id is not None
            assert row.type == SurveyQuestion.Types.LIKERT
            # Rows carry their own copy of the shared scale.
            assert row.options[0]["min"] == 1
            assert row.options[0]["max"] == 5
            assert row.options[0]["na_label"] == "Does not apply"
            assert row.required is True
        for stem in stems:
            assert stem.required is False

        # Rows sort after their stem.
        for stem in stems:
            stem_rows = stem.subquestions.all()
            assert all(r.order > stem.order for r in stem_rows)
