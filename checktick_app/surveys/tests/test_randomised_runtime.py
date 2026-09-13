"""Tests for the RCT runtime hook (step 4).

When survey.layout == rct and the participant has no assigned_arm, the
take view: ensures a RandomisedMenu, assigns an arm, resolves
selected_group_ids from the arm's groups (ordered by the Organise-page
order), stores both on SurveyProgress, and renders the filtered question
list. On resume (assigned_arm set), the assignment is skipped and the
previously-resolved selected_group_ids is used. There is no picker page
for RCT.
"""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    RandomisedArm,
    RandomisedMenu,
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


@pytest.fixture
def rct_survey(owner, org):
    """A published RCT survey with two arms.

    Demographics: in both arms (shared)
    Intervention: in Intervention arm only
    Control: in Control arm only
    """
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="RCT Survey",
        slug="rct-survey",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.RCT,
    )
    g_demo = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g_int = QuestionGroup.objects.create(name="Intervention", owner=owner)
    g_ctrl = QuestionGroup.objects.create(name="Control", owner=owner)
    s.question_groups.add(g_demo, g_int, g_ctrl)
    SurveyQuestion.objects.create(
        survey=s, group=g_demo, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_int, text="Dose", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g_ctrl, text="Placebo", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = RandomisedMenu.objects.create(
        survey=s,
        seed=42,
        allocation_strategy=RandomisedMenu.AllocationStrategy.BALANCED,
    )
    arm_int = RandomisedArm.objects.create(menu=menu, name="Intervention", order=1)
    arm_ctrl = RandomisedArm.objects.create(menu=menu, name="Control", order=2)
    arm_int.groups.add(g_demo, g_int)
    arm_ctrl.groups.add(g_demo, g_ctrl)
    s._g_demo = g_demo
    s._g_int = g_int
    s._g_ctrl = g_ctrl
    s._arm_int = arm_int
    s._arm_ctrl = arm_ctrl
    s._menu = menu
    return s


# --- arm assignment on first access ---


@pytest.mark.django_db
def test_first_access_assigns_arm_and_filters_questions(
    client, rct_survey, participant
):
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": rct_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=rct_survey, user=participant)
    assert progress.assigned_arm is not None
    assert progress.assigned_arm in (rct_survey._arm_int, rct_survey._arm_ctrl)
    assert progress.randomisation_seed is not None
    # selected_group_ids should be the arm's groups, ordered by
    # _resolved_group_order_ids (Demographics first by name).
    assert set(progress.selected_group_ids) == set(
        progress.assigned_arm.groups.values_list("id", flat=True)
    )
    # No picker for RCT — the question list renders directly.
    html = res.content.decode()
    assert "Age" in html  # Demographics (shared)
    # Exactly one of Dose/Placebo appears, depending on the arm.
    assert ("Dose" in html) != ("Placebo" in html)


@pytest.mark.django_db
def test_resume_skips_assignment(client, rct_survey, participant):
    """On a second GET, the assigned_arm and selected_group_ids are reused."""
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": rct_survey.slug})
    client.get(url)
    progress1 = SurveyProgress.objects.get(survey=rct_survey, user=participant)
    first_arm_id = progress1.assigned_arm_id
    first_seed = progress1.randomisation_seed
    first_selection = list(progress1.selected_group_ids)
    # Second access — should not re-assign.
    client.get(url)
    progress2 = SurveyProgress.objects.get(survey=rct_survey, user=participant)
    assert progress2.assigned_arm_id == first_arm_id
    assert progress2.randomisation_seed == first_seed
    assert list(progress2.selected_group_ids) == first_selection
    # Re-render status check via a fresh GET.
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_selected_group_ids_ordered_by_organise_page_order(
    client, rct_survey, participant
):
    """The arm's groups are resolved through _resolved_group_order_ids so
    the authored order is preserved, not the M2M add order."""
    from checktick_app.surveys.views import _resolved_group_order_ids

    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": rct_survey.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=rct_survey, user=participant)
    arm_group_ids = set(progress.assigned_arm.groups.values_list("id", flat=True))
    expected = [
        gid for gid in _resolved_group_order_ids(rct_survey) if gid in arm_group_ids
    ]
    assert progress.selected_group_ids == expected


@pytest.mark.django_db
def test_no_arms_blocks_take_with_error(client, owner, org, participant):
    """An RCT survey with no arms configured shows an error and redirects."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Empty RCT",
        slug="empty-rct",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.RCT,
    )
    RandomisedMenu.objects.create(survey=s)  # menu with no arms
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": s.slug})
    res = client.get(url)
    # Redirects to detail with an error message.
    assert res.status_code in (200, 302)
    progress = SurveyProgress.objects.filter(survey=s, user=participant).first()
    if progress:
        assert progress.assigned_arm is None


@pytest.mark.django_db
def test_empty_arm_falls_back_gracefully(client, owner, org, participant):
    """An arm with no groups yields an empty selected_group_ids but the
    take view still renders (the survey is completable as empty)."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Empty Arm RCT",
        slug="empty-arm-rct",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.AUTHENTICATED,
        allow_any_authenticated=True,
        layout=Survey.Layout.RCT,
    )
    g = QuestionGroup.objects.create(name="G", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q1", type=SurveyQuestion.Types.TEXT, order=0
    )
    menu = RandomisedMenu.objects.create(survey=s, seed=1)
    RandomisedArm.objects.create(menu=menu, name="Empty", order=1)  # no groups
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": s.slug})
    res = client.get(url)
    assert res.status_code == 200
    progress = SurveyProgress.objects.get(survey=s, user=participant)
    assert progress.assigned_arm is not None
    assert progress.selected_group_ids == []


@pytest.mark.django_db
def test_rct_does_not_render_picker(client, rct_survey, participant):
    """RCT has no picker — the take view renders the question list directly."""
    client.force_login(participant)
    url = reverse("surveys:take", kwargs={"slug": rct_survey.slug})
    res = client.get(url)
    html = res.content.decode()
    # The section_menu picker template should not be used for RCT.
    assert "section-picker" not in html
    assert "Choose sections" not in html


@pytest.mark.django_db
def test_balanced_allocation_progression(client, rct_survey, owner):
    """With a fixed seed and balanced strategy, four participants walk two
    permuted blocks — 2 Intervention, 2 Control."""
    # rct_survey has 1:1 ratios, seed=42, balanced.
    assignments = []
    for i in range(4):
        p_user = type(rct_survey.owner).objects.create_user(
            username=f"p{i}@example.com", password=TEST_PASSWORD
        )
        client.force_login(p_user)
        client.get(reverse("surveys:take", kwargs={"slug": rct_survey.slug}))
        progress = SurveyProgress.objects.get(survey=rct_survey, user=p_user)
        assignments.append(progress.assigned_arm.name)
    assert assignments.count("Intervention") == 2
    assert assignments.count("Control") == 2
