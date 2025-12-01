from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.core.models import UserProfile
from checktick_app.surveys.models import QuestionGroup, Survey, SurveyQuestion
from checktick_app.surveys.views import (
    DEMOGRAPHIC_FIELD_DEFS,
    PATIENT_TEMPLATE_DEFAULT_FIELDS,
)


@pytest.fixture
def pro_owner(db):
    """Create a PRO tier user for patient data tests."""
    owner = User.objects.create_user(username="owner", password="x")
    owner.profile.account_tier = UserProfile.AccountTier.PRO
    owner.profile.save()
    return owner


@pytest.mark.django_db
def test_add_patient_template_creates_question(client, pro_owner):
    survey = Survey.objects.create(owner=pro_owner, name="Demo", slug="demo")
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)

    client.force_login(pro_owner)
    url = reverse(
        "surveys:builder_group_template_add",
        kwargs={"slug": survey.slug, "gid": group.id},
    )
    resp = client.post(url, {"template": "patient_details_encrypted"})
    assert resp.status_code == 200
    qs = SurveyQuestion.objects.filter(survey=survey, group=group)
    assert qs.count() == 1
    q = qs.first()
    assert q.type == SurveyQuestion.Types.TEMPLATE_PATIENT
    assert q.options["template"] == "patient_details_encrypted"
    fields = q.options.get("fields", [])
    assert len(fields) == len(DEMOGRAPHIC_FIELD_DEFS)
    selected_keys = {f.get("key") for f in fields if f.get("selected")}
    assert selected_keys == set(PATIENT_TEMPLATE_DEFAULT_FIELDS)
    assert not q.options.get("include_imd")


@pytest.mark.django_db
def test_duplicate_template_request_no_second_question(client):
    owner = User.objects.create_user(username="owner2", password="x")
    survey = Survey.objects.create(owner=owner, name="Demo 2", slug="demo-2")
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    survey.question_groups.add(group)

    client.force_login(owner)
    url = reverse(
        "surveys:builder_group_template_add",
        kwargs={"slug": survey.slug, "gid": group.id},
    )
    client.post(url, {"template": "professional_details"})
    resp = client.post(url, {"template": "professional_details"})
    assert resp.status_code == 200
    qs = SurveyQuestion.objects.filter(survey=survey, group=group)
    assert qs.count() == 1
    q = qs.first()
    assert q.type == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL
    assert q.options["template"] == "professional_details"


@pytest.mark.django_db
def test_patient_template_update_toggles_fields(client):
    # Patient data requires PRO tier
    owner = User.objects.create_user(username="owner3", password="x")
    owner.profile.account_tier = UserProfile.AccountTier.PRO
    owner.profile.save()

    survey = Survey.objects.create(owner=owner, name="Demo 3", slug="demo-3")
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    survey.question_groups.add(group)

    client.force_login(owner)
    add_url = reverse(
        "surveys:builder_group_template_add",
        kwargs={"slug": survey.slug, "gid": group.id},
    )
    client.post(add_url, {"template": "patient_details_encrypted"})
    question = SurveyQuestion.objects.get(survey=survey, group=group)

    update_url = reverse(
        "surveys:builder_group_question_template_patient_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )

    resp = client.post(
        update_url,
        {
            "fields": ["first_name", "post_code"],
            "include_imd": "on",
        },
    )
    assert resp.status_code == 200

    question.refresh_from_db()
    fields = {f["key"]: f for f in question.options["fields"]}
    assert fields["first_name"]["selected"] is True
    assert fields["post_code"]["selected"] is True
    assert all(
        not meta["selected"]
        for key, meta in fields.items()
        if key not in {"first_name", "post_code"}
    )
    assert question.options["include_imd"] is True

    resp = client.post(update_url, {"fields": ["first_name"]})
    assert resp.status_code == 200
    question.refresh_from_db()
    fields = {f["key"]: f for f in question.options["fields"]}
    assert fields["post_code"]["selected"] is False
    assert question.options["include_imd"] is False


@pytest.mark.django_db
def test_professional_template_update_respects_ods_toggle(client):
    owner = User.objects.create_user(username="owner4", password="x")
    survey = Survey.objects.create(owner=owner, name="Demo 4", slug="demo-4")
    group = QuestionGroup.objects.create(name="Group", owner=owner)
    survey.question_groups.add(group)

    client.force_login(owner)
    add_url = reverse(
        "surveys:builder_group_template_add",
        kwargs={"slug": survey.slug, "gid": group.id},
    )
    client.post(add_url, {"template": "professional_details"})
    question = SurveyQuestion.objects.get(survey=survey, group=group)

    update_url = reverse(
        "surveys:builder_group_question_template_professional_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )

    resp = client.post(
        update_url,
        {
            "fields": ["employing_trust", "job_title"],
            "ods_employing_trust": "on",
        },
    )
    assert resp.status_code == 200

    question.refresh_from_db()
    fields = {f["key"]: f for f in question.options["fields"]}
    assert fields["employing_trust"]["selected"] is True
    assert fields["employing_trust"]["ods_enabled"] is True
    assert fields["job_title"]["selected"] is True
    assert fields["employing_health_board"]["ods_enabled"] is False

    resp = client.post(update_url, {"fields": ["job_title"]})
    assert resp.status_code == 200
    question.refresh_from_db()
    fields = {f["key"]: f for f in question.options["fields"]}
    assert fields["employing_trust"]["selected"] is False
    assert fields["employing_trust"]["ods_enabled"] is False
