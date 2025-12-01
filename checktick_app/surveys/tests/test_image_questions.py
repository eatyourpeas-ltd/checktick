"""
Tests for image choice questions.

WARNING: Images are NOT encrypted and should only be used for
non-medical, non-patient-identifying content.
"""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
import pytest

from checktick_app.surveys.models import (
    QuestionImage,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)

# Use simple test password to avoid hardcoded password warnings
TEST_PASSWORD = "x"


@pytest.fixture
def survey(db, django_user_model):
    """Create a basic survey with an owner."""
    user = django_user_model.objects.create_user(
        username="testuser", password=TEST_PASSWORD, email="test@example.com"
    )
    survey = Survey.objects.create(
        name="Test Survey",
        slug="test-survey",
        owner=user,
    )
    return survey


@pytest.fixture
def image_question(survey):
    """Create an image choice question."""
    return SurveyQuestion.objects.create(
        survey=survey,
        text="Select an image",
        type=SurveyQuestion.Types.IMAGE_CHOICE,
        order=0,
    )


@pytest.fixture
def sample_image():
    """Create a simple valid image file."""
    # Create a simple 1x1 pixel PNG
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return SimpleUploadedFile("test.png", buffer.read(), content_type="image/png")


@pytest.fixture
def large_image():
    """Create an image that exceeds the size limit (>1MB)."""
    # Create a file with more than 1MB of data
    # A simple approach: repeat image data until it's over 1MB
    data = b"x" * (1024 * 1024 + 1)  # 1MB + 1 byte
    return SimpleUploadedFile("large.png", data, content_type="image/png")


class TestQuestionImageModel:
    """Tests for the QuestionImage model."""

    def test_create_question_image(self, image_question, sample_image):
        """Test creating a QuestionImage."""
        img = QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Red Square",
            order=0,
        )
        assert img.pk is not None
        assert img.question == image_question
        assert img.label == "Red Square"
        assert img.order == 0
        assert img.image.url is not None

    def test_question_image_ordering(self, image_question, sample_image):
        """Test that images are ordered by order field then id."""
        img2 = QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Second",
            order=1,
        )
        # Create another sample image for first
        from PIL import Image

        img_file = Image.new("RGB", (100, 100), color="green")
        buffer = io.BytesIO()
        img_file.save(buffer, format="PNG")
        buffer.seek(0)
        first_image = SimpleUploadedFile(
            "test2.png", buffer.read(), content_type="image/png"
        )

        img1 = QuestionImage.objects.create(
            question=image_question,
            image=first_image,
            label="First",
            order=0,
        )

        images = list(image_question.images.all())
        assert images[0] == img1
        assert images[1] == img2

    def test_cascade_delete(self, image_question, sample_image):
        """Test that deleting a question deletes its images."""
        QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Test",
            order=0,
        )
        question_id = image_question.id
        image_question.delete()
        assert QuestionImage.objects.filter(question_id=question_id).count() == 0


class TestImageUploadView:
    """Tests for the image upload endpoint."""

    def test_upload_requires_authentication(self, client, image_question):
        """Test that unauthenticated users cannot upload images."""
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url)
        assert response.status_code == 302  # Redirect to login

    def test_upload_requires_edit_permission(
        self, client, image_question, django_user_model
    ):
        """Test that users without edit permission cannot upload."""
        django_user_model.objects.create_user(
            username="other", password=TEST_PASSWORD, email="other@example.com"
        )
        client.login(username="other", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url)
        assert response.status_code == 403

    def test_upload_success(self, client, image_question, sample_image):
        """Test successful image upload."""
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url, {"image": sample_image, "label": "My Image"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "image" in data
        assert data["image"]["label"] == "My Image"

        # Verify the image was created
        assert image_question.images.count() == 1
        img = image_question.images.first()
        assert img.label == "My Image"

    def test_upload_no_image(self, client, image_question):
        """Test upload fails without an image file."""
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url, {"label": "No Image"})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "No image file" in data["error"]

    def test_upload_rejects_large_file(self, client, image_question, large_image):
        """Test that files larger than 1MB are rejected."""
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url, {"image": large_image, "label": "Large"})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "1MB" in data["error"]

    def test_upload_rejects_non_image(self, client, image_question):
        """Test that non-image files are rejected."""
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        fake_file = SimpleUploadedFile(
            "test.txt", b"not an image", content_type="text/plain"
        )
        response = client.post(url, {"image": fake_file, "label": "Not Image"})
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False


