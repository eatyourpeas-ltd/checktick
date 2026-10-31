"""Grid of sub-questions (matrix/battery) — model + builder plumbing.

A grid is a stem with no answer of its own plus rows sharing one scale.
Rows are real SurveyQuestion rows (type likert) with ``parent`` set, so
answers stay flat (keyed by row id) and every flat consumer —
submissions, partial answers, progress, analytics, exports — works
unchanged. See docs/respondent-categories-implementation-plan.md for the
360° assessment background.
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion
from checktick_app.surveys.views import (
    _duplicate_question,
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
