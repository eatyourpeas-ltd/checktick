from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from checktick_app.surveys.models import QuestionGroup, Survey, SurveyAccessToken


def create_published_survey_for_testing(survey, end_date=None):
    """Helper function to create a properly published survey for testing"""
    if end_date is None:
        end_date = timezone.now() + timedelta(days=30)

    survey.status = Survey.Status.PUBLISHED
    survey.visibility = "authenticated"
    survey.end_at = end_date
    survey.published_at = timezone.now()
    survey.start_at = timezone.now()
    # Set a dummy encryption key for testing
    survey.encrypted_key = b"dummy_key_data"
    survey.save()
    return survey


@pytest.mark.django_db
def test_authenticated_required_when_patient_data(client, django_user_model):
    owner = django_user_model.objects.create_user(username="owner", password="p")
    _ = django_user_model.objects.create_user(username="participant", password="p")
    s = Survey.objects.create(owner=owner, name="S", slug="s")
    # Attach a patient details group with fields
    g = QuestionGroup.objects.create(
        owner=owner,
        name="Patient details",
        schema={"template": "patient_details_encrypted", "fields": ["first_name"]},
    )
    s.question_groups.add(g)

    s.status = Survey.Status.PUBLISHED
    s.visibility = Survey.Visibility.PUBLIC
    s.no_patient_data_ack = False
    s.save()

    # Login as participant (not owner)
    client.login(username="participant", password="p")
    # Public take should 404 due to patient data and no ack
    resp = client.get(reverse("surveys:take", kwargs={"slug": s.slug}))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_unlisted_link_flow(client, django_user_model):
    user = django_user_model.objects.create_user(username="u2", password="p")
    client.login(username="u2", password="p")
    s = Survey.objects.create(
        owner=user,
        name="S2",
        slug="s2",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.UNLISTED,
    )
    s.unlisted_key = "abc123"
    s.save()
    resp = client.get(
        reverse("surveys:take_unlisted", kwargs={"slug": s.slug, "key": s.unlisted_key})
    )
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_token_one_time_use(client, django_user_model):
    user = django_user_model.objects.create_user(username="u3", password="p")
    s = Survey.objects.create(
        owner=user,
        name="S3",
        slug="s3",
        status=Survey.Status.PUBLISHED,
        visibility=Survey.Visibility.TOKEN,
    )
    tok = SurveyAccessToken.objects.create(survey=s, token="tok123", created_by=user)

    # First GET loads
    resp = client.get(
        reverse("surveys:take_token", kwargs={"slug": s.slug, "token": tok.token})
    )
    assert resp.status_code in (200, 302)

    # Simulate a submit (no fields)
    resp = client.post(
        reverse("surveys:take_token", kwargs={"slug": s.slug, "token": tok.token}), {}
    )
    assert resp.status_code in (302,)

    tok.refresh_from_db()
    assert tok.used_at is not None

    # Second submit should redirect to closed page
    resp = client.post(
        reverse("surveys:take_token", kwargs={"slug": s.slug, "token": tok.token}), {}
    )
    assert resp.status_code == 302
    assert "/closed/" in resp.url
    assert "reason=token_used" in resp.url


@pytest.mark.django_db
def test_survey_close_and_reopen(client, django_user_model):
    """Test closing and reopening a survey through publish settings"""
    user = django_user_model.objects.create_user(username="testuser", password="p")
    client.login(username="testuser", password="p")

    # Create survey with questions
    s = Survey.objects.create(
        owner=user,
        name="Test Survey",
        slug="test-survey",
        status=Survey.Status.DRAFT,
    )

    # Add a question group
    g = QuestionGroup.objects.create(
        owner=user,
        name="Test Group",
        schema={"fields": [{"type": "text", "label": "Test Question"}]},
    )
    s.question_groups.add(g)

    # For testing purposes, directly set up a published survey
    end_date = timezone.now() + timedelta(days=30)
    s = create_published_survey_for_testing(s, end_date)

    # Verify survey is published
    s.refresh_from_db()
    assert s.status == Survey.Status.PUBLISHED
    assert s.is_closed is False

    # Close survey
    publish_url = reverse("surveys:publish_settings", kwargs={"slug": s.slug})
    close_data = {
        "action": "close",
    }

    response = client.post(publish_url, close_data)
    assert response.status_code == 302

    s.refresh_from_db()
    assert s.status == Survey.Status.CLOSED
    assert s.is_closed is True
    assert s.closed_at is not None

    # Reopen survey
    reopen_data = {
        "action": "reopen",
    }

    response = client.post(publish_url, reopen_data)
    assert response.status_code == 302

    s.refresh_from_db()
    assert s.status == Survey.Status.PUBLISHED
    assert s.is_closed is False
    assert s.closed_at is None


