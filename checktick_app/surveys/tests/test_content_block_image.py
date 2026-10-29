"""Tests for content block image upload in the builder configure form.

The original "Upload Image" affordance was a plain <a href> link to the
POST-only JSON image-upload endpoint, so clicking it 405'd in every
environment (dev and production alike — nothing to do with media
volumes). Worse, even a correct POST would not have displayed the image:
the endpoint created a QuestionImage row but never set the
``options.image_id`` the content block renderer reads.

The image is now uploaded as part of the content block configure form
(multipart htmx post), with replace/remove semantics, and validation
errors are surfaced inline in the re-rendered row.
"""

import base64

import pytest

from checktick_app.surveys.models import (
    QuestionGroup,
    QuestionImage,
    Survey,
    SurveyQuestion,
)

TEST_PASSWORD = "x"

# Minimal valid 1x1 PNG.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )


@pytest.fixture
def survey(owner):
    return Survey.objects.create(owner=owner, name="S", slug="cbimg")


@pytest.fixture
def group(owner, survey):
    g = QuestionGroup.objects.create(name="Intro", owner=owner)
    survey.question_groups.add(g)
    return g


@pytest.fixture
def block(survey, group):
    return SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Welcome",
        type=SurveyQuestion.Types.CONTENT_BLOCK,
        options={"heading": "", "body_md": "", "links": [], "render_once": True},
        order=0,
    )


def _configure_url(survey, group, q):
    return (
        f"/surveys/{survey.slug}/builder/groups/{group.id}"
        f"/questions/{q.id}/template/content_block"
    )


def _builder_url(survey, group):
    return f"/surveys/{survey.slug}/builder/?gid={group.id}"


def _png(name="logo.png"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, PNG_1PX, content_type="image/png")


@pytest.mark.django_db
def test_configure_form_uploads_image(client, owner, survey, group, block):
    client.force_login(owner)
    res = client.post(
        _configure_url(survey, group, block),
        {"heading": "Welcome", "content_block_image": _png()},
    )
    assert res.status_code == 200
    block.refresh_from_db()
    image = QuestionImage.objects.get(question=block)
    assert block.options["image_id"] == image.id
    # The rest of the form saved too.
    assert block.options["heading"] == "Welcome"
    # The re-rendered row reflects the new state, with a thumbnail.
    html = res.content.decode()
    assert "Image set" in html
    assert image.image.url in html
    assert "Content block image preview" in html


@pytest.mark.django_db
def test_configure_form_replaces_previous_image(client, owner, survey, group, block):
    client.force_login(owner)
    client.post(
        _configure_url(survey, group, block), {"content_block_image": _png("a.png")}
    )
    client.post(
        _configure_url(survey, group, block), {"content_block_image": _png("b.png")}
    )
    block.refresh_from_db()
    # Only the latest image remains — the replaced row is deleted so
    # storage does not accumulate unreachable files.
    images = list(QuestionImage.objects.filter(question=block))
    assert len(images) == 1
    assert block.options["image_id"] == images[0].id


@pytest.mark.django_db
def test_configure_form_remove_image(client, owner, survey, group, block):
    client.force_login(owner)
    client.post(_configure_url(survey, group, block), {"content_block_image": _png()})
    block.refresh_from_db()
    assert block.options["image_id"] is not None

    res = client.post(_configure_url(survey, group, block), {"remove_image": "on"})
    assert res.status_code == 200
    block.refresh_from_db()
    assert block.options["image_id"] is None
    assert not QuestionImage.objects.filter(question=block).exists()


@pytest.mark.django_db
def test_configure_form_invalid_image_keeps_existing_and_shows_error(
    client, owner, survey, group, block
):
    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(owner)
    client.post(_configure_url(survey, group, block), {"content_block_image": _png()})
    block.refresh_from_db()
    original_image_id = block.options["image_id"]

    bad = SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")
    res = client.post(
        _configure_url(survey, group, block),
        {"heading": "H", "content_block_image": bad},
    )
    assert res.status_code == 200
    block.refresh_from_db()
    # Existing image kept; the rest of the form still saved.
    assert block.options["image_id"] == original_image_id
    assert block.options["heading"] == "H"
    # The validation error is surfaced in the re-rendered row.
    html = res.content.decode()
    assert "alert-error" in html


@pytest.mark.django_db
def test_row_has_file_input_and_no_dead_upload_link(
    client, owner, survey, group, block
):
    client.force_login(owner)
    res = client.get(_builder_url(survey, group))
    assert res.status_code == 200
    html = res.content.decode()
    # The real upload control is part of the configure form.
    assert 'name="content_block_image"' in html
    # The old GET link to the POST-only endpoint is gone.
    dead_link = (
        f"/surveys/{survey.slug}/builder/groups/{group.id}"
        f"/questions/{block.id}/images/upload"
    )
    assert dead_link not in html


@pytest.mark.django_db
def test_builder_page_shows_thumbnail(client, owner, survey, group, block):
    """After upload, a full builder page reload shows the thumbnail too
    (the image is batch-resolved in _prepare_question_rendering)."""
    client.force_login(owner)
    client.post(_configure_url(survey, group, block), {"content_block_image": _png()})
    image = QuestionImage.objects.get(question=block)
    res = client.get(_builder_url(survey, group))
    assert res.status_code == 200
    html = res.content.decode()
    assert image.image.url in html
    assert "Content block image preview" in html
    # The builder mini-preview caps the image too.
    assert "max-h-24" in html


@pytest.mark.django_db
def test_take_page_renders_capped_top_right_image(client, owner, survey, group, block):
    """The live/preview render caps the image and places it top-right
    (heading/subtitle left) instead of letting a full-size image swamp the
    card. The preview route renders the same detail.html as the live take
    route."""
    client.force_login(owner)
    client.post(_configure_url(survey, group, block), {"content_block_image": _png()})
    image = QuestionImage.objects.get(question=block)
    res = client.get(f"/surveys/{survey.slug}/preview/")
    assert res.status_code == 200
    html = res.content.decode()
    assert image.image.url in html
    assert "max-h-28" in html
    assert "justify-between" in html


@pytest.mark.django_db
def test_dangling_image_id_shows_warning_and_remove(
    client, owner, survey, group, block
):
    """An image_id whose QuestionImage row is gone (e.g. removed from
    storage) shows a warning and still offers Remove, and never renders
    another question's image."""
    client.force_login(owner)
    block.options = {**block.options, "image_id": 999999}
    block.save(update_fields=["options"])
    res = client.get(_builder_url(survey, group))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Image missing" in html
    assert 'name="remove_image"' in html
    assert "Content block image preview" not in html


@pytest.mark.django_db
def test_builder_hints_at_content_blocks(client, owner, survey, group):
    """The Build-a-Question tab points authors at content blocks, which
    otherwise only appear under Special Templates."""
    client.force_login(owner)
    res = client.get(_builder_url(survey, group))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Special Templates" in html
    assert "closing acknowledgement" in html
    assert "Content block" in html
