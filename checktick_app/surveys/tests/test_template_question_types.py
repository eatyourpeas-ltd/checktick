from __future__ import annotations

import textwrap

from django.urls import reverse
import pytest

from checktick_app.surveys.markdown_import import parse_bulk_markdown
from checktick_app.surveys.models import Survey, SurveyQuestion

TEST_PASSWORD = "x"


# --- Parsing ---


def test_parse_template_professional_type():
    md = textwrap.dedent("""
        # Section {sec}
        ## Professional details
        (template_professional)
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "template_professional"
    assert q["final_options"] == {"template": "professional_details"}


def test_parse_template_professional_address_lookup():
    md = textwrap.dedent("""
        # Section {sec}
        ## Professional details
        (template_professional)
        address_lookup: true
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "template_professional"
    assert q["final_options"]["address_lookup"] is True


def test_parse_template_patient_type():
    md = textwrap.dedent("""
        # Section {sec}
        ## Patient details
        (template_patient)
        """).strip()

    groups = parse_bulk_markdown(md)
    q = groups[0]["questions"][0]
    assert q["final_type"] == "template_patient"
    assert q["final_options"] == {"template": "patient_details_encrypted"}


def test_parse_template_aliases():
    md = textwrap.dedent("""
        # Section {sec}
        ## Prof
        (professional details)

        ## Pat
        (patient details)
        """).strip()

    groups = parse_bulk_markdown(md)
    types = [q["final_type"] for q in groups[0]["questions"]]
    assert types == ["template_professional", "template_patient"]


# --- Full bulk upload import ---


@pytest.mark.django_db
def test_bulk_import_creates_professional_template_question(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="author", password=TEST_PASSWORD
    )
    survey = Survey.objects.create(owner=user, name="BulkProf", slug="bulk-prof")

    md = textwrap.dedent("""
        # Section {sec}
        ## Professional details
        (template_professional)
        address_lookup: true
        """).strip()

    client.login(username="author", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
        follow=False,
    )
    assert response.status_code == 302

    q = SurveyQuestion.objects.get(survey=survey, text="Professional details")
    assert q.type == SurveyQuestion.Types.TEMPLATE_PROFESSIONAL
    assert q.options["template"] == "professional_details"
    assert q.options["address_lookup"] is True


@pytest.mark.django_db
def test_bulk_import_patient_template_requires_paid_tier(client, django_user_model):
    from checktick_app.core.models import UserProfile

    user = django_user_model.objects.create_user(
        username="freeuser", password=TEST_PASSWORD
    )
    UserProfile.objects.filter(user=user).update(
        account_tier=UserProfile.AccountTier.FREE
    )
    survey = Survey.objects.create(owner=user, name="BulkPat", slug="bulk-pat")

    md = textwrap.dedent("""
        # Section {sec}
        ## Patient details
        (template_patient)
        """).strip()

    client.login(username="freeuser", password=TEST_PASSWORD)
    response = client.post(
        reverse("surveys:bulk_upload", kwargs={"slug": survey.slug}),
        {"markdown": md},
    )
    assert response.status_code == 200
    assert "requires a paid subscription" in response.content.decode()
    assert not SurveyQuestion.objects.filter(
        survey=survey, type=SurveyQuestion.Types.TEMPLATE_PATIENT
    ).exists()
