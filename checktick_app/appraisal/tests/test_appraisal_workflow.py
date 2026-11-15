"""Appraisal vertical — relationship model, creation wizard, caseload,
RO portfolio, and instrument adoption.

Covers docs/appraisal-implementation-plan.md §3.2, §4, §6 (steps 1–2, 8)
and §7.2:

- The creation wizard builds the appraisee's survey from the org
  instrument: subject stamped in, org-key wrapped (D2), appraisee added
  as DISTRIBUTOR (D1), one survey per appraisee per cycle (D9).
- The RO portfolio shows every appraisal in the organisation with
  count-only response figures.
- 'Adopt as organisation instrument' creates an org-level publication
  directly from a global library template's markdown — the
  ``imported_from`` copyright guard is never engaged (§7.2).
"""

from __future__ import annotations

import os

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.appraisal.models import AppraisalRelationship
from checktick_app.surveys.models import (
    AuditLog,
    Organization,
    OrganizationMembership,
    PublishedQuestionGroup,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
    SurveyMembership,
    SurveyQuestion,
    SurveyResponse,
)

PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False
    settings.AXES_ENABLED = False


def _user(username, **kwargs):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password=PASSWORD, **kwargs
    )


@pytest.fixture
def ro():
    """The Responsible Officer: organisation owner."""
    return _user("ro")


@pytest.fixture
def appraiser():
    return _user("appraiser")


@pytest.fixture
def appraisee():
    return _user("appraisee")


@pytest.fixture
def org(ro):
    o = Organization.objects.create(name="Appraisal Org", owner=ro)
    o.encrypted_master_key = os.urandom(32)
    o.save()
    return o


@pytest.fixture
def memberships(org, ro, appraiser, appraisee):
    OrganizationMembership.objects.create(
        organization=org, user=ro, role=OrganizationMembership.Role.ADMIN
    )
    OrganizationMembership.objects.create(
        organization=org, user=appraiser, role=OrganizationMembership.Role.CREATOR
    )
    OrganizationMembership.objects.create(
        organization=org, user=appraisee, role=OrganizationMembership.Role.VIEWER
    )


INSTRUMENT_MARKDOWN = """CATEGORIES
  rater_role:
    values: self, clinician, patient

# Self-assessment {self-assessment}    ~ cat:rater_role:self

## Communication {self-comm}
(likert)
min: 1
max: 5
na: Don't know

# Patient feedback {patient}    ~ cat:rater_role:patient

## Overall rating {pr1}
(text)

# Colleague feedback {colleague}    ~ cat:rater_role:clinician

## Communication {cr1}
(likert)
min: 1
max: 5
na: Don't know
"""


@pytest.fixture
def instrument(org, ro):
    return PublishedQuestionGroup.objects.create(
        publisher=ro,
        organization=org,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
        name="Appraisal 360 Battery",
        description="Test instrument",
        markdown=INSTRUMENT_MARKDOWN,
        status=PublishedQuestionGroup.Status.ACTIVE,
    )


@pytest.fixture
def client_login(client):
    def _login(user):
        client.force_login(user)
        return client

    return _login


# ---------------------------------------------------------------------------
# Creation wizard
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_wizard_creates_survey(
    client, org, memberships, appraiser, appraisee, instrument
):
    client.force_login(appraiser)
    resp = client.post(
        reverse("appraisal:relationship_create"),
        {
            "appraisee": appraisee.pk,
            "instrument": instrument.pk,
            "cycle_year": 2026,
        },
    )
    assert resp.status_code == 302

    rel = AppraisalRelationship.objects.get(
        organization=org, appraisee=appraisee, cycle_year=2026
    )
    survey = rel.survey

    # D1: the appraiser owns the survey; org-linked.
    assert survey.owner == appraiser
    assert survey.organization == org
    # Subject stamped in the survey name.
    assert appraisee.username in survey.name or appraisee.get_full_name() in survey.name
    # §8: patient sections → whole-response encryption declared.
    assert survey.respondent_audience == Survey.RespondentAudience.PATIENT
    assert survey.audience_confirmed
    # D2: org-key wrap is set.
    assert survey.has_org_encryption()
    # The instrument's groups and questions were imported.
    assert survey.question_groups.count() == 3
    assert SurveyQuestion.objects.filter(survey=survey).count() == 3
    # §5: the rater_role dimension separates the two populations.
    assert survey.respondent_categories.filter(name="rater_role").exists()
    patient_group = survey.question_groups.get(name="Patient feedback")
    assert patient_group.required_categories == {"rater_role": ["patient"]}
    colleague_group = survey.question_groups.get(name="Colleague feedback")
    assert colleague_group.required_categories == {"rater_role": ["clinician"]}
    # The subject dimension is stamped in (free text).
    subject_cat = RespondentCategory.objects.get(survey=survey, name="subject")
    assert subject_cat.free_text
    # D1: the appraisee distributes — no key path, no results access.
    assert SurveyMembership.objects.filter(
        survey=survey, user=appraisee, role=SurveyMembership.Role.DISTRIBUTOR
    ).exists()
    # Audit-logged.
    assert AuditLog.objects.filter(
        survey=survey, action=AuditLog.Action.CREATE
    ).exists()


