from __future__ import annotations

from django.contrib.auth.models import User
import pytest

from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyQuestionCondition,
)

TEST_PASSWORD = "x"


def _make_survey_and_groups(owner: User, slug: str):
    survey = Survey.objects.create(owner=owner, name="Demo", slug=slug)
    group_a = QuestionGroup.objects.create(name="Section A", owner=owner)
    group_b = QuestionGroup.objects.create(name="Section B", owner=owner)
    survey.question_groups.add(group_a, group_b)
    return survey, group_a, group_b


def _move_url(survey_slug: str, qid: int, gid: int | None = None) -> str:
    if gid is None:
        return f"/surveys/{survey_slug}/builder/questions/{qid}/move"
    return f"/surveys/{survey_slug}/builder/groups/{gid}/questions/{qid}/move"


@pytest.mark.django_db
def test_move_appends_question_to_end_of_target_section(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-basic")
    q1 = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Q1",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group_b,
        text="Q2",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=2,
    )

    client.force_login(owner)
    resp = client.post(
        _move_url(survey.slug, q1.id, group_a.id), {"target_gid": group_b.id}
    )

    assert resp.status_code == 200
    q1.refresh_from_db()
    assert q1.group_id == group_b.id
    assert q1.order == 3  # appended after the target section's max order
    html = resp.content.decode()
    # Source list re-rendered without the question...
    assert "Q1" not in html
    assert "Question moved" in html
    # ...and the rail is OOB-swapped with updated counts.
    assert 'hx-swap-oob="outerHTML"' in html
    assert 'data-gid="%d"' % group_a.id in html


@pytest.mark.django_db
def test_move_grid_moves_rows_as_block(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-grid")
    stem = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Grid",
        type=SurveyQuestion.Types.GRID,
        options={
            "type": "grid",
            "row_type": "likert",
            "scale": {"type": "number-scale"},
        },
        order=1,
    )
    rows = [
        SurveyQuestion.objects.create(
            survey=survey,
            group=group_a,
            parent=stem,
            text=f"Row {i}",
            type=SurveyQuestion.Types.LIKERT,
            options=[{"type": "number-scale", "min": 1, "max": 5}],
            order=i,
        )
        for i in (2, 3)
    ]

    client.force_login(owner)
    resp = client.post(
        _move_url(survey.slug, stem.id, group_a.id), {"target_gid": group_b.id}
    )

    assert resp.status_code == 200
    stem.refresh_from_db()
    assert stem.group_id == group_b.id
    for row in rows:
        row.refresh_from_db()
        assert row.group_id == group_b.id
    assert "Grid and its 2 row(s) moved" in resp.content.decode()


@pytest.mark.django_db
def test_move_rejects_same_section_and_unknown_section(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-invalid")
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Q1",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )

    client.force_login(owner)
    resp = client.post(
        _move_url(survey.slug, q.id, group_a.id), {"target_gid": group_a.id}
    )
    assert resp.status_code == 200
    assert b"already in that section" in resp.content
    q.refresh_from_db()
    assert q.group_id == group_a.id

    resp = client.post(
        _move_url(survey.slug, q.id, group_a.id), {"target_gid": "99999"}
    )
    assert resp.status_code == 200
    assert b"no longer exists" in resp.content
    q.refresh_from_db()
    assert q.group_id == group_a.id


@pytest.mark.django_db
def test_move_ungrouped_question_into_section(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, _group_b = _make_survey_and_groups(owner, "move-ungrouped")
    q = SurveyQuestion.objects.create(
        survey=survey,
        text="Loose",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=0,
    )

    client.force_login(owner)
    resp = client.post(_move_url(survey.slug, q.id), {"target_gid": group_a.id})

    assert resp.status_code == 200
    q.refresh_from_db()
    assert q.group_id == group_a.id
    assert b"Question moved" in resp.content


@pytest.mark.django_db
def test_move_requires_edit_permission(client):
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    viewer = User.objects.create_user(username="viewer", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-perms")
    q = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Q1",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )

    client.force_login(viewer)
    resp = client.post(
        _move_url(survey.slug, q.id, group_a.id), {"target_gid": group_b.id}
    )
    assert resp.status_code in (302, 403)
    q.refresh_from_db()
    assert q.group_id == group_a.id


@pytest.mark.django_db
def test_move_carries_branching_conditions_with_the_question(client):
    """Conditions attached to a moved question travel with it (FK)."""
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-branch")
    source = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Trigger",
        type=SurveyQuestion.Types.YESNO,
        options=[],
        order=1,
    )
    target = SurveyQuestion.objects.create(
        survey=survey,
        group=group_b,
        text="Target",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )
    SurveyQuestionCondition.objects.create(
        question=source,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_question=target,
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )

    client.force_login(owner)
    resp = client.post(
        _move_url(survey.slug, source.id, group_a.id), {"target_gid": group_b.id}
    )

    assert resp.status_code == 200
    source.refresh_from_db()
    assert source.group_id == group_b.id
    cond = SurveyQuestionCondition.objects.get(question=source)
    assert cond.target_question_id == target.id


@pytest.mark.django_db
def test_move_card_signposts_anchor_and_conditions(client):
    """Move button exposes branching data attributes for the modal notices."""
    owner = User.objects.create_user(username="owner", password=TEST_PASSWORD)
    survey, group_a, group_b = _make_survey_and_groups(owner, "move-signpost")
    anchor = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="Anchor",
        type=SurveyQuestion.Types.TEXT,
        options=[{"type": "text", "format": "free"}],
        order=1,
    )
    other = SurveyQuestion.objects.create(
        survey=survey,
        group=group_b,
        text="Other",
        type=SurveyQuestion.Types.YESNO,
        options=[],
        order=1,
    )
    # Another question jumps to the *section* A — resolved via its first question.
    SurveyQuestionCondition.objects.create(
        question=other,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_group=group_a,
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )
    # The anchor has an outgoing condition of its own.
    SurveyQuestionCondition.objects.create(
        question=anchor,
        operator=SurveyQuestionCondition.Operator.EQUALS,
        value="yes",
        target_question=other,
        action=SurveyQuestionCondition.Action.JUMP_TO,
    )

    client.force_login(owner)
    resp = client.get(f"/surveys/{survey.slug}/builder/?gid={group_a.id}")
    assert resp.status_code == 200
    html = resp.content.decode()
    move_btn = html[html.index("builder-move-button") :]
    assert 'data-anchor="1"' in move_btn
    assert 'data-out="1"' in move_btn
