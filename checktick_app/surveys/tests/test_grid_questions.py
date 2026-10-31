"""Grid of sub-questions (matrix/battery) — model + builder plumbing.

A grid is a stem with no answer of its own plus rows sharing one scale.
Rows are real SurveyQuestion rows (type likert) with ``parent`` set, so
answers stay flat (keyed by row id) and every flat consumer —
submissions, partial answers, progress, analytics, exports — works
unchanged. See docs/respondent-categories-implementation-plan.md for the
360° assessment background.
"""

from __future__ import annotations

import textwrap

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.views import (
    _annotate_question_render_sequence,
    _duplicate_question,
    _export_survey_to_markdown,
    _parse_builder_question_form,
    _prepare_question_rendering,
)

TEST_PASSWORD = "testpass123"


def _make_survey(user: User, name: str = "Grid Test") -> Survey:
    return Survey.objects.create(owner=user, name=name, slug=f"grid-{user.id}")


# --- Builder form parsing ---


def test_parse_builder_form_grid_number_scale_with_rows():
    data = {
        "text": "How good was your doctor today at each of the following?",
        "type": "grid",
        "likert_mode": "number",
        "likert_min": "1",
        "likert_max": "5",
        "likert_left_label": "Not at all good",
        "likert_right_label": "Very good",
        "grid_include_na": "on",
        "grid_na_label": "Does not apply",
        "grid_new_rows": "being polite\nmaking you feel at ease\nlistening to you",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["type"] == "grid"
    assert form_data["options"] == {
        "type": "grid",
        "row_type": "likert",
        "scale": {
            "type": "number-scale",
            "min": 1,
            "max": 5,
            "left": "Not at all good",
            "right": "Very good",
            "render": "radio",
            "na_label": "Does not apply",
        },
    }
    assert form_data["grid_new_rows"] == [
        "being polite",
        "making you feel at ease",
        "listening to you",
    ]


def test_parse_builder_form_grid_categories_scale():
    data = {
        "text": "Rate each aspect",
        "type": "grid",
        "likert_mode": "categories",
        "likert_categories": "Poor\nFair\nGood",
        "grid_new_rows": "aspect one\naspect two",
    }
    form_data = _parse_builder_question_form(data)
    scale = form_data["options"]["scale"]
    assert scale["type"] == "categories"
    assert scale["labels"] == ["Poor", "Fair", "Good"]
    # No NA toggle — no na_label key.
    assert "na_label" not in scale


def test_parse_builder_form_grid_na_default_label():
    data = {
        "text": "Rate each aspect",
        "type": "grid",
        "likert_mode": "number",
        "grid_include_na": "on",
        "grid_new_rows": "row one",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["options"]["scale"]["na_label"] == "Does not apply"


def test_parse_builder_form_grid_blank_rows_dropped():
    data = {
        "text": "Rate each aspect",
        "type": "grid",
        "likert_mode": "number",
        "grid_new_rows": "\n  \nrow one\n\nrow two\n",
    }
    form_data = _parse_builder_question_form(data)
    assert form_data["grid_new_rows"] == ["row one", "row two"]


# --- Model validation ---


def test_clean_rejects_required_grid_parent(db):
    survey = Survey.objects.create(
        owner=User.objects.create_user(username="u1", password="x"),
        name="S",
        slug="s-clean-parent",
    )
    q = SurveyQuestion(
        survey=survey,
        text="Stem",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
        required=True,
    )
    with pytest.raises(ValidationError):
        q.clean()


def test_clean_rejects_nested_grid(db):
    survey = Survey.objects.create(
        owner=User.objects.create_user(username="u2", password="x"),
        name="S",
        slug="s-clean-nested",
    )
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Stem",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
    )
    row = SurveyQuestion(
        survey=survey,
        parent=parent,
        text="Row",
        type=SurveyQuestion.Types.GRID,
    )
    with pytest.raises(ValidationError):
        row.clean()


def test_clean_rejects_disallowed_row_type(db):
    survey = Survey.objects.create(
        owner=User.objects.create_user(username="u3", password="x"),
        name="S",
        slug="s-clean-rowtype",
    )
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Stem",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
    )
    row = SurveyQuestion(
        survey=survey,
        parent=parent,
        text="Row",
        # orderable is not a valid grid row type
        type=SurveyQuestion.Types.ORDERABLE,
    )
    with pytest.raises(ValidationError):
        row.clean()