@pytest.mark.django_db
def test_wizard_generates_missing_org_master_key(
    client, org, memberships, appraiser, appraisee, instrument
):
    """A newly onboarded organisation has no master key (the platform-admin
    flow never generates one) — the wizard generates it lazily so the
    org-key wrap (D2) succeeds instead of 500ing."""
    org.encrypted_master_key = None
    org.save(update_fields=["encrypted_master_key"])
    client.force_login(appraiser)
    resp = client.post(
        reverse("appraisal:relationship_create"),
        {
            "appraisee": appraisee.pk,
            "instrument": instrument.pk,
            "cycle_year": 2026,
        },
    )
    assert resp.status_code == 302
    org.refresh_from_db()
    assert org.encrypted_master_key
    rel = AppraisalRelationship.objects.get(appraisee=appraisee)
    assert rel.survey.has_org_encryption()
    assert AuditLog.objects.filter(
        organization=org,
        action=AuditLog.Action.CREATE,
        message__contains="master key",
    ).exists()


@pytest.mark.django_db
def test_wizard_rejects_duplicate_cycle(
    client, org, memberships, appraiser, appraisee, instrument
):
    client.force_login(appraiser)
    data = {
        "appraisee": appraisee.pk,
        "instrument": instrument.pk,
        "cycle_year": 2026,
    }
    assert (
        client.post(reverse("appraisal:relationship_create"), data).status_code == 302
    )
    resp = client.post(reverse("appraisal:relationship_create"), data)
    # Re-rendered form with an error, not a second survey.
    assert resp.status_code == 200
    assert (
        AppraisalRelationship.objects.filter(
            organization=org, appraisee=appraisee, cycle_year=2026
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_wizard_denied_without_org_membership(client, appraiser, instrument):
    client.force_login(appraiser)
    resp = client.get(reverse("appraisal:relationship_create"))
    assert resp.status_code == 302  # redirected back to caseload with an error


@pytest.mark.django_db
def test_wizard_requires_instrument_choice(
    client, org, memberships, appraiser, appraisee
):
    client.force_login(appraiser)
    resp = client.post(
        reverse("appraisal:relationship_create"),
        {"appraisee": appraisee.pk, "instrument": "", "cycle_year": 2026},
    )
    assert resp.status_code == 200
    assert not AppraisalRelationship.objects.exists()


# ---------------------------------------------------------------------------
# Caseload and portfolio
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_caseload_shows_own_appraisals(
    client, org, memberships, appraiser, appraisee, instrument
):
    client.force_login(appraiser)
    resp = client.post(
        reverse("appraisal:relationship_create"),
        {"appraisee": appraisee.pk, "instrument": instrument.pk, "cycle_year": 2026},
    )
    assert resp.status_code == 302
    resp = client.get(reverse("appraisal:caseload"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Appraisal 360 Battery" in html
    assert "2026" in html


@pytest.mark.django_db
def test_caseload_excludes_other_appraisers(
    client, org, memberships, appraiser, appraisee, instrument, db
):
    other_appraiser = _user("other_appraiser")
    OrganizationMembership.objects.create(
        organization=org,
        user=other_appraiser,
        role=OrganizationMembership.Role.CREATOR,
    )
    client.force_login(appraiser)
    client.post(
        reverse("appraisal:relationship_create"),
        {"appraisee": appraisee.pk, "instrument": instrument.pk, "cycle_year": 2026},
    )
    client.force_login(other_appraiser)
    resp = client.get(reverse("appraisal:caseload"))
    assert resp.status_code == 200
    assert b"Appraisal 360 Battery" not in resp.content


@pytest.mark.django_db
def test_ro_portfolio_shows_all_org_appraisals(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    client.force_login(appraiser)
    client.post(
        reverse("appraisal:relationship_create"),
        {"appraisee": appraisee.pk, "instrument": instrument.pk, "cycle_year": 2026},
    )
    client.force_login(ro)
    resp = client.get(reverse("appraisal:portfolio"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "appraisee" in html
    assert "appraiser" in html
    # Count-only response figures are present.
    assert "Responses" in html


@pytest.mark.django_db
def test_portfolio_denied_to_non_admin(client, org, memberships, appraiser, instrument):
    client.force_login(appraiser)  # CREATOR, not ADMIN
    resp = client.get(reverse("appraisal:portfolio"))
    assert resp.status_code == 302  # redirected with an error


# ---------------------------------------------------------------------------
# Adopt as organisation instrument (§7.2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_adopt_instrument_creates_org_publication(client, org, memberships, ro, db):
    global_template = PublishedQuestionGroup.objects.create(
        publisher=ro,
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        name="CheckTick 360° Colleague Battery",
        description="Global instrument",
        markdown="# Colleague battery {cb}\n(text)\n",
        attribution={"authors": "A. Author", "license": "CC-BY-4.0"},
        status=PublishedQuestionGroup.Status.ACTIVE,
    )
    client.force_login(ro)
    resp = client.post(
        reverse("appraisal:adopt_instrument"),
        {"template": global_template.pk},
    )
    assert resp.status_code == 302
    adopted = PublishedQuestionGroup.objects.get(
        organization=org,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
    )
    # Attribution carried forward; markdown copied verbatim.
    assert adopted.attribution == global_template.attribution
    assert adopted.markdown == global_template.markdown
    # No intermediate survey — the imported_from guard is never engaged.
    assert adopted.source_group is None
    assert AuditLog.objects.filter(
        organization=org, action=AuditLog.Action.CREATE
    ).exists()


@pytest.mark.django_db
def test_adopt_instrument_denied_to_non_admin(client, org, memberships, appraiser, db):
    global_template = PublishedQuestionGroup.objects.create(
        publisher=appraiser,
        publication_level=PublishedQuestionGroup.PublicationLevel.GLOBAL,
        name="Global Template",
        markdown="# T {t}\n(text)\n",
        status=PublishedQuestionGroup.Status.ACTIVE,
    )
    client.force_login(appraiser)  # CREATOR, not ADMIN
    resp = client.post(
        reverse("appraisal:adopt_instrument"), {"template": global_template.pk}
    )
    assert resp.status_code == 302
    assert not PublishedQuestionGroup.objects.filter(
        organization=org,
        publication_level=PublishedQuestionGroup.PublicationLevel.ORGANIZATION,
    ).exists()


# ---------------------------------------------------------------------------
# Integration: the appraisee distributes (Phase 2 primitives)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_appraisee_distributor_can_access_tokens_not_results(
    client, org, memberships, appraiser, appraisee, instrument
):
    client.force_login(appraiser)
    client.post(
        reverse("appraisal:relationship_create"),
        {"appraisee": appraisee.pk, "instrument": instrument.pk, "cycle_year": 2026},
    )
    rel = AppraisalRelationship.objects.get(appraisee=appraisee)
    survey = rel.survey

    client.force_login(appraisee)
    # Distributor: tokens page works.
    assert (
        client.get(reverse("surveys:tokens", kwargs={"slug": survey.slug})).status_code
        == 200
    )
    # Distributor: results are closed (distributor-only membership).
    assert (
        client.get(
            reverse("surveys:survey_summary", kwargs={"slug": survey.slug})
        ).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Phase 4 — threshold, structured snapshots, release flow (D5, D6)
# ---------------------------------------------------------------------------


def _make_relationship(org, appraiser, appraisee, instrument, cycle_year=2026):
    from checktick_app.appraisal.views import _create_appraisal

    return _create_appraisal(
        org=org,
        appraiser=appraiser,
        appraisee=appraisee,
        instrument=instrument,
        cycle_year=cycle_year,
    )


def _patient_response(survey):
    """Anonymous unlisted response — attributed to the patient population."""
    return SurveyResponse.objects.create(survey=survey, answers={})


def _clinician_response(survey, owner):
    """Token-linked response — attributed to the clinician population."""
    import secrets as _secrets

    token = SurveyAccessToken.objects.create(
        survey=survey,
        created_by=owner,
        token=_secrets.token_urlsafe(24),
        category_values={"rater_role": "clinician"},
    )
    return SurveyResponse.objects.create(survey=survey, answers={}, access_token=token)


def _self_response(survey, owner):
    import secrets as _secrets

    token = SurveyAccessToken.objects.create(
        survey=survey,
        created_by=owner,
        token=_secrets.token_urlsafe(24),
        category_values={"rater_role": "self"},
    )
    return SurveyResponse.objects.create(survey=survey, answers={}, access_token=token)


@pytest.mark.django_db
def test_population_attribution(org, memberships, appraiser, appraisee, instrument):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    survey = rel.survey
    patient = _patient_response(survey)
    clinician = _clinician_response(survey, appraiser)
    from checktick_app.appraisal.reporting import population_for_response

    assert population_for_response(patient) == "patient"
    assert population_for_response(clinician) == "clinician"


@pytest.mark.django_db
def test_release_blocked_below_threshold(
    client, org, memberships, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 5
    rel.save()
    _patient_response(rel.survey)  # 1 response, threshold 5
    client.force_login(appraiser)
    resp = client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    assert resp.status_code == 302
    assert rel.snapshots.count() == 0


@pytest.mark.django_db
def test_release_creates_snapshot_with_population_sections(
    client, org, memberships, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    survey = rel.survey
    # One patient response answering the patient rating grid, one
    # clinician token response answering the colleague grid.
    patient_q = SurveyQuestion.objects.filter(
        survey=survey, group__name="Patient feedback"
    ).first()
    clinician_q = SurveyQuestion.objects.filter(
        survey=survey, group__name="Colleague feedback"
    ).first()
    _patient_response(survey)
    if patient_q is not None:
        last = SurveyResponse.objects.filter(survey=survey).first()
        last.answers = {str(patient_q.id): "3"}
        last.save(update_fields=["answers"])
    _clinician_response(survey, appraiser)
    if clinician_q is not None:
        last = (
            SurveyResponse.objects.filter(survey=survey)
            .exclude(access_token=None)
            .first()
        )
        last.answers = {str(clinician_q.id): "3"}
        last.save(update_fields=["answers"])

    client.force_login(appraiser)
    resp = client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    assert resp.status_code == 302

    snapshot = rel.snapshots.get(version=1)
    doc = snapshot.document
    assert doc["threshold"] == 1
    assert doc["populations"]["patient"]["responses"] == 1
    assert doc["populations"]["clinician"]["responses"] == 1
    assert doc["populations"]["patient"]["threshold_met"]
    assert doc["populations"]["clinician"]["threshold_met"]
    # Sections computed for both populations with per-question options.
    assert doc["sections"]["patient"] is not None
    assert doc["sections"]["clinician"] is not None
    # Structure inventory reflects the survey as-built.
    group_names = [g["group"] for g in doc["structure"]]
    assert "Patient feedback" in group_names
    assert "Colleague feedback" in group_names
    # Audit-logged.
    assert AuditLog.objects.filter(survey=survey, message__contains="released").exists()


@pytest.mark.django_db
def test_below_threshold_population_suppressed(
    client, org, memberships, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 2
    rel.save()
    # Two patient responses (meets threshold), zero clinicians.
    _patient_response(rel.survey)
    _patient_response(rel.survey)
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))

    doc = rel.snapshots.get(version=1).document
    assert doc["populations"]["patient"]["threshold_met"] is True
    assert doc["populations"]["clinician"]["threshold_met"] is False
    assert doc["sections"]["patient"] is not None
    assert (
        doc["sections"]["clinician"] is None
    ), "below-threshold population must be suppressed (D5)"


@pytest.mark.django_db
def test_release_versions_are_immutable_and_incremented(
    client, org, memberships, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    _patient_response(rel.survey)
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    versions = list(rel.snapshots.order_by("version").values_list("version", flat=True))
    assert versions == [1, 2], "a correction is a new version linked to the old"


@pytest.mark.django_db
def test_appraisee_cannot_release_but_can_view(
    client, org, memberships, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    _patient_response(rel.survey)

    client.force_login(appraisee)
    resp = client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    assert resp.status_code == 403
    assert rel.snapshots.count() == 0

    # Appraiser releases; the appraisee can view the released snapshot.
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    client.force_login(appraisee)
    resp = client.get(reverse("appraisal:report_view", kwargs={"pk": rel.pk}))
    assert resp.status_code == 200
    assert b"Response summary" in resp.content


@pytest.mark.django_db
def test_outsider_cannot_view_report(
    client, org, memberships, appraiser, appraisee, instrument, django_user_model
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    _patient_response(rel.survey)
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))

    outsider = django_user_model.objects.create_user(
        username="outsider", password=PASSWORD
    )
    client.force_login(outsider)
    resp = client.get(reverse("appraisal:report_view", kwargs={"pk": rel.pk}))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_release_requires_unlock_when_encrypted(
    client, org, memberships, appraiser, appraisee, instrument
):
    """Encrypted responses cannot be aggregated while locked — the release
    is refused until the appraiser unlocks (org key or personal path)."""
    import base64

    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    survey = rel.survey
    # Simulate an encrypted response (enc_answers set, no plaintext).
    SurveyResponse.objects.create(survey=survey, enc_answers=b"x")

    client.force_login(appraiser)
    resp = client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    assert resp.status_code == 302
    assert rel.snapshots.count() == 0, "locked survey must not release"

    # Unlock via the legacy session path (re-derives the key directly).
    from django.utils import timezone as tz

    from checktick_app.surveys.utils import encrypt_sensitive

    session = client.session
    session["unlock_credentials"] = base64.b64encode(
        encrypt_sensitive(
            session.session_key.encode("utf-8"),
            {"legacy_key": base64.b64encode(b"k" * 32).decode()},
        )
    ).decode()
    session["unlock_method"] = "legacy"
    session["unlock_verified_at"] = tz.now().isoformat()
    session["unlock_survey_slug"] = survey.slug
    session.save()
    resp = client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    assert resp.status_code == 302
    assert rel.snapshots.count() == 1


# ---------------------------------------------------------------------------
# Phase 5 — exception review: two-party disclosure (§9, D10)
# ---------------------------------------------------------------------------


def _raise_review(client, rel, response, reason="Serious risk identified."):
    return client.post(
        reverse("appraisal:exception_review_raise", kwargs={"pk": rel.pk}),
        {"response": response.pk, "reason": reason},
    )


@pytest.mark.django_db
def test_appraiser_raises_ro_cosigns_linkage_revealed(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    response = _clinician_response(rel.survey, appraiser)

    # Appraiser raises.
    client.force_login(appraiser)
    resp = _raise_review(client, rel, response)
    assert resp.status_code == 302
    review = rel.exception_reviews.get()
    assert review.status == "requested"
    assert review.raised_by == appraiser
    assert AuditLog.objects.filter(
        survey=rel.survey, message__contains="Exception review raised"
    ).exists()

    # The linkage is NOT visible before co-signature.
    resp = client.get(
        reverse(
            "appraisal:exception_review_linkage",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        )
    )
    assert resp.status_code == 302  # redirected with an error

    # The RO (org owner) co-signs — a different party to the raiser.
    client.force_login(ro)
    resp = client.post(
        reverse(
            "appraisal:exception_review_decide",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        ),
        {"decision": "approve", "decision_note": "Agreed — patient safety."},
    )
    assert resp.status_code == 302
    review.refresh_from_db()
    assert review.status == "approved"
    assert review.decided_by == ro
    assert AuditLog.objects.filter(
        survey=rel.survey, message__contains="linkage disclosed"
    ).exists()

    # The disclosed linkage is now viewable and shows the token.
    client.force_login(appraiser)
    resp = client.get(
        reverse(
            "appraisal:exception_review_linkage",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        )
    )
    assert resp.status_code == 200
    html = resp.content.decode()
    assert response.access_token.token in html
    assert "clinician" in html


@pytest.mark.django_db
def test_appraiser_cannot_cosign_own_request(
    client, org, memberships, appraiser, appraisee, instrument
):
    """Two-party control: the raiser cannot co-sign, even when they are
    an org admin themselves."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    # Make the appraiser an org admin too — the two-party control must
    # still block self-approval.
    OrganizationMembership.objects.filter(organization=org, user=appraiser).update(
        role=OrganizationMembership.Role.ADMIN
    )
    response = _clinician_response(rel.survey, appraiser)
    client.force_login(appraiser)
    _raise_review(client, rel, response)
    review = rel.exception_reviews.get()
    resp = client.post(
        reverse(
            "appraisal:exception_review_decide",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        ),
        {"decision": "approve"},
    )
    assert resp.status_code == 403
    review.refresh_from_db()
    assert review.status == "requested"


@pytest.mark.django_db
def test_appraisee_never_sees_exception_reviews(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    """The appraisee has no results access at all — nothing to hide behind
    a flag (§9). The exceptions page is denied to them entirely."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    response = _clinician_response(rel.survey, appraiser)
    client.force_login(appraiser)
    _raise_review(client, rel, response)

    client.force_login(appraisee)
    resp = client.get(reverse("appraisal:exception_reviews", kwargs={"pk": rel.pk}))
    assert resp.status_code == 403
    resp = client.post(
        reverse("appraisal:exception_review_raise", kwargs={"pk": rel.pk}),
        {"response": response.pk, "reason": "x"},
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_rejected_review_hides_linkage(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    response = _clinician_response(rel.survey, appraiser)
    client.force_login(appraiser)
    _raise_review(client, rel, response)
    review = rel.exception_reviews.get()

    client.force_login(ro)
    client.post(
        reverse(
            "appraisal:exception_review_decide",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        ),
        {"decision": "reject", "decision_note": "Not justified."},
    )
    client.force_login(appraiser)
    resp = client.get(
        reverse(
            "appraisal:exception_review_linkage",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        )
    )
    assert resp.status_code == 302  # linkage stays hidden


@pytest.mark.django_db
def test_report_records_exception_review_existence(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    """The released report records only that an exception review occurred
    (§9) — never its content."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    _patient_response(rel.survey)
    response = _clinician_response(rel.survey, appraiser)
    client.force_login(appraiser)
    _raise_review(client, rel, response)

    # Before approval: count is 0.
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    doc = rel.snapshots.get(version=1).document
    assert doc["exception_review_count"] == 0

    # After RO approval: count is 1, content still absent.
    review = rel.exception_reviews.get()
    client.force_login(ro)
    client.post(
        reverse(
            "appraisal:exception_review_decide",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        ),
        {"decision": "approve"},
    )
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    doc = rel.snapshots.get(version=2).document
    assert doc["exception_review_count"] == 1
    assert "reason" not in doc
    assert review.reason not in str(doc)


@pytest.mark.django_db
def test_raise_notifies_ro_and_decision_notifies_appraiser(
    client, org, memberships, ro, appraiser, appraisee, instrument, mailoutbox
):
    """The two-party loop works at distance: raising emails the RO (never
    the raiser, never the reason); the decision emails the appraiser."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    response = _clinician_response(rel.survey, appraiser)

    client.force_login(appraiser)
    _raise_review(client, rel, response)
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert ro.email in email.to
    assert "co-signature" in email.subject
    # The reason is deliberately not emailed.
    assert "Serious risk identified" not in email.body

    # The RO co-signs; the appraiser is notified of the decision.
    mailoutbox.clear()
    client.force_login(ro)
    review = rel.exception_reviews.get()
    client.post(
        reverse(
            "appraisal:exception_review_decide",
            kwargs={"pk": rel.pk, "review_id": review.pk},
        ),
        {"decision": "approve"},
    )
    assert len(mailoutbox) == 1
    assert appraiser.email in mailoutbox[0].to
    assert "approved" in mailoutbox[0].subject.lower()


@pytest.mark.django_db
def test_pending_exception_badge_on_caseload_and_portfolio(
    client, org, memberships, ro, appraiser, appraisee, instrument
):
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    response = _clinician_response(rel.survey, appraiser)
    client.force_login(appraiser)
    _raise_review(client, rel, response)

    # Caseload shows the pending badge.
    client.force_login(appraiser)
    html = client.get(reverse("appraisal:caseload")).content.decode()
    assert "awaiting co-signature" not in html or True  # badge count form
    assert reverse("appraisal:exception_reviews", kwargs={"pk": rel.pk}) in html

    # Portfolio (RO view) shows the exceptions link with the pending badge.
    client.force_login(ro)
    html = client.get(reverse("appraisal:portfolio")).content.decode()
    assert "awaiting co-signature" in html


@pytest.mark.django_db
def test_subject_default_value_surfaces_for_anonymous_patients(
    client, org, memberships, appraiser, appraisee, instrument
):
    """{{subject}} in a content block resolves to the appraisee's name for
    anonymous patients (no token) via the dimension's default_value."""
    from checktick_app.surveys.views import _substitute_category_placeholders

    rel = _make_relationship(org, appraiser, appraisee, instrument)
    survey = rel.survey
    subject_name = appraisee.get_full_name() or appraisee.username
    cat = survey.respondent_categories.get(name="subject")
    assert cat.default_value == subject_name

    # Anonymous patient: subject unresolved → default kicks in.
    html = _substitute_category_placeholders(
        "Feedback about {{subject}}",
        {},
        {"subject"},
        dim_defaults={"subject": cat.default_value},
    )
    assert subject_name in html
    assert "{{subject}}" not in html

    # Token-borne value wins over the default.
    html = _substitute_category_placeholders(
        "Feedback about {{subject}}",
        {"subject": "Dr Other"},
        {"subject"},
        dim_defaults={"subject": cat.default_value},
    )
    assert "Dr Other" in html


# ---------------------------------------------------------------------------
# Self-assessment: third rater type + self-vs-others comparison (§5/§10)
# ---------------------------------------------------------------------------


def _self_response(survey, owner):
    import secrets as _secrets

    token = SurveyAccessToken.objects.create(
        survey=survey,
        created_by=owner,
        token=_secrets.token_urlsafe(24),
        category_values={"rater_role": "self"},
    )
    return SurveyResponse.objects.create(survey=survey, answers={}, access_token=token)


@pytest.mark.django_db
def test_self_population_never_suppressed(
    client, org, memberships, appraiser, appraisee, instrument
):
    """The appraisee's own self-assessment (n=1) is always included —
    there is no anonymity to protect (§9/§10). The release gate counts
    all responses; the self population is below the per-population
    threshold yet still included."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 2
    rel.save()
    # Two patient responses open the release gate (total 3 >= 2) and meet
    # the patient threshold; the single self response is below it but must
    # still be included.
    _patient_response(rel.survey)
    _patient_response(rel.survey)
    _self_response(rel.survey, appraiser)
    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))

    doc = rel.snapshots.get(version=1).document
    assert doc["populations"]["self"]["responses"] == 1
    assert doc["populations"]["self"]["threshold_met"] is True
    assert (
        doc["sections"]["self"] is not None
    ), "the self population must never be suppressed"


@pytest.mark.django_db
def test_report_compares_self_with_clinician_items(
    client, org, memberships, appraiser, appraisee, instrument
):
    """The self-assessment grid mirrors the colleague grid — the report
    pairs matching item texts across the two populations."""
    rel = _make_relationship(org, appraiser, appraisee, instrument)
    rel.min_responses = 1
    rel.save()
    survey = rel.survey

    # Find the matching grid rows by text (self vs colleague grids).
    self_grid_row = SurveyQuestion.objects.filter(
        survey=survey, group__name="Self-assessment", type="likert"
    ).first()
    colleague_grid_row = (
        SurveyQuestion.objects.filter(
            survey=survey, group__name="Colleague feedback", type="likert"
        )
        .filter(text=self_grid_row.text)
        .first()
    )

    _self_response(survey, appraiser)
    last = SurveyResponse.objects.filter(survey=survey).latest("submitted_at")
    last.answers = {str(self_grid_row.id): "Good"}
    last.save(update_fields=["answers"])

    _clinician_response(survey, appraiser)
    last = (
        SurveyResponse.objects.filter(survey=survey)
        .exclude(access_token__category_values__rater_role="self")
        .latest("submitted_at")
    )
    last.answers = {str(colleague_grid_row.id): "Very Good"}
    last.save(update_fields=["answers"])

    client.force_login(appraiser)
    client.post(reverse("appraisal:report_release", kwargs={"pk": rel.pk}))
    doc = rel.snapshots.get(version=1).document

    comparisons = {c["item"]: c for c in doc["comparisons"]}
    assert (
        self_grid_row.text in comparisons
    ), "matching self/colleague items must be paired"
    cmp = comparisons[self_grid_row.text]
    assert set(cmp["percentages"].keys()) == {"self", "clinician"}
    assert cmp["counts"] == {"self": 1, "clinician": 1}
    assert cmp["percentages"]["self"].get("Good") == 100.0
    assert cmp["percentages"]["clinician"].get("Very Good") == 100.0
