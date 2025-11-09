from __future__ import annotations

from django.contrib.auth.models import User
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    OrganizationMembership,
    Survey,
    SurveyMembership,
)


@pytest.fixture
def users(db):
    admin = User.objects.create_user(username="admin", password="x")
    creator = User.objects.create_user(username="creator", password="x")
    viewer = User.objects.create_user(username="viewer", password="x")
    outsider = User.objects.create_user(username="outsider", password="x")
    participant = User.objects.create_user(username="participant", password="x")
    return admin, creator, viewer, outsider, participant


@pytest.fixture
def org(db, users):
    admin, creator, viewer, outsider, participant = users
    org = Organization.objects.create(name="Org", owner=admin)
    OrganizationMembership.objects.create(
        organization=org, user=admin, role=OrganizationMembership.Role.ADMIN
    )
    OrganizationMembership.objects.create(
        organization=org, user=creator, role=OrganizationMembership.Role.CREATOR
    )
    OrganizationMembership.objects.create(
        organization=org, user=viewer, role=OrganizationMembership.Role.VIEWER
    )
    return org


@pytest.fixture
def surveys(db, org, users):
    admin, creator, viewer, outsider, participant = users
    s1 = Survey.objects.create(owner=creator, organization=org, name="S1", slug="s1")
    s2 = Survey.objects.create(owner=admin, organization=org, name="S2", slug="s2")
    return s1, s2


def login(client, user):
    client.force_login(user)


@pytest.mark.django_db
def test_creator_sees_only_own_surveys(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    login(client, creator)
    res = client.get(reverse("surveys:list"))
    assert res.status_code == 200
    names = {s.name for s in res.context["surveys"]}
    assert names == {"S1"}


@pytest.mark.django_db
def test_admin_sees_all_org_surveys(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    login(client, admin)
    res = client.get(reverse("surveys:list"))
    assert res.status_code == 200
    names = {s.name for s in res.context["surveys"]}
    assert names == {"S1", "S2"}


@pytest.mark.django_db
def test_viewer_sees_only_own_surveys(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    login(client, viewer)
    res = client.get(reverse("surveys:list"))
    assert res.status_code == 200
    names = {s.name for s in res.context["surveys"]}
    assert names == set()


@pytest.mark.django_db
def test_creator_cannot_edit_others_survey(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    login(client, creator)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s2.slug}))
    assert res.status_code == 403


@pytest.mark.django_db
def test_admin_can_edit_any_in_org(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    login(client, admin)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s1.slug}))
    assert res.status_code == 200


