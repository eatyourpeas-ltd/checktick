"""Tests for Survey Map pickable badges + preview simulate selection (step 9)."""

from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    Organization,
    QuestionGroup,
    SectionMenu,
    SectionMenuItem,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


@pytest.fixture
def section_menu_survey(owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Menu Survey",
        slug="menu-step9",
        layout=Survey.Layout.SECTION_MENU,
    )
    g1 = QuestionGroup.objects.create(name="Demographics", owner=owner)
    g2 = QuestionGroup.objects.create(name="Medical", owner=owner)
    g3 = QuestionGroup.objects.create(name="Lifestyle", owner=owner)
    s.question_groups.add(g1, g2, g3)
    SurveyQuestion.objects.create(
        survey=s, group=g1, text="Age", type=SurveyQuestion.Types.TEXT, order=0
    )
    SurveyQuestion.objects.create(
        survey=s, group=g2, text="Condition", type=SurveyQuestion.Types.TEXT, order=1
    )
    SurveyQuestion.objects.create(
        survey=s, group=g3, text="Exercise", type=SurveyQuestion.Types.TEXT, order=2
    )
    menu = SectionMenu.objects.create(survey=s, min_selected=1, max_selected=2)
    SectionMenuItem.objects.create(menu=menu, group=g1, is_pickable=False, order=1)
    SectionMenuItem.objects.create(menu=menu, group=g2, is_pickable=True, order=2)
    SectionMenuItem.objects.create(
        menu=menu, group=g3, is_pickable=True, estimated_minutes=3, order=3
    )
    s._g1, s._g2, s._g3 = g1, g2, g3
    return s


# --- Survey Map pickable badges ---


