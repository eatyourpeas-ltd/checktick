"""Reproduce the question-order bug with the GMC 360 template scenario.

Imports the new GMC patient questionnaire (grids + CATEGORIES) into a
survey via the appraisal builder path, reorders questions within a
group, and checks the live/preview order.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.urls import reverse
import pytest

from checktick_app.appraisal.views import _build_survey_from_instrument
from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    Survey,
    SurveyQuestion,
)
from checktick_app.surveys.views import (
    _order_questions_by_group,
    create_default_section,
)

PASSWORD = "x"
TEMPLATE = Path(
    "docs/question-group-templates/question-group-templates-360-gmc-patient-questionnaire.md"
)


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


@pytest.mark.django_db
def test_gmc_template_reorder_persists(client, django_user_model):
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username="gmc@example.com", password=PASSWORD
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.ORGANIZATION, email_confirmed=True
    )
    user._state.fields_cache.pop("profile", None)
    client.force_login(user)

    org = Organization.objects.create(name="GMC Org", owner=user)
    org.encrypted_master_key = os.urandom(32)
    org.save()
    OrganizationMembership.objects.create(
        organization=org, user=user, role=OrganizationMembership.Role.ADMIN
    )

    markdown = TEMPLATE.read_text()
    PublishedQuestionGroup.objects.create(
        publisher=user,
        organization=org,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
        name="GMC 360",
        markdown=markdown,
        status=PublishedQuestionGroup.Status.ACTIVE,
    )
    survey = Survey.objects.create(
        owner=user,
        organization=org,
        name="GMC Survey",
        slug="gmc-reorder-survey",
    )
    _build_survey_from_instrument(survey=survey, markdown=markdown, owner=user)

    # Reorder within the patient group: move the last patient question
    # ("Was this visit with your usual doctor?") to the front.
    patient_group = survey.question_groups.get(name="Patient Introduction")
    qs = list(
        SurveyQuestion.objects.filter(survey=survey, group=patient_group).order_by(
            "order", "id"
        )
    )
    assert len(qs) >= 3, f"expected several patient questions, got {len(qs)}"
    last = qs[-1]
    new_order_ids = [last.id] + [q.id for q in qs if q.id != last.id]

    resp = client.post(
        reverse(
            "surveys:builder_group_questions_reorder",
            kwargs={"slug": survey.slug, "gid": patient_group.id},
        ),
        {"order": ",".join(str(i) for i in new_order_ids)},
    )
    assert resp.status_code == 200

    last.refresh_from_db()
    assert last.order == 0, f"reorder not persisted: last.order={last.order}"

    # Live ordering honours it
    all_questions = list(survey.questions.all())
    ordered = _order_questions_by_group(survey, all_questions)
    patient_ordered = [q for q in ordered if q.group_id == patient_group.id]
    assert patient_ordered[0].id == last.id, (
        "live order does not reflect the persisted reorder: "
        f"{[q.text[:40] for q in patient_ordered]}"
    )


@pytest.mark.django_db
def test_group_reorder_persists_and_live_order_follows(client, django_user_model):
    """The Organise page's section drag must be reflected in the live survey."""
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username="greorder@example.com", password=PASSWORD
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.PRO, email_confirmed=True
    )
    user._state.fields_cache.pop("profile", None)
    client.force_login(user)

    survey = Survey.objects.create(
        owner=user, name="Group Reorder Survey", slug="group-reorder-survey"
    )
    g1 = create_default_section(survey, user)
    g1.name = "Alpha"
    g1.save()
    g2 = create_default_section(survey, user)
    g2.name = "Beta"
    g2.save()
    SurveyQuestion.objects.create(
        survey=survey, group=g1, text="A1", type="text", order=0
    )
    SurveyQuestion.objects.create(
        survey=survey, group=g2, text="B1", type="text", order=0
    )

    # Drag Beta above Alpha
    resp = client.post(
        reverse("surveys:survey_groups_reorder", kwargs={"slug": survey.slug}),
        {"order": f"{g2.id},{g1.id}"},
    )
    assert resp.status_code == 302

    survey.refresh_from_db()
    from checktick_app.surveys.views import _resolved_group_order_ids

    resolved = _resolved_group_order_ids(survey)
    print(f"\nresolved group order: {resolved} (beta={g2.id} alpha={g1.id})")
    assert resolved == [g2.id, g1.id], "group reorder not persisted"

    all_questions = list(survey.questions.all())
    ordered = _order_questions_by_group(survey, all_questions)
    assert [q.text for q in ordered] == ["B1", "A1"]
