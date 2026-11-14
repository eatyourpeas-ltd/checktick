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

TEMPLATE_360 = TEMPLATE_DIR / (
    "question-group-templates-360-gmc-patient-questionnaire.md"
)


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


# --- The 360° GMC patient feedback template ---


def test_360_template_structure():
    """The GMC 360 instrument: two rater populations in one survey,
    separated by the rater_role category, with typed/required follow-ups."""
    metadata, markdown = _split_frontmatter(TEMPLATE_360.read_text(encoding="utf-8"))
    assert metadata["title"] == "360° GMC Patient Feedback Questionnaire"
    parsed = parse_bulk_markdown_with_collections(markdown)
    groups = parsed["groups"]

    # Rater populations: patient and colleague sections separated by
    # required_categories rules on the rater_role dimension.
    assert parsed.get("categories"), "template must define CATEGORIES"
    dims = {d["name"]: d for d in parsed["categories"]["dimensions"]}
    assert "rater_role" in dims
    assert set(dims["rater_role"]["allowed_values"]) == {
        "self",
        "clinician",
        "patient",
    }

    rules = parsed["categories_group_rules"]
    patient_groups = [
        name
        for name, r in rules.items()
        if any(d == "rater_role" and v == "patient" for d, v in r)
    ]
    clinician_groups = [
        name
        for name, r in rules.items()
        if any(d == "rater_role" and v == "clinician" for d, v in r)
    ]
    assert patient_groups, "no patient-facing sections"
    assert clinician_groups, "no colleague-facing sections"

    # Patient experience grid: 9 rows on a 1-5 scale with NA option.
    patient_grid = next(
        q
        for g in groups
        for q in g["questions"]
        if q["final_type"] == "grid"
        and "Being polite" in [r["title"] for r in q.get("grid_rows", [])]
    )
    assert len(patient_grid["grid_rows"]) == 9
    scale = patient_grid["final_options"]["scale"]
    assert scale["type"] == "number-scale"
    assert scale["min"] == 1
    assert scale["max"] == 5
    assert scale["na_label"] == "Does not apply"

    # Colleague behaviours grid: 19 rows, categories scale with Don't know.
    colleague_grid = next(
        q
        for g in groups
        for q in g["questions"]
        if q["final_type"] == "grid"
        and "Clinical Knowledge" in [r["title"] for r in q.get("grid_rows", [])]
    )
    assert len(colleague_grid["grid_rows"]) == 18
    cscale = colleague_grid["final_options"]["scale"]
    assert cscale["type"] == "categories"
    assert "Don't know" in str(cscale)

    # Typed follow-up: the professional role question's Doctor option
    # carries a required Yes/No follow-up (training grade).
    role_q = next(
        q
        for g in groups
        for q in g["questions"]
        if "professional role" in q["title"].lower()
    )
    doctor = next(o for o in role_q["final_options"] if o.get("label") == "Doctor")
    assert doctor["followup_text"]["type"] == "yesno"
    assert doctor["followup_text"]["required"] is True
    assert doctor["followup_text"]["label"] == (
        "If you are a doctor, are you in a training grade?"
    )


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
            name="360° GMC Patient Feedback Questionnaire",
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

        # Template import takes the FIRST group — the patient introduction
        # section of the GMC instrument.
        group = QuestionGroup.objects.get(imported_from=template)
        assert group.name == "Patient Introduction"
        survey_questions = SurveyQuestion.objects.filter(survey=survey, group=group)
        stems = survey_questions.filter(type=SurveyQuestion.Types.GRID).order_by(
            "order"
        )
        assert stems.count() == 1

        rows = SurveyQuestion.objects.filter(
            survey=survey, group=group, parent__isnull=False
        ).order_by("order", "id")
        # The 9-row patient experience grid.
        assert rows.count() == 9
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
