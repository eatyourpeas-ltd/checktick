from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    Survey,
    SurveyQuestion,
)

User = get_user_model()


def _group_sequence(questions: list[SurveyQuestion]) -> list[str]:
    """Return ordered unique group names from a question list."""
    sequence: list[str] = []
    for q in questions:
        name = q.group.name if q.group else ""
        if name and (not sequence or sequence[-1] != name):
            sequence.append(name)
    return sequence


@pytest.mark.django_db
def test_survey_map_preview_take_share_same_question_order(client):
    owner = User.objects.create_user(username="owner-order", password="x")
    org = Organization.objects.create(name="Org", owner=owner)

    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Order Contract",
        slug="order-contract",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )

    group_a = QuestionGroup.objects.create(name="Group A", owner=owner)
    group_b = QuestionGroup.objects.create(name="Group B", owner=owner)
    survey.question_groups.add(group_a, group_b)

    # Intentionally make global question.order conflict with desired group order.
    # Desired order (via /groups map state): A then B.
    style = survey.style or {}
    style["group_order"] = [group_a.id, group_b.id]
    survey.style = style
    survey.save(update_fields=["style"])

    q_b = SurveyQuestion.objects.create(
        survey=survey,
        group=group_b,
        text="B question",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    q_a = SurveyQuestion.objects.create(
        survey=survey,
        group=group_a,
        text="A question",
        type=SurveyQuestion.Types.TEXT,
        order=1,
    )

    client.force_login(owner)

    # Survey Map source of truth
    map_resp = client.get(
        reverse("surveys:branching_data_api", kwargs={"slug": survey.slug})
    )
    assert map_resp.status_code == 200
    map_ids = [int(q["id"]) for q in map_resp.json()["questions"]]
    assert map_ids == [q_a.id, q_b.id]

    # Preview should match map
    preview_resp = client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert preview_resp.status_code == 200
    preview_ids = [q.id for q in list(preview_resp.context["questions"])]
    assert preview_ids == map_ids

    # Live take should also match map (use non-owner access path)
    client.logout()
    take_resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert take_resp.status_code == 200
    take_ids = [q.id for q in list(take_resp.context["questions"])]
    assert take_ids == map_ids

    # And live should carry branching_config in this same order
    branching_config = json.loads(take_resp.context["branching_config"])
    assert branching_config["questions"] == [str(i) for i in map_ids]


@pytest.mark.django_db
def test_preview_and_take_match_groups_page_order_when_group_order_is_partial(client):
    owner = User.objects.create_user(username="owner-partial", password="x")
    org = Organization.objects.create(name="Org", owner=owner)

    survey = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Partial Group Order",
        slug="partial-group-order",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.PUBLIC,
    )

    # IDs increase in this creation order: Zulu, Mike, Alpha.
    group_zulu = QuestionGroup.objects.create(name="Zulu", owner=owner)
    group_mike = QuestionGroup.objects.create(name="Mike", owner=owner)
    group_alpha = QuestionGroup.objects.create(name="Alpha", owner=owner)
    survey.question_groups.add(group_zulu, group_mike, group_alpha)

    # Partial saved order: one explicit group + one stale id.
    # Remaining groups should follow same fallback as /groups/ page.
    style = survey.style or {}
    style["group_order"] = [group_zulu.id, 999999]
    survey.style = style
    survey.save(update_fields=["style"])

    SurveyQuestion.objects.create(
        survey=survey,
        group=group_zulu,
        text="Z question",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group_mike,
        text="M question",
        type=SurveyQuestion.Types.TEXT,
        order=1,
    )
    SurveyQuestion.objects.create(
        survey=survey,
        group=group_alpha,
        text="A question",
        type=SurveyQuestion.Types.TEXT,
        order=2,
    )

    client.force_login(owner)

    groups_resp = client.get(reverse("surveys:groups", kwargs={"slug": survey.slug}))
    assert groups_resp.status_code == 200
    groups_page_order = [g.name for g in list(groups_resp.context["groups"])]
    assert groups_page_order == ["Zulu", "Alpha", "Mike"]

    preview_resp = client.get(reverse("surveys:preview", kwargs={"slug": survey.slug}))
    assert preview_resp.status_code == 200
    preview_group_order = _group_sequence(list(preview_resp.context["questions"]))
    assert preview_group_order == groups_page_order

    client.logout()
    take_resp = client.get(reverse("surveys:take", kwargs={"slug": survey.slug}))
    assert take_resp.status_code == 200
    take_group_order = _group_sequence(list(take_resp.context["questions"]))
    assert take_group_order == groups_page_order