@pytest.mark.django_db
def test_participant_cannot_access_builder(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    # Simulate a participant (non-org) user
    login(client, participant)
    res = client.get(reverse("surveys:groups", kwargs={"slug": s1.slug}))
    assert res.status_code == 403


@pytest.mark.django_db
def test_anonymous_cannot_access_survey_detail(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    res = client.get(reverse("surveys:detail", kwargs={"slug": s1.slug}))
    # login_required should redirect anonymous users
    assert res.status_code in (302, 401, 403)


@pytest.mark.django_db
def test_authenticated_without_rights_gets_403_on_detail(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    # outsider is authenticated but not owner, not org admin, not member
    client.force_login(outsider)
    res = client.get(reverse("surveys:detail", kwargs={"slug": s1.slug}))
    assert res.status_code == 403


@pytest.mark.django_db
def test_authenticated_without_rights_gets_403_on_other_views(
    client, users, org, surveys
):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    client.force_login(outsider)
    # These SSR views should be forbidden to users who lack view/edit rights
    urls = [
        reverse("surveys:preview", kwargs={"slug": s1.slug}),
        reverse("surveys:dashboard", kwargs={"slug": s1.slug}),
        reverse("surveys:groups", kwargs={"slug": s1.slug}),
        reverse("surveys:groups", kwargs={"slug": s1.slug}),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 403


@pytest.mark.django_db
def test_preview_requires_permission(client, users, org, surveys):
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys
    # Creator can preview their own
    login(client, creator)
    assert (
        client.get(reverse("surveys:preview", kwargs={"slug": s1.slug})).status_code
        == 200
    )
    # But not others
    assert (
        client.get(reverse("surveys:preview", kwargs={"slug": s2.slug})).status_code
        == 403
    )


@pytest.mark.django_db
def test_editor_role_permissions(client, users, org, surveys):
    """Test that EDITOR role can edit content but cannot manage users."""
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys

    # Create an editor user and add them as EDITOR to s1
    editor = User.objects.create_user(username="editor", password="x")
    SurveyMembership.objects.create(
        survey=s1, user=editor, role=SurveyMembership.Role.EDITOR
    )

    login(client, editor)

    # EDITOR can access content editing views
    assert (
        client.get(reverse("surveys:dashboard", kwargs={"slug": s1.slug})).status_code
        == 200
    )
    assert (
        client.get(reverse("surveys:preview", kwargs={"slug": s1.slug})).status_code
        == 200
    )
    assert (
        client.get(reverse("surveys:groups", kwargs={"slug": s1.slug})).status_code
        == 200
    )

    # EDITOR cannot access user management views
    assert (
        client.get(
            reverse("surveys:survey_users", kwargs={"slug": s1.slug})
        ).status_code
        == 404
    )

    # EDITOR cannot access surveys they're not a member of
    assert (
        client.get(reverse("surveys:dashboard", kwargs={"slug": s2.slug})).status_code
        == 403
    )


@pytest.mark.django_db
def test_editor_role_dashboard_buttons(client, users, org, surveys):
    """Test that EDITOR sees manage groups button but not manage collaborators button."""
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys

    # Create an editor user and add them as EDITOR to s1
    editor = User.objects.create_user(username="editor", password="x")
    SurveyMembership.objects.create(
        survey=s1, user=editor, role=SurveyMembership.Role.EDITOR
    )

    login(client, editor)
    res = client.get(reverse("surveys:dashboard", kwargs={"slug": s1.slug}))
    assert res.status_code == 200

    content = res.content.decode()
    # EDITOR should see the clickable survey title that links to groups
    assert f'<a class="link link-accent" href="/surveys/{s1.slug}/groups/"' in content
    # EDITOR should NOT see the manage collaborators button
    assert "Manage collaborators" not in content


@pytest.mark.django_db
def test_creator_role_dashboard_buttons(client, users, org, surveys):
    """Test that CREATOR sees both manage groups and manage collaborators buttons."""
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys

    login(client, creator)
    res = client.get(reverse("surveys:dashboard", kwargs={"slug": s1.slug}))
    assert res.status_code == 200

    content = res.content.decode()
    # CREATOR should see the clickable survey title that links to groups
    assert f'<a class="link link-accent" href="/surveys/{s1.slug}/groups/"' in content
    # CREATOR should also see the manage collaborators button
    assert "Manage collaborators" in content


@pytest.mark.django_db
def test_viewer_role_dashboard_limited_access(client, users, org, surveys):
    """Test that VIEWER has limited access to surveys."""
    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys

    # Add viewer as VIEWER to s1
    SurveyMembership.objects.create(
        survey=s1, user=viewer, role=SurveyMembership.Role.VIEWER
    )

    login(client, viewer)

    # VIEWER can access dashboard and preview (read-only)
    assert (
        client.get(reverse("surveys:dashboard", kwargs={"slug": s1.slug})).status_code
        == 200
    )
    assert (
        client.get(reverse("surveys:preview", kwargs={"slug": s1.slug})).status_code
        == 200
    )

    # VIEWER cannot access editing views
    assert (
        client.get(reverse("surveys:groups", kwargs={"slug": s1.slug})).status_code
        == 403
    )
    assert (
        client.get(
            reverse("surveys:survey_users", kwargs={"slug": s1.slug})
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_permission_functions_with_editor_role(db, users, org, surveys):
    """Test the permission functions directly with EDITOR role."""
    from checktick_app.surveys.permissions import (
        can_edit_survey,
        can_manage_survey_users,
    )

    admin, creator, viewer, outsider, participant = users
    s1, s2 = surveys

    # Create an editor user and add them as EDITOR to s1
    editor = User.objects.create_user(username="editor", password="x")
    SurveyMembership.objects.create(
        survey=s1, user=editor, role=SurveyMembership.Role.EDITOR
    )

    # EDITOR can edit survey content
    assert can_edit_survey(editor, s1) is True
    # EDITOR cannot manage survey users
    assert can_manage_survey_users(editor, s1) is False

    # CREATOR can do both
    assert can_edit_survey(creator, s1) is True
    assert can_manage_survey_users(creator, s1) is True

    # VIEWER can do neither
    SurveyMembership.objects.create(
        survey=s1, user=viewer, role=SurveyMembership.Role.VIEWER
    )
    assert can_edit_survey(viewer, s1) is False
    assert can_manage_survey_users(viewer, s1) is False


@pytest.mark.django_db
def test_group_builder_blocks_unauthenticated_users(client, users, org):
    """
    Test that the group builder (which includes Special Templates) is NOT
    accessible to unauthenticated users. This is critical for security.
    """
    admin, creator, viewer, outsider, participant = users

    # Create survey owned by creator
    survey = Survey.objects.create(
        owner=creator, organization=org, name="Test", slug="test"
    )

    # Create a question group
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(name="Test Group", owner=creator)
    survey.question_groups.add(group)

    url = reverse(
        "surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id}
    )

    # Test 1: Anonymous/unauthenticated user must be blocked
    client.logout()
    res = client.get(url)
    assert res.status_code in (
        302,
        401,
        403,
    ), "Unauthenticated users should not be able to access group builder"

    # Test 2: User without edit permissions should be blocked
    client.force_login(viewer)
    SurveyMembership.objects.create(
        survey=survey, user=viewer, role=SurveyMembership.Role.VIEWER
    )
    res = client.get(url)
    assert (
        res.status_code == 403
    ), "Viewer role should not be able to access builder (edit-only)"

    # Test 3: Complete outsider should be blocked
    client.force_login(outsider)
    res = client.get(url)
    assert (
        res.status_code == 403
    ), "Users without any survey membership should not access builder"


@pytest.mark.django_db
def test_group_builder_allows_authorized_users(client, users, org):
    """
    Test that users with edit permissions CAN access the group builder.
    This verifies the positive case - authorized users should see the builder
    including the Special Templates tab.
    """
    admin, creator, viewer, outsider, participant = users

    # Create survey owned by creator
    survey = Survey.objects.create(
        owner=creator, organization=org, name="Test", slug="test"
    )

    # Create a question group
    from checktick_app.surveys.models import QuestionGroup

    group = QuestionGroup.objects.create(name="Test Group", owner=creator)
    survey.question_groups.add(group)

    url = reverse(
        "surveys:group_builder", kwargs={"slug": survey.slug, "gid": group.id}
    )

    # Test 1: Survey owner can access
    client.force_login(creator)
    res = client.get(url)
    assert res.status_code == 200
    assert (
        b'aria-label="Special Templates"' in res.content
    ), "Special Templates tab should be visible to authorized users"

    # Test 2: Org admin can access
    client.force_login(admin)
    res = client.get(url)
    assert res.status_code == 200
    assert b'aria-label="Special Templates"' in res.content

    # Test 3: Survey member with CREATOR role can access
    editor_user = User.objects.create_user(username="editor", password="x")
    SurveyMembership.objects.create(
        survey=survey, user=editor_user, role=SurveyMembership.Role.CREATOR
    )
    client.force_login(editor_user)
    res = client.get(url)
    assert res.status_code == 200
    assert b'aria-label="Special Templates"' in res.content

    # Test 4: Survey member with EDITOR role can access
    editor2 = User.objects.create_user(username="editor2", password="x")
    SurveyMembership.objects.create(
        survey=survey, user=editor2, role=SurveyMembership.Role.EDITOR
    )
    client.force_login(editor2)
    res = client.get(url)
    assert res.status_code == 200
    assert b'aria-label="Special Templates"' in res.content