@pytest.mark.django_db
def test_survey_map_shows_pickable_badges(client, owner, section_menu_survey):
    client.force_login(owner)
    res = client.get(
        reverse("surveys:survey_map", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable" in html.lower()
    assert "mandatory" in html.lower()
    assert "Medical" in html
    assert "Demographics" in html


@pytest.mark.django_db
def test_survey_map_no_badges_for_linear(client, owner, org):
    s = Survey.objects.create(
        owner=owner, organization=org, name="Linear", slug="linear-map"
    )
    g = QuestionGroup.objects.create(name="Only", owner=owner)
    s.question_groups.add(g)
    SurveyQuestion.objects.create(
        survey=s, group=g, text="Q", type=SurveyQuestion.Types.TEXT
    )
    client.force_login(owner)
    res = client.get(reverse("surveys:survey_map", kwargs={"slug": s.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "pickable status" not in html.lower()


# --- Preview simulate selection ---


@pytest.mark.django_db
def test_preview_shows_simulate_panel(client, owner, section_menu_survey):
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Simulate section selection" in html
    assert "Medical" in html
    assert "Lifestyle" in html


@pytest.mark.django_db
def test_preview_simulate_filters_questions(client, owner, section_menu_survey):
    """When simulate_groups is set, only selected + mandatory questions appear."""
    client.force_login(owner)
    # Simulate selecting only Medical (g2), not Lifestyle (g3)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
        + f"?simulate_groups={section_menu_survey._g2.id}"
    )
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (mandatory) should appear
    assert "Age" in html
    # Medical (selected) should appear
    assert "Condition" in html
    # Lifestyle (not selected) should NOT appear
    assert "Exercise" not in html


@pytest.mark.django_db
def test_preview_default_shows_mandatory_only(client, owner, section_menu_survey):
    """By default (no simulate_groups), only mandatory sections appear in preview.

    Pickable sections are hidden until the author ticks them in the simulate
    panel, mirroring what a participant sees before making a selection.
    """
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (mandatory) should appear
    assert "Age" in html
    # Medical (pickable) should NOT appear by default
    assert "Condition" not in html
    # Lifestyle (pickable) should NOT appear by default
    assert "Exercise" not in html
    # Reset button should not show when no explicit selection has been made
    assert "Reset" not in html


@pytest.mark.django_db
def test_preview_simulate_estimated_time(client, owner, section_menu_survey):
    """The simulate panel shows estimated time when enabled."""
    section_menu_survey.section_menu.show_estimated_time = True
    section_menu_survey.section_menu.save(update_fields=["show_estimated_time"])
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "~3 min" in html


@pytest.mark.django_db
def test_preview_simulate_multiple_groups_repeated_keys(
    client, owner, section_menu_survey
):
    """Selecting multiple checkboxes (repeated query keys) filters to all selected.

    The simulate panel submits multiple checkboxes all named
    ``simulate_groups``, which the browser serialises as repeated query keys
    (``?simulate_groups=1&simulate_groups=3``). Previously the view used
    ``request.GET.get()`` which only returned the first value, silently
    dropping the rest.
    """
    client.force_login(owner)
    # Simulate selecting both Medical (g2) and Lifestyle (g3) via repeated keys
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
        + f"?simulate_groups={section_menu_survey._g2.id}"
        + f"&simulate_groups={section_menu_survey._g3.id}"
    )
    assert res.status_code == 200
    html = res.content.decode()
    # Demographics (mandatory) should appear
    assert "Age" in html
    # Medical (selected) should appear
    assert "Condition" in html
    # Lifestyle (selected) should appear
    assert "Exercise" in html


@pytest.mark.django_db
def test_preview_simulate_multiple_groups_comma_separated(
    client, owner, section_menu_survey
):
    """Comma-separated simulate_groups values are still supported for shareable URLs."""
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
        + f"?simulate_groups={section_menu_survey._g2.id},{section_menu_survey._g3.id}"
    )
    assert res.status_code == 200
    html = res.content.decode()
    assert "Age" in html
    assert "Condition" in html
    assert "Exercise" in html


@pytest.mark.django_db
def test_preview_simulate_checkbox_state_reflects_selection(
    client, owner, section_menu_survey
):
    """The simulate panel checkboxes stay checked for the selected groups."""
    client.force_login(owner)
    res = client.get(
        reverse("surveys:preview", kwargs={"slug": section_menu_survey.slug})
        + f"?simulate_groups={section_menu_survey._g2.id}"
        + f"&simulate_groups={section_menu_survey._g3.id}"
    )
    assert res.status_code == 200
    html = res.content.decode()
    # Both pickable checkboxes should be checked
    g2_checked = (
        f'value="{section_menu_survey._g2.id}"' in html
        and "checked"
        in html.split(f'value="{section_menu_survey._g2.id}"', 1)[1].split("/>", 1)[0]
    )
    g3_checked = (
        f'value="{section_menu_survey._g3.id}"' in html
        and "checked"
        in html.split(f'value="{section_menu_survey._g3.id}"', 1)[1].split("/>", 1)[0]
    )
    assert g2_checked, "Medical checkbox not checked after selecting it"
    assert g3_checked, "Lifestyle checkbox not checked after selecting it"
    # Reset button should appear once an explicit selection is made
    assert "Reset" in html


# --- Intro / landing content on Section menu picker ---


@pytest.mark.django_db
def test_section_menu_picker_shows_intro(client, owner, org, section_menu_survey):
    """When intro_content is set, it renders above the picker prompt."""
    section_menu_survey.status = Survey.Status.PUBLISHED
    section_menu_survey.visibility = Survey.Visibility.AUTHENTICATED
    section_menu_survey.allow_any_authenticated = True
    section_menu_survey.save(
        update_fields=["status", "visibility", "allow_any_authenticated"]
    )

    section_menu_survey.section_menu.intro_content = {
        "heading": "Welcome",
        "body_md": "Please read this.",
    }
    section_menu_survey.section_menu.save(update_fields=["intro_content"])

    from django.contrib.auth.models import User

    participant = User.objects.create_user(
        username="picker_intro", password=TEST_PASSWORD
    )
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": section_menu_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Welcome" in html
    assert "Please read this." in html


@pytest.mark.django_db
def test_section_menu_picker_no_intro_by_default(
    client, owner, org, section_menu_survey
):
    """Without intro_content, the picker renders normally (no intro)."""
    section_menu_survey.status = Survey.Status.PUBLISHED
    section_menu_survey.visibility = Survey.Visibility.AUTHENTICATED
    section_menu_survey.allow_any_authenticated = True
    section_menu_survey.save(
        update_fields=["status", "visibility", "allow_any_authenticated"]
    )

    from django.contrib.auth.models import User

    participant = User.objects.create_user(
        username="picker_nointro", password=TEST_PASSWORD
    )
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": section_menu_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Which sections" in html
    assert 'class="content-block prose' not in html


@pytest.mark.django_db
def test_section_menu_save_intro(client, owner, section_menu_survey):
    """Saving the config form with intro fields persists intro_content."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_subtitle": "",
            "intro_body_md": "Please read this.",
            "intro_link_labels": ["Privacy"],
            "intro_link_urls": ["https://example.com/privacy"],
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    assert intro is not None
    assert intro["heading"] == "Welcome"
    assert intro["body_md"] == "Please read this."
    assert intro["links"] == [
        {"label": "Privacy", "url": "https://example.com/privacy"}
    ]


@pytest.mark.django_db
def test_section_menu_save_clears_intro(client, owner, section_menu_survey):
    """Unchecking intro_enabled clears intro_content."""
    section_menu_survey.section_menu.intro_content = {"heading": "Old"}
    section_menu_survey.section_menu.save(update_fields=["intro_content"])

    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            # intro_enabled not submitted = unchecked
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    assert section_menu_survey.section_menu.intro_content is None


@pytest.mark.django_db
def test_section_menu_save_intro_with_image(client, owner, section_menu_survey):
    """Saving with an image URL stores it in intro_content."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_subtitle": "",
            "intro_body_md": "",
            "intro_image_url": "/media/intro_images/test/logo.png",
            "intro_image_alt": "Logo",
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    assert intro["image_url"] == "/media/intro_images/test/logo.png"
    assert intro["image_alt"] == "Logo"


@pytest.mark.django_db
def test_section_menu_picker_renders_image(client, owner, org, section_menu_survey):
    """The intro image renders in the picker page."""
    section_menu_survey.status = Survey.Status.PUBLISHED
    section_menu_survey.visibility = Survey.Visibility.AUTHENTICATED
    section_menu_survey.allow_any_authenticated = True
    section_menu_survey.save(
        update_fields=["status", "visibility", "allow_any_authenticated"]
    )
    section_menu_survey.section_menu.intro_content = {
        "heading": "Welcome",
        "image_url": "/media/intro_images/test/logo.png",
        "image_alt": "Study logo",
    }
    section_menu_survey.section_menu.save(update_fields=["intro_content"])

    from django.contrib.auth.models import User

    participant = User.objects.create_user(
        username="picker_img", password=TEST_PASSWORD
    )
    client.force_login(participant)
    res = client.get(reverse("surveys:take", kwargs={"slug": section_menu_survey.slug}))
    assert res.status_code == 200
    html = res.content.decode()
    assert "/media/intro_images/test/logo.png" in html
    assert "Study logo" in html


@pytest.mark.django_db
def test_section_menu_intro_image_upload(client, owner, section_menu_survey):
    """The image upload endpoint stores the file and returns a URL."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(owner)
    # Create a minimal valid PNG (1x1 pixel)
    import struct
    import zlib

    def _minimal_png():
        header = b"\x89PNG\r\n\x1a\n"
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        ihdr = b"IHDR" + ihdr_data
        ihdr_chunk = (
            struct.pack(">I", len(ihdr_data))
            + ihdr
            + struct.pack(">I", zlib.crc32(ihdr) & 0xFFFFFFFF)
        )
        idat_data = zlib.compress(b"\x00\xff\x00\x00")
        idat = b"IDAT" + idat_data
        idat_chunk = (
            struct.pack(">I", len(idat_data))
            + idat
            + struct.pack(">I", zlib.crc32(idat) & 0xFFFFFFFF)
        )
        iend = b"IEND"
        iend_chunk = (
            struct.pack(">I", 0)
            + iend
            + struct.pack(">I", zlib.crc32(iend) & 0xFFFFFFFF)
        )
        return header + ihdr_chunk + idat_chunk + iend_chunk

    img = SimpleUploadedFile("test.png", _minimal_png(), content_type="image/png")
    res = client.post(
        reverse(
            "surveys:section_menu_intro_image_upload",
            kwargs={"slug": section_menu_survey.slug},
        ),
        {"image": img, "alt": "Test logo"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["image_url"].startswith("/media/intro_images/")
    assert data["alt"] == "Test logo"


@pytest.mark.django_db
def test_section_menu_intro_rejects_javascript_link_url(
    client, owner, section_menu_survey
):
    """Link URLs with javascript: scheme are stripped at save time."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_body_md": "",
            "intro_link_labels": ["Evil"],
            "intro_link_urls": ["javascript:alert(1)"],
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    # The javascript: URL should have been stripped — link dropped entirely
    assert intro["links"] == []


@pytest.mark.django_db
def test_section_menu_intro_rejects_javascript_image_url(
    client, owner, section_menu_survey
):
    """Image URLs with javascript: scheme are stripped at save time."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_body_md": "",
            "intro_image_url": "javascript:alert(1)",
            "intro_image_alt": "",
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    assert intro["image_url"] == ""


@pytest.mark.django_db
def test_section_menu_intro_rejects_data_uri_image_url(
    client, owner, section_menu_survey
):
    """Image URLs with data: scheme are stripped at save time."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_body_md": "",
            "intro_image_url": "data:text/html,<script>alert(1)</script>",
            "intro_image_alt": "",
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    assert intro["image_url"] == ""


@pytest.mark.django_db
def test_section_menu_intro_accepts_relative_image_url(
    client, owner, section_menu_survey
):
    """Relative image URLs (e.g. /media/...) are allowed."""
    client.force_login(owner)
    res = client.post(
        reverse("surveys:groups", kwargs={"slug": section_menu_survey.slug}),
        {
            "action": "save_section_menu",
            "prompt_text": "Pick sections",
            "min_selected": "1",
            "max_selected": "",
            "order_mode": "authored",
            "intro_enabled": "1",
            "intro_heading": "Welcome",
            "intro_body_md": "",
            "intro_image_url": "/media/intro_images/test/logo.png",
            "intro_image_alt": "Logo",
        },
        follow=False,
    )
    assert res.status_code == 302
    section_menu_survey.section_menu.refresh_from_db()
    intro = section_menu_survey.section_menu.intro_content
    assert intro["image_url"] == "/media/intro_images/test/logo.png"