def test_clean_accepts_likert_row(db):
    survey = Survey.objects.create(
        owner=User.objects.create_user(username="u4", password="x"),
        name="S",
        slug="s-clean-ok",
    )
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Stem",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
    )
    row = SurveyQuestion(
        survey=survey,
        parent=parent,
        text="Row",
        type=SurveyQuestion.Types.LIKERT,
        options=[{"type": "number-scale", "min": 1, "max": 5, "render": "radio"}],
    )
    row.clean()  # no error


# --- Builder create ---


@pytest.mark.django_db
class TestGridCreate:
    def setup_survey(self, client):
        user = User.objects.create_user(username="griduser", password=TEST_PASSWORD)
        survey = _make_survey(user)
        client.force_login(user)
        return user, survey

    def test_create_grid_makes_parent_and_rows(self, client):
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
        response = client.post(
            url,
            {
                "text": "How good was your doctor today at each of the following?",
                "type": "grid",
                "likert_mode": "number",
                "likert_min": "1",
                "likert_max": "5",
                "required": "on",
                "grid_new_rows": "being polite\nmaking you feel at ease",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Question created." in response.content

        parent = SurveyQuestion.objects.filter(
            survey=survey, type=SurveyQuestion.Types.GRID
        ).get()
        # Stem required is False — required lives on the rows.
        assert parent.required is False
        rows = list(parent.subquestions.order_by("order", "id"))
        assert [r.text for r in rows] == ["being polite", "making you feel at ease"]
        for row in rows:
            assert row.type == SurveyQuestion.Types.LIKERT
            # Rows carry their own copy of the shared scale so flat
            # consumers (analytics, exports, rendering) need no changes.
            assert row.options[0]["type"] == "number-scale"
            assert row.options[0]["min"] == 1
            assert row.options[0]["max"] == 5
            assert row.options[0]["render"] == "radio"
            assert row.required is True
            assert row.parent_id == parent.id
            assert row.group_id == parent.group_id
        # Rows sort after the parent.
        assert rows[0].order > parent.order
        assert rows[1].order > rows[0].order

    def test_builder_list_shows_rows_inline_not_standalone(self, client):
        user, survey = self.setup_survey(client)
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
        client.post(
            url,
            {
                "text": "Rate each aspect",
                "type": "grid",
                "likert_mode": "number",
                "grid_new_rows": "aspect one\naspect two",
            },
            HTTP_HX_REQUEST="true",
        )
        # Re-render the builder list directly through the prepared path.
        questions = _prepare_question_rendering(
            survey, survey.questions.select_related("group").all()
        )
        # Rows are filtered out of the top-level list…
        assert all(q.type != SurveyQuestion.Types.LIKERT for q in questions)
        parent = questions[0]
        assert parent.type == SurveyQuestion.Types.GRID
        # …and attached to the parent instead.
        assert [r.text for r in parent.grid_rows] == ["aspect one", "aspect two"]

    def test_create_grid_in_group(self, client):
        user, survey = self.setup_survey(client)
        group = QuestionGroup.objects.create(name="G", owner=user)
        group.surveys.set([survey])
        url = reverse("surveys:builder_question_create", kwargs={"slug": survey.slug})
        client.post(
            url,
            {
                "text": "Rate it",
                "type": "grid",
                "likert_mode": "number",
                "grid_new_rows": "row one",
                "group_id": str(group.id),
            },
            HTTP_HX_REQUEST="true",
        )
        parent = SurveyQuestion.objects.get(
            survey=survey, type=SurveyQuestion.Types.GRID
        )
        assert parent.group_id == group.id
        assert parent.subquestions.get().group_id == group.id


# --- Builder edit ---


@pytest.mark.django_db
class TestGridEdit:
    def setup_grid(self, client):
        user = User.objects.create_user(username="gridedit", password=TEST_PASSWORD)
        survey = _make_survey(user, name="Grid Edit")
        client.force_login(user)
        parent = SurveyQuestion.objects.create(
            survey=survey,
            text="Rate each aspect",
            type=SurveyQuestion.Types.GRID,
            options={
                "type": "grid",
                "row_type": "likert",
                "scale": {
                    "type": "number-scale",
                    "min": 1,
                    "max": 5,
                    "render": "radio",
                },
            },
        )
        row_ids = []
        for text in ["aspect one", "aspect two"]:
            row = SurveyQuestion.objects.create(
                survey=survey,
                parent=parent,
                text=text,
                type=SurveyQuestion.Types.LIKERT,
                options=[
                    {"type": "number-scale", "min": 1, "max": 5, "render": "radio"}
                ],
            )
            row_ids.append(row.id)
        return user, survey, parent, row_ids

    def _edit_post(self, client, survey, parent, extra=None):
        url = reverse(
            "surveys:builder_question_edit",
            kwargs={"slug": survey.slug, "qid": parent.id},
        )
        data = {
            "text": "Rate each aspect",
            "type": "grid",
            "likert_mode": "number",
            "likert_min": "1",
            "likert_max": "5",
        }
        data.update(extra or {})
        return client.post(url, data, HTTP_HX_REQUEST="true")

    def test_rename_row_keeps_identity(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        response = self._edit_post(
            client,
            survey,
            parent,
            {
                f"grid_row_id_{row_ids[0]}": "aspect one (renamed)",
                f"grid_row_id_{row_ids[1]}": "aspect two",
            },
        )
        assert response.status_code == 200
        rows = list(parent.subquestions.order_by("order", "id"))
        assert [r.id for r in rows] == row_ids  # same questions, not recreated
        assert rows[0].text == "aspect one (renamed)"

    def test_remove_row_deletes_it(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        # Only row 0 posts — row 1 was removed in the browser.
        self._edit_post(
            client, survey, parent, {f"grid_row_id_{row_ids[0]}": "aspect one"}
        )
        rows = list(parent.subquestions.order_by("order", "id"))
        assert [r.id for r in rows] == [row_ids[0]]

    def test_add_row_appends(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        self._edit_post(
            client,
            survey,
            parent,
            {
                f"grid_row_id_{row_ids[0]}": "aspect one",
                f"grid_row_id_{row_ids[1]}": "aspect two",
                "grid_new_rows": "aspect three",
            },
        )
        rows = list(parent.subquestions.order_by("order", "id"))
        assert [r.text for r in rows] == [
            "aspect one",
            "aspect two",
            "aspect three",
        ]
        assert rows[2].order > rows[1].order

    def test_required_toggle_propagates_to_rows(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        self._edit_post(
            client,
            survey,
            parent,
            {
                f"grid_row_id_{row_ids[0]}": "aspect one",
                f"grid_row_id_{row_ids[1]}": "aspect two",
                "required": "on",
            },
        )
        parent.refresh_from_db()
        assert parent.required is False  # stem stays non-required
        for row in parent.subquestions.all():
            assert row.required is True

    def test_scale_edit_reaches_existing_rows(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        self._edit_post(
            client,
            survey,
            parent,
            {
                f"grid_row_id_{row_ids[0]}": "aspect one",
                f"grid_row_id_{row_ids[1]}": "aspect two",
                "likert_min": "0",
                "likert_max": "10",
                "grid_include_na": "on",
            },
        )
        for row in parent.subquestions.all():
            assert row.options[0]["min"] == 0
            assert row.options[0]["max"] == 10
            assert row.options[0]["na_label"] == "Does not apply"

    def test_switching_away_from_grid_deletes_rows(self, client):
        user, survey, parent, row_ids = self.setup_grid(client)
        url = reverse(
            "surveys:builder_question_edit",
            kwargs={"slug": survey.slug, "qid": parent.id},
        )
        client.post(
            url,
            {"text": "Just a likert now", "type": "likert", "likert_mode": "number"},
            HTTP_HX_REQUEST="true",
        )
        parent.refresh_from_db()
        assert parent.type == SurveyQuestion.Types.LIKERT
        assert parent.subquestions.count() == 0
        assert not SurveyQuestion.objects.filter(id__in=row_ids).exists()


# --- Copy ---


def test_duplicate_grid_clones_rows(db):
    user = User.objects.create_user(username="griddup", password=TEST_PASSWORD)
    survey = _make_survey(user, name="Grid Dup")
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Rate each aspect",
        type=SurveyQuestion.Types.GRID,
        order=1,
        options={
            "type": "grid",
            "row_type": "likert",
            "scale": {"type": "number-scale", "min": 1, "max": 5, "render": "radio"},
        },
    )
    for text in ["one", "two"]:
        SurveyQuestion.objects.create(
            survey=survey,
            parent=parent,
            text=text,
            type=SurveyQuestion.Types.LIKERT,
            order=parent.order + 1 if text == "one" else parent.order + 2,
            options=[{"type": "number-scale", "min": 1, "max": 5, "render": "radio"}],
        )
    other = SurveyQuestion.objects.create(
        survey=survey, text="after", type=SurveyQuestion.Types.TEXT, order=99
    )

    cloned = _duplicate_question(parent)

    assert cloned.id != parent.id
    assert cloned.type == SurveyQuestion.Types.GRID
    rows = list(cloned.subquestions.order_by("order", "id"))
    assert [r.text for r in rows] == ["one", "two"]
    for row in rows:
        assert row.parent_id == cloned.id
        assert row.type == SurveyQuestion.Types.LIKERT

    # The cloned block sits between the source grid and the question after
    # it, without colliding with the source rows' orders.
    source_rows = list(parent.subquestions.order_by("order", "id"))
    assert cloned.order == parent.order + 1
    assert rows[0].order == cloned.order + 1
    assert rows[1].order == cloned.order + 2
    other.refresh_from_db()
    assert other.order > rows[1].order
    for row in source_rows:
        row.refresh_from_db()
        assert row.order > rows[1].order


# --- Delete cascade ---


def test_deleting_grid_cascades_rows(db):
    user = User.objects.create_user(username="griddel", password=TEST_PASSWORD)
    survey = _make_survey(user, name="Grid Del")
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Rate each aspect",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
    )
    row = SurveyQuestion.objects.create(
        survey=survey,
        parent=parent,
        text="one",
        type=SurveyQuestion.Types.LIKERT,
    )
    parent.delete()
    assert not SurveyQuestion.objects.filter(id=row.id).exists()


# --- Branching target picker ---


def test_grid_rows_not_offered_as_branch_targets(db):
    user = User.objects.create_user(username="gridbr", password=TEST_PASSWORD)
    survey = _make_survey(user, name="Grid BR")
    parent = SurveyQuestion.objects.create(
        survey=survey,
        text="Rate each aspect",
        type=SurveyQuestion.Types.GRID,
        options={"type": "grid", "row_type": "likert", "scale": {}},
    )
    SurveyQuestion.objects.create(
        survey=survey,
        parent=parent,
        text="one",
        type=SurveyQuestion.Types.LIKERT,
    )
    _ = _prepare_question_rendering(
        survey, survey.questions.select_related("group").all()
    )
    # all_questions_meta (the branch target/source list) excludes rows —
    # rebuild it the same way the view does to assert the filter.
    from checktick_app.surveys.views import _serialize_question_for_builder

    # The parent is offered; the row is not: the builder list must not
    # contain the row as a standalone question.
    prepared = _prepare_question_rendering(
        survey, survey.questions.select_related("group").all()
    )
    assert [q.type for q in prepared] == [SurveyQuestion.Types.GRID]
    payload = _serialize_question_for_builder(prepared[0])
    assert [r["text"] for r in payload["grid_rows"]] == ["one"]


# --- Outline grammar (see docs/import.md §Grid of sub-questions) ---


GRID_MD = textwrap.dedent("""
    # About your consultation {consultation}

    ## How good was your doctor today at each of the following?* {doctor-quality}
    (grid likert number)
    min: 1
    max: 5
    left: Not at all good
    right: Very good
    na: Does not apply
    ### Being polite {being-polite}
    ### Making you feel at ease
    ### Listening to you*
    """).strip()


def test_parse_grid_markdown():
    groups = parse_bulk_markdown(GRID_MD)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "grid"
    assert q["required"] is False  # stem never required
    scale = q["final_options"]["scale"]
    assert scale["type"] == "number-scale"
    assert scale["min"] == 1
    assert scale["max"] == 5
    assert scale["left"] == "Not at all good"
    assert scale["right"] == "Very good"
    assert scale["render"] == "radio"
    assert scale["na_label"] == "Does not apply"
    # Rows: order preserved, `*` on the stem marks every row required,
    # a `*` on a single row overrides upward for mixed grids.
    assert [(r["title"], r["required"]) for r in q["grid_rows"]] == [
        ("Being polite", True),
        ("Making you feel at ease", True),
        ("Listening to you", True),
    ]
    # Row refs survive for stable round-trips.
    assert q["grid_rows"][0]["ref"] == "being-polite"


def test_parse_grid_categories_markdown():
    md = textwrap.dedent("""
        # Section {sec}

        ## Rate each aspect {rate}
        (grid likert categories)
        - Poor
        - Fair
        - Good
        ### Aspect one
        ### Aspect two
        """).strip()
    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    scale = q["final_options"]["scale"]
    assert scale["type"] == "categories"
    assert scale["labels"] == ["Poor", "Fair", "Good"]
    assert [r["title"] for r in q["grid_rows"]] == ["Aspect one", "Aspect two"]


def test_parse_grid_row_outside_grid_errors():
    md = textwrap.dedent("""
        # Section {sec}

        ## Standalone question
        (likert number)
        min: 1
        max: 5
        ### Orphan row
        """).strip()
    with pytest.raises(Exception, match=r"outside a \(grid"):
        parse_bulk_markdown(md)


def test_parse_grid_defaults_to_number_scale():
    md = textwrap.dedent("""
        # Section {sec}

        ## Rate it {rate}
        (grid)
        ### Row one
        """).strip()
    groups = parse_bulk_markdown(md)
    scale = groups[0]["questions"][0]["final_options"]["scale"]
    assert scale["type"] == "number-scale"
    assert scale["min"] == 1
    assert scale["max"] == 5


@pytest.mark.django_db
class TestGridOutlineRoundTrip:
    def test_export_then_parse_keeps_grid(self):
        user = User.objects.create_user(username="gridrt", password=TEST_PASSWORD)
        survey = _make_survey(user, name="Grid RT")
        group = QuestionGroup.objects.create(name="Section", owner=user)
        group.surveys.set([survey])
        parent = SurveyQuestion.objects.create(
            survey=survey,
            group=group,
            text="How good was your doctor today at each of the following?",
            type=SurveyQuestion.Types.GRID,
            order=1,
            options={
                "type": "grid",
                "row_type": "likert",
                "scale": {
                    "type": "number-scale",
                    "min": 1,
                    "max": 5,
                    "left": "Not at all good",
                    "right": "Very good",
                    "render": "radio",
                    "na_label": "Does not apply",
                },
            },
        )
        for idx, text in enumerate(["Being polite", "Listening to you"], start=2):
            SurveyQuestion.objects.create(
                survey=survey,
                group=group,
                parent=parent,
                text=text,
                type=SurveyQuestion.Types.LIKERT,
                required=True,
                order=idx,
                options=[
                    {
                        "type": "number-scale",
                        "min": 1,
                        "max": 5,
                        "left": "Not at all good",
                        "right": "Very good",
                        "render": "radio",
                    }
                ],
            )

        exported = _export_survey_to_markdown(survey)

        # The stem exports as a grid with the full scale…
        assert "(grid likert number)" in exported
        assert "min: 1" in exported
        assert "na: Does not apply" in exported
        # …rows export as ### lines, never as top-level ## questions…
        assert "### Being polite" in exported
        assert "### Listening to you*" in exported
        assert not any(
            line.startswith("## Being polite") for line in exported.splitlines()
        )
        # …and the re-parse round-trips.
        groups = parse_bulk_markdown(exported)
        q = groups[0]["questions"][0]
        assert q["final_type"] == "grid"
        assert q["final_options"]["scale"]["na_label"] == "Does not apply"
        assert [r["title"] for r in q["grid_rows"]] == [
            "Being polite",
            "Listening to you",
        ]
        assert all(r["required"] for r in q["grid_rows"])


# --- Participant-facing rendering + submission ---


def _published_grid_survey(user: User) -> tuple[Survey, SurveyQuestion, list]:
    """Published public survey with a grid stem and two rows."""
    survey = Survey.objects.create(
        owner=user,
        name="Grid Take",
        slug=f"grid-take-{user.id}",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )
    stem = SurveyQuestion.objects.create(
        survey=survey,
        text="How good was your doctor today at each of the following?",
        type=SurveyQuestion.Types.GRID,
        order=1,
        options={
            "type": "grid",
            "row_type": "likert",
            "scale": {
                "type": "number-scale",
                "min": 1,
                "max": 5,
                "left": "Not at all good",
                "right": "Very good",
                "render": "radio",
                "na_label": "Does not apply",
            },
        },
    )
    rows = []
    for idx, text in enumerate(["Being polite", "Listening to you"], start=2):
        rows.append(
            SurveyQuestion.objects.create(
                survey=survey,
                parent=stem,
                text=text,
                type=SurveyQuestion.Types.LIKERT,
                required=True,
                order=idx,
                options=[
                    {
                        "type": "number-scale",
                        "min": 1,
                        "max": 5,
                        "left": "Not at all good",
                        "right": "Very good",
                        "render": "radio",
                    }
                ],
            )
        )
    return survey, stem, rows


@pytest.mark.django_db
class TestGridTakePage:
    def setup_method(self):
        self.user = User.objects.create_user(
            username="gridtake", password=TEST_PASSWORD
        )
        self.survey, self.stem, self.rows = _published_grid_survey(self.user)

    def test_take_page_renders_grid(self, client):
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        assert res.status_code == 200
        html = res.content.decode()

        # Rows render as labelled radiogroups named q_<row id> — answers
        # stay flat, exactly like a standalone question.
        for row in self.rows:
            assert f'name="q_{row.id}"' in html
            assert f'id="grid_row_label_{row.id}"' in html
            assert f'aria-labelledby="grid_row_label_{row.id}' in html
        # Required rows enforce one answer per row (any required radio in
        # a named group makes the group required).
        assert html.count('name="q_%s"' % self.rows[0].id) >= 5
        # Every row offers the numbers 1-5 and the Does-not-apply answer.
        assert html.count(">1</span>") >= 2
        assert html.count(">5</span>") >= 2
        assert html.count('value="na"') == 2
        assert "Does not apply" in html
        # The shared scale labels render once for the whole grid.
        assert "Not at all good" in html
        assert "Very good" in html
        # The stem itself has no answer input.
        assert f'name="q_{self.stem.id}"' not in html
        # Required rows are marked for assistive tech.
        assert 'aria-required="true"' in html
        # Rows render ONLY inside the grid — never again as standalone
        # questions (their h2 label id must not appear).
        for row in self.rows:
            assert f"q_label_{row.id}" not in html

    def test_take_page_renders_categories_scale(self, client):
        opts = dict(self.stem.options)
        opts["scale"] = {
            "type": "categories",
            "labels": ["Poor", "Fair", "Good"],
            "render": "radio",
        }
        self.stem.options = opts
        self.stem.save()
        res = client.get(reverse("surveys:take", kwargs={"slug": self.survey.slug}))
        assert res.status_code == 200
        html = res.content.decode()
        assert "Poor, Fair, Good" in html  # shared scale hint line
        # Category labels become radio values.
        assert 'value="Fair"' in html
        # No Does-not-apply column without na_label.
        assert 'value="na"' not in html

    def test_annotate_filters_rows_and_attaches_to_stem(self):

        likert = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Standalone",
            type=SurveyQuestion.Types.LIKERT,
            order=10,
            options=[{"type": "number-scale", "min": 1, "max": 3, "render": "radio"}],
        )
        all_qs = list(self.survey.questions.order_by("order", "id"))
        out = _annotate_question_render_sequence(self.survey, all_qs)
        # Rows render inside the stem — filtered out of the sequence.
        assert [q.id for q in out] == [self.stem.id, likert.id]
        stem = out[0]
        assert [r.id for r in stem.grid_rows] == [r.id for r in self.rows]
        # The shared column-scale value list is attached for the template.
        assert stem.grid_scale_values == [1, 2, 3, 4, 5]
        # Likert radio questions get their value list on the take path too
        # (this was previously only set on the builder path, so a published
        # render=radio Likert rendered no inputs at all).
        standalone = out[1]
        assert standalone.num_scale_values == [1, 2, 3]

    def test_submit_stores_row_answers_flat(self, client):
        res = client.post(
            reverse("surveys:take", kwargs={"slug": self.survey.slug}),
            data={
                f"q_{self.rows[0].id}": "4",
                f"q_{self.rows[1].id}": "na",
            },
        )
        assert res.status_code in (200, 302)
        response = SurveyResponse.objects.filter(survey=self.survey).first()
        assert response is not None
        # Answers are keyed by row id — no nesting.
        assert response.answers[str(self.rows[0].id)] == "4"
        assert response.answers[str(self.rows[1].id)] == "na"
        # The stem carries no answer.
        assert response.answers.get(str(self.stem.id)) in (None, "")

    def test_csv_export_skips_stem_keeps_rows(self):
        """Grid stems get no CSV column; rows export as their own columns."""
        # Simulate the column-selection loop from survey_export_csv — the
        # view skips template_*, content_block, and grid stems.
        questions = list(self.survey.questions.order_by("order", "id"))
        columns = [
            q.text
            for q in questions
            if q.type
            not in (
                "template_patient",
                "template_professional",
                "content_block",
                "grid",
            )
        ]
        assert columns == ["Being polite", "Listening to you"]

    def test_delphi_aggregation_skips_stem(self):
        from checktick_app.surveys.delphi import _aggregate_single_question

        assert _aggregate_single_question(self.stem, [], None) is None
        # Rows aggregate as ordinary likert questions.
        stats = _aggregate_single_question(self.rows[0], [], None)
        assert stats["question_type"] == "likert"
