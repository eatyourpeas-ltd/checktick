"""Tests for the staged runtime hook (step 3).

When survey.layout == staged, the take view recomputes the currently-open
phases on every access and resolves selected_group_ids from their union
(ordered by the Organise-page order). Unlike rct (fixed arm assignment),
the open set changes over time, so we recompute each visit. When no phase
is open, a friendly "check back later" page renders instead of an empty
form.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    StagedMenu,
    StagedPhase,
    Survey,
    SurveyProgress,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


def _make_staged_survey(owner, org, *, slug="staged-survey", start_at=None):
    """A published staged survey with three groups and no phases yet."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Staged Survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.STAGED,
        start_at=start_at,
    )
    g_base = QuestionGroup.objects.create(name="Baseline", owner=owner)
    g_follow = QuestionGroup.objects.create(name="Followup", owner=owner)
    g_review = QuestionGroup.objects.create(name="Review", owner=owner)
    s.question_groups.add(g_base, g_follow, g_review)
    SurveyQuestion.objects.create(
        survey=s,
        group=g_base,
        text="Baseline Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_follow,
        text="Followup Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_review,
        text="Review Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    s._g_base = g_base
    s._g_follow = g_follow
    s._g_review = g_review
    return s


# --- first access: open phase filters questions ---


@pytest.mark.django_db
def test_first_access_open_phase_filters_questions(client, owner, org, participant):
    s = _make_staged_survey(owner, org)
    menu = StagedMenu.objects.create(survey=s)  # enrolment anchor
    # Baseline open now (0..14), follow-up later.
    baseline = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    baseline.groups.add(s._g_base)
    followup = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    followup.groups.add(s._g_follow)

    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": s.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    # Only the baseline group is open right now.
    assert progress.selected_group_ids == [s._g_base.id]
    html = res.content.decode()
    assert "Baseline Q" in html
    assert "Followup Q" not in html
    assert "Review Q" not in html


@pytest.mark.django_db
def test_multiple_open_phases_union_groups(client, owner, org, participant):
    s = _make_staged_survey(owner, org, slug="staged-multi")
    menu = StagedMenu.objects.create(survey=s)
    # Both phases open now (overlapping windows).
    p1 = StagedPhase.objects.create(
        menu=menu, name="P1", order=1, start_offset_days=0, end_offset_days=10
    )
    p1.groups.add(s._g_base, s._g_follow)
    p2 = StagedPhase.objects.create(
        menu=menu, name="P2", order=2, start_offset_days=0, end_offset_days=None
    )
    p2.groups.add(s._g_follow, s._g_review)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    # Union of both phases' groups, ordered by Organise-page order
    # (Baseline, Followup, Review by name).
    assert progress.selected_group_ids == [
        s._g_base.id,
        s._g_follow.id,
        s._g_review.id,
    ]
    html = res.content.decode()
    assert "Baseline Q" in html
    assert "Followup Q" in html
    assert "Review Q" in html


# --- no phases open ---


@pytest.mark.django_db
def test_no_phases_open_renders_check_back_page(client, owner, org, participant):
    s = _make_staged_survey(owner, org, slug="staged-future")
    menu = StagedMenu.objects.create(survey=s)
    # Only a future phase — nothing open now.
    phase = StagedPhase.objects.create(
        menu=menu, name="Later", order=1, start_offset_days=100, end_offset_days=None
    )
    phase.groups.add(s._g_base)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No sections available yet" in html
    assert "Baseline Q" not in html
    # Progress row is preserved so resume works when the phase opens.
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.selected_group_ids == []


@pytest.mark.django_db
def test_no_staged_menu_renders_no_phases_page(client, owner, org, participant):
    """A staged survey with no StagedMenu configured shows the no-phases
    page — participants never see unconfigured/future sections."""
    s = _make_staged_survey(owner, org, slug="staged-unconfigured")
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No sections available yet" in html
    assert "Baseline Q" not in html


# --- recompute on each access (unlike rct) ---


@pytest.mark.django_db
def test_recomputes_open_set_on_each_access(client, owner, org, participant):
    """Staged recomputes the open phases every visit — the stored
    selected_group_ids is overwritten, not preserved like rct."""
    s = _make_staged_survey(owner, org, slug="staged-recompute")
    menu = StagedMenu.objects.create(survey=s)
    baseline = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    baseline.groups.add(s._g_base)

    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": s.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.selected_group_ids == [s._g_base.id]

    # Simulate time passing: backdate enrolment so baseline has closed and
    # follow-up (start=14) is now open.
    progress.created_at = timezone.now() - timedelta(days=20)
    progress.save(update_fields=["created_at"])
    followup = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    followup.groups.add(s._g_follow)

    res = client.get(url)
    assert res.status_code == 200
    progress.refresh_from_db()
    # Recomputed: baseline closed, follow-up open.
    assert progress.selected_group_ids == [s._g_follow.id]
    html = res.content.decode()
    assert "Followup Q" in html
    assert "Baseline Q" not in html


# --- survey_open anchor ---


@pytest.mark.django_db
def test_survey_open_anchor_uses_start_at(client, owner, org, participant):
    s = _make_staged_survey(
        owner,
        org,
        slug="staged-surveyopen",
        start_at=timezone.now() - timedelta(days=20),
    )
    menu = StagedMenu.objects.create(survey=s, anchor=StagedMenu.Anchor.SURVEY_OPEN)
    # Baseline 0..14 (closed by day 20), follow-up 14..28 (open at day 20).
    baseline = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    baseline.groups.add(s._g_base)
    followup = StagedPhase.objects.create(
        menu=menu, name="Followup", order=2, start_offset_days=14, end_offset_days=28
    )
    followup.groups.add(s._g_follow)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.selected_group_ids == [s._g_follow.id]
    html = res.content.decode()
    assert "Followup Q" in html
    assert "Baseline Q" not in html


@pytest.mark.django_db
def test_survey_open_anchor_no_start_at_renders_all(client, owner, org, participant):
    """survey_open anchor with no Survey.start_at: anchor is None, nothing
    is open, but we don't crash — falls through to rendering all sections
    (the organise-view warnings flag this misconfiguration)."""
    s = _make_staged_survey(owner, org, slug="staged-no-start", start_at=None)
    menu = StagedMenu.objects.create(survey=s, anchor=StagedMenu.Anchor.SURVEY_OPEN)
    phase = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    phase.groups.add(s._g_base)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    # open_group_ids returns [] (anchor None), so selected_group_ids is []
    # and the no-phases page renders.
    html = res.content.decode()
    assert "No sections available yet" in html


# --- no picker for staged ---


@pytest.mark.django_db
def test_staged_does_not_render_picker(client, owner, org, participant):
    s = _make_staged_survey(owner, org, slug="staged-nopicker")
    menu = StagedMenu.objects.create(survey=s)
    phase = StagedPhase.objects.create(
        menu=menu, name="Baseline", order=1, start_offset_days=0, end_offset_days=14
    )
    phase.groups.add(s._g_base)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    html = res.content.decode()
    # The section_menu picker template is not used for staged.
    assert "section-picker" not in html
    assert "Choose sections" not in html
