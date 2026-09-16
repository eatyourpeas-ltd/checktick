"""Tests for the Delphi runtime hook.

When survey.layout == delphi, the take view assigns the participant to
the current open round (FK on SurveyProgress), resolves
selected_group_ids from the round's groups (ordered by the Organise-page
order), and renders the questions. When no round is open, a friendly
"check back later" page renders instead of an empty form. When the
assigned round has closed, the participant advances to the next open
round.
"""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    DelphiMenu,
    DelphiRound,
    Organization,
    QuestionGroup,
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
        username="delphi_owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def participant(django_user_model):
    return django_user_model.objects.create_user(
        username="delphi_participant@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


def _make_delphi_survey(owner, org, *, slug="delphi-survey", start_at=None):
    """A published Delphi survey with three groups and no rounds yet."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Delphi Survey",
        slug=slug,
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.DELPHI,
        start_at=start_at,
    )
    g_r1 = QuestionGroup.objects.create(name="Round1", owner=owner)
    g_r2 = QuestionGroup.objects.create(name="Round2", owner=owner)
    g_shared = QuestionGroup.objects.create(name="Shared", owner=owner)
    s.question_groups.add(g_r1, g_r2, g_shared)
    SurveyQuestion.objects.create(
        survey=s,
        group=g_r1,
        text="Round 1 Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_r2,
        text="Round 2 Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    SurveyQuestion.objects.create(
        survey=s,
        group=g_shared,
        text="Shared Q",
        type=SurveyQuestion.Types.TEXT,
        order=0,
    )
    s._g_r1 = g_r1
    s._g_r2 = g_r2
    s._g_shared = g_shared
    return s


# --- first access: open round filters questions ---


@pytest.mark.django_db
def test_first_access_open_round_filters_questions(client, owner, org, participant):
    s = _make_delphi_survey(owner, org)
    menu = DelphiMenu.objects.create(survey=s)  # enrolment anchor
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(s._g_r1, s._g_shared)
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(s._g_r2, s._g_shared)

    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": s.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    # Assigned to round 1.
    assert progress.delphi_round_id == r1.id
    # Only round 1's groups are selected.
    assert s._g_r1.id in progress.selected_group_ids
    assert s._g_shared.id in progress.selected_group_ids
    assert s._g_r2.id not in progress.selected_group_ids
    html = res.content.decode()
    assert "Round 1 Q" in html
    assert "Shared Q" in html
    assert "Round 2 Q" not in html


# --- no round open ---


@pytest.mark.django_db
def test_no_round_open_renders_check_back_page(client, owner, org, participant):
    s = _make_delphi_survey(owner, org, slug="delphi-future")
    menu = DelphiMenu.objects.create(survey=s)
    # Only a future round — nothing open now.
    rnd = DelphiRound.objects.create(
        menu=menu, order=0, name="Later", start_offset_days=100, end_offset_days=None
    )
    rnd.groups.add(s._g_r1)

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No round available right now" in html
    assert "Round 1 Q" not in html
    # Progress row is preserved so resume works when the round opens.
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.delphi_round is None


@pytest.mark.django_db
def test_no_delphi_menu_renders_error(client, owner, org, participant):
    """A Delphi survey with no DelphiMenu configured shows an error."""
    s = _make_delphi_survey(owner, org, slug="delphi-unconfigured")
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    # Redirects to the detail page with an error message.
    assert res.status_code == 302


# --- round advancement ---


@pytest.mark.django_db
def test_advances_to_next_round_when_current_closes(client, owner, org, participant):
    """When the assigned round's window has passed, advance to the next."""
    s = _make_delphi_survey(owner, org, slug="delphi-advance")
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(s._g_r1, s._g_shared)
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="Round 2", start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(s._g_r2, s._g_shared)

    # Simulate first access 10 days ago (round 1 was open then).
    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))

    # Manually shift the progress row's created_at back 10 days so round 1
    # has closed and round 2 is now open.
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    progress.created_at = timezone.now() - timedelta(days=10)
    progress.save(update_fields=["created_at"])

    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    progress.refresh_from_db()
    # Now on round 2.
    assert progress.delphi_round_id == r2.id
    assert s._g_r2.id in progress.selected_group_ids
    assert s._g_r1.id not in progress.selected_group_ids
    html = res.content.decode()
    assert "Round 2 Q" in html
    assert "Round 1 Q" not in html


# --- resume: assigned round preserved ---


@pytest.mark.django_db
def test_resume_preserves_round_assignment(client, owner, org, participant):
    """On resume, the assigned round is preserved (idempotent)."""
    s = _make_delphi_survey(owner, org, slug="delphi-resume")
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="Round 1", start_offset_days=0, end_offset_days=14
    )
    r1.groups.add(s._g_r1, s._g_shared)

    client.force_login(participant)
    # First access.
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.delphi_round_id == r1.id

    # Second access (resume).
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    progress.refresh_from_db()
    # Still on round 1.
    assert progress.delphi_round_id == r1.id


# --- round with no groups ---


@pytest.mark.django_db
def test_round_with_no_groups_renders_check_back_page(client, owner, org, participant):
    """A round with an empty group set renders the no-round page (graceful)."""
    s = _make_delphi_survey(owner, org, slug="delphi-empty-round")
    menu = DelphiMenu.objects.create(survey=s)
    DelphiRound.objects.create(
        menu=menu, order=0, name="Empty", start_offset_days=0, end_offset_days=7
    )  # No groups added

    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No round available right now" in html


# --- shared group across rounds ---


@pytest.mark.django_db
def test_shared_group_appears_in_both_rounds(client, owner, org, participant):
    """A group in multiple rounds appears in each round's selection."""
    s = _make_delphi_survey(owner, org, slug="delphi-shared")
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(s._g_r1, s._g_shared)
    r2 = DelphiRound.objects.create(
        menu=menu, order=1, name="R2", start_offset_days=7, end_offset_days=14
    )
    r2.groups.add(s._g_r2, s._g_shared)

    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert s._g_shared.id in progress.selected_group_ids

    # Advance to round 2.
    progress.created_at = timezone.now() - timedelta(days=10)
    progress.save(update_fields=["created_at"])
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    progress.refresh_from_db()
    assert s._g_shared.id in progress.selected_group_ids
    assert s._g_r2.id in progress.selected_group_ids
    assert s._g_r1.id not in progress.selected_group_ids


# --- last round closed: no next round ---


@pytest.mark.django_db
def test_last_round_closed_renders_check_back_page(client, owner, org, participant):
    """When the last round has closed and there's no next, render check-back."""
    s = _make_delphi_survey(owner, org, slug="delphi-last-closed")
    menu = DelphiMenu.objects.create(survey=s)
    r1 = DelphiRound.objects.create(
        menu=menu, order=0, name="R1", start_offset_days=0, end_offset_days=7
    )
    r1.groups.add(s._g_r1)

    client.force_login(participant)
    client.get(reverse("surveys:take", kwargs={"slug": s.slug}))

    # Shift to after round 1 closed.
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    progress.created_at = timezone.now() - timedelta(days=20)
    progress.save(update_fields=["created_at"])

    res = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "No round available right now" in html