class TestImageDeleteView:
    """Tests for the image delete endpoint."""

    def test_delete_requires_authentication(self, client, image_question, sample_image):
        """Test that unauthenticated users cannot delete images."""
        img = QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Test",
            order=0,
        )
        url = reverse(
            "surveys:builder_question_image_delete",
            kwargs={
                "slug": image_question.survey.slug,
                "qid": image_question.id,
                "img_id": img.id,
            },
        )
        response = client.post(url)
        assert response.status_code == 302

    def test_delete_success(self, client, image_question, sample_image):
        """Test successful image deletion."""
        img = QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Test",
            order=0,
        )
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_delete",
            kwargs={
                "slug": image_question.survey.slug,
                "qid": image_question.id,
                "img_id": img.id,
            },
        )
        response = client.post(url)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert not QuestionImage.objects.filter(id=img.id).exists()

    def test_delete_nonexistent_image(self, client, image_question):
        """Test deleting a non-existent image returns 404."""
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_delete",
            kwargs={
                "slug": image_question.survey.slug,
                "qid": image_question.id,
                "img_id": 99999,
            },
        )
        response = client.post(url)
        assert response.status_code == 404


class TestImageQuestionInSurvey:
    """Tests for image questions in the survey flow."""

    def test_image_question_preview(self, client, image_question, sample_image):
        """Test that image questions render in preview."""
        QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Option 1",
            order=0,
        )
        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse("surveys:preview", kwargs={"slug": image_question.survey.slug})
        response = client.get(url)
        assert response.status_code == 200
        assert b"Option 1" in response.content

    def test_submit_image_choice(self, client, image_question, sample_image):
        """Test submitting a response with an image choice."""
        img = QuestionImage.objects.create(
            question=image_question,
            image=sample_image,
            label="Selected",
            order=0,
        )

        # Add membership so user can submit (use SurveyMembership, not Collaborator)
        from django.contrib.auth import get_user_model

        from checktick_app.surveys.models import SurveyMembership

        User = get_user_model()
        respondent = User.objects.create_user(
            username="respondent", password=TEST_PASSWORD, email="resp@example.com"
        )
        SurveyMembership.objects.create(
            survey=image_question.survey,
            user=respondent,
            role=SurveyMembership.Role.VIEWER,
        )

        client.login(username="respondent", password=TEST_PASSWORD)
        url = reverse("surveys:detail", kwargs={"slug": image_question.survey.slug})
        response = client.post(url, {f"q_{image_question.id}": str(img.id)})
        # Should redirect after successful submission
        assert response.status_code == 302

        # Verify the response was saved
        survey_response = SurveyResponse.objects.filter(
            survey=image_question.survey
        ).first()
        assert survey_response is not None
        assert str(image_question.id) in survey_response.answers
        assert survey_response.answers[str(image_question.id)] == str(img.id)


class TestImageResizing:
    """Tests for image resizing functionality."""

    def test_large_dimensions_resized(self, client, image_question):
        """Test that images larger than 800x800 are resized."""
        from PIL import Image

        # Create a large image (1000x1000)
        img = Image.new("RGB", (1000, 1000), color="green")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        large_dim_image = SimpleUploadedFile(
            "big.png", buffer.read(), content_type="image/png"
        )

        client.login(username="testuser", password=TEST_PASSWORD)
        url = reverse(
            "surveys:builder_question_image_upload",
            kwargs={"slug": image_question.survey.slug, "qid": image_question.id},
        )
        response = client.post(url, {"image": large_dim_image, "label": "Resized"})
        assert response.status_code == 200

        # Verify the image was created and resized
        question_img = image_question.images.first()
        assert question_img is not None
        # Open and check dimensions
        img = Image.open(question_img.image)
        assert img.width <= 800
        assert img.height <= 800