@pytest.mark.django_db
def test_survey_extend_end_date(client, django_user_model):
    """Test extending end date of a closed survey"""
    # Create user and login
    user = django_user_model.objects.create_user(
        username="testuser2", password="password123"
    )
    client.login(username="testuser2", password="password123")

    # Create survey with questions
    s = Survey.objects.create(
        owner=user,
        name="Test Survey 2",
        slug="test-survey-2",
        status=Survey.Status.DRAFT,
    )

    # Add a question group to make survey publishable
    g = QuestionGroup.objects.create(
        owner=user,
        name="Test Group 2",
        schema={"fields": [{"type": "text", "label": "Test Question 2"}]},
    )
    s.question_groups.add(g)

    # For testing purposes, directly set up a published survey
    end_date = timezone.now() + timedelta(days=30)
    s = create_published_survey_for_testing(s, end_date)

    # Close survey
    publish_url = reverse("surveys:publish_settings", kwargs={"slug": s.slug})
    close_data = {
        "action": "close",
    }
    client.post(publish_url, close_data)
    s.refresh_from_db()

    # Extend end date by saving changes
    new_end_date = timezone.now() + timedelta(days=45)
    extend_data = {
        "action": "save",
        "visibility": "authenticated",
        "start_at": s.start_at.strftime("%Y-%m-%dT%H:%M") if s.start_at else "",
        "end_at": new_end_date.strftime("%Y-%m-%dT%H:%M"),
        "max_responses": "",
        "captcha_required": "on",
        "no_patient_data_ack": "on",
    }

    response = client.post(publish_url, extend_data)
    assert response.status_code == 302  # Redirect to dashboard

    # Refresh survey from database
    s.refresh_from_db()
    # When we save changes to a closed survey, it should remain closed
    # The save action doesn't change the status, only the fields
    assert s.status == Survey.Status.CLOSED
    assert s.end_at.date() == new_end_date.date()
    assert s.is_closed is True  # Survey remains closed but with updated end date


@pytest.mark.django_db
def test_start_date_disabled_after_publish(client, django_user_model):
    """Test that start date field is disabled after first publish"""
    user = django_user_model.objects.create_user(username="testuser3", password="p")
    client.login(username="testuser3", password="p")

    # Create survey with questions
    s = Survey.objects.create(
        owner=user,
        name="Test Survey 3",
        slug="test-survey-3",
        status=Survey.Status.DRAFT,
    )

    # Add a question group
    g = QuestionGroup.objects.create(
        owner=user,
        name="Test Group 3",
        schema={"fields": [{"type": "text", "label": "Test Question 3"}]},
    )
    s.question_groups.add(g)

    # For testing purposes, directly set up a published survey
    end_date = timezone.now() + timedelta(days=30)
    s = create_published_survey_for_testing(s, end_date)

    # Close survey to test closed state
    publish_url = reverse("surveys:publish_settings", kwargs={"slug": s.slug})
    close_data = {
        "action": "close",
    }
    client.post(publish_url, close_data)
    s.refresh_from_db()

    # Check publish settings form for closed survey
    response = client.get(publish_url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show warning about closed survey
    assert "Survey Closed" in content
    # Start date should still be disabled
    assert "disabled" in content or "Start date cannot be changed" in content
    # Should show reopen button
    assert "Reopen Survey" in content


@pytest.mark.django_db
def test_dashboard_displays_correct_buttons(client, django_user_model):
    """Test that dashboard shows correct buttons for published and closed surveys"""
    # Create user and login
    user = django_user_model.objects.create_user(
        username="testuser4", password="password123"
    )
    client.login(username="testuser4", password="password123")

    # Create survey with questions
    s = Survey.objects.create(
        owner=user,
        name="Test Survey 4",
        slug="test-survey-4",
        status=Survey.Status.DRAFT,
    )

    # Add a question group to make survey publishable
    g = QuestionGroup.objects.create(
        owner=user,
        name="Test Group 4",
        schema={"fields": [{"type": "text", "label": "Test Question 4"}]},
    )
    s.question_groups.add(g)

    # For testing purposes, directly set up a published survey
    end_date = timezone.now() + timedelta(days=30)
    s = create_published_survey_for_testing(s, end_date)

    # Check dashboard shows published status
    dashboard_url = reverse("surveys:dashboard", kwargs={"slug": s.slug})
    response = client.get(dashboard_url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    # Should show edit publication button
    assert "Edit Publication" in content or "Edit" in content

    # Close survey
    publish_url = reverse("surveys:publish_settings", kwargs={"slug": s.slug})
    close_data = {
        "action": "close",
    }
    client.post(publish_url, close_data)
    s.refresh_from_db()

    # Check dashboard shows closed status
    response = client.get(dashboard_url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    # Should show reopen button
    assert "Reopen" in content
    assert "Closed" in content

    # Reopen survey
    reopen_data = {
        "action": "reopen",
    }
    client.post(publish_url, reopen_data)
    s.refresh_from_db()

    # Check dashboard shows published status again
    response = client.get(dashboard_url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    # Should show edit option again
    assert "Edit" in content or "Publish" in content
