"""Tests for the UK postcode → address lookup feature.

Covers the lookup service (postcodes.io-compatible API), the HTMX endpoint,
builder option persistence, respondent rendering, and answer capture in
survey_detail. The postcode lookup API is mocked throughout; no test should
hit the network.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
import pytest
import requests

from checktick_app.surveys.models import (
    QuestionGroup,
    Survey,
    SurveyQuestion,
    SurveyResponse,
)
from checktick_app.surveys.services.address_lookup import (
    AddressLookupResult,
    AddressLookupService,
)

TWO_ADDRESSES = [
    {
        "line_1": "1 High Street",
        "line_2": "",
        "line_3": "",
        "post_town": "LONDON",
        "county": "Greater London",
        "postcode": "SW1A 1AA",
    },
    {
        "line_1": "2 High Street",
        "line_2": "Flat B",
        "line_3": "Rear Entrance",
        "post_town": "LONDON",
        "county": "",
        "postcode": "SW1A 1AA",
    },
]


def _service_response(status_code=200, payload=None):
    patcher = patch("checktick_app.surveys.services.address_lookup.requests.get")
    mock = patcher.start()
    mock.return_value.status_code = status_code
    mock.return_value.json.return_value = payload if payload is not None else {}
    return patcher, mock


@pytest.fixture
def pro_owner(db):
    owner = User.objects.create_user(username="al_owner", password="x")
    from checktick_app.core.models import UserProfile

    owner.profile.account_tier = UserProfile.AccountTier.PRO
    owner.profile.save()
    return owner


@pytest.fixture
def respondent(db):
    return User.objects.create_user(username="al_respondent", password="x")


@pytest.fixture
def patient_template_survey(pro_owner, respondent):
    """Survey with a patient template question (post_code + address lookup)."""
    survey = Survey.objects.create(
        owner=pro_owner,
        name="Address Lookup Survey",
        slug="address-lookup-survey",
        visibility=Survey.Visibility.AUTHENTICATED,
        status=Survey.Status.PUBLISHED,
    )
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(
        survey=survey, user=respondent, role=SurveyMembership.Role.VIEWER
    )
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Patient details (encrypted)",
        type=SurveyQuestion.Types.TEMPLATE_PATIENT,
        options={
            "template": "patient_details_encrypted",
            "fields": [
                {"key": "first_name", "label": "First name", "selected": True},
                {"key": "post_code", "label": "Post code", "selected": True},
            ],
            "include_imd": False,
            "address_lookup": True,
        },
        order=1,
    )
    return survey, question


# ============================================================================
# Service tests
# ============================================================================


@pytest.mark.django_db
class TestAddressLookupService:
    @pytest.fixture(autouse=True)
    def _ignore_env_address_api(self, settings):
        """Neutralise real env-provided lookup config so each test controls
        its own settings (override_settings in a test wins over this)."""
        settings.ADDRESS_LOOKUP_API_URL = None
        settings.ADDRESS_LOOKUP_API_KEY = None

    def test_lookup_multiple_addresses(self):
        patcher, mock = _service_response(
            payload={"status": 200, "result": TWO_ADDRESSES}
        )
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert result.is_valid
        assert len(result.addresses) == 2
        assert result.addresses[0]["line_1"] == "1 High Street"
        assert result.addresses[0]["town_city"] == "LONDON"
        assert mock.called
        # Postcode is normalised (spaces stripped) in the request URL
        assert "SW1A1AA" in mock.call_args[0][0]

    def test_lookup_normalises_fields(self):
        patcher, _mock = _service_response(
            payload={"status": 200, "result": [TWO_ADDRESSES[1]]}
        )
        result = AddressLookupService.lookup("sw1a 1aa")
        patcher.stop()
        addr = result.addresses[0]
        assert addr["line_1"] == "2 High Street"
        assert addr["line_2"] == "Flat B Rear Entrance"
        assert addr["town_city"] == "LONDON"
        assert addr["county"] == ""
        assert "2 High Street" in addr["summary"]

    def test_lookup_single_dict_result(self):
        # Some proxies return a single object rather than a list
        patcher, _mock = _service_response(
            payload={"status": 200, "result": TWO_ADDRESSES[0]}
        )
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert result.is_valid
        assert len(result.addresses) == 1

    def test_lookup_404_returns_friendly_error(self):
        patcher, _mock = _service_response(status_code=404)
        result = AddressLookupService.lookup("BT1 1AA")
        patcher.stop()
        assert not result.is_valid
        assert "No addresses found" in result.error

    def test_lookup_timeout(self):
        patcher = patch(
            "checktick_app.surveys.services.address_lookup.requests.get",
            side_effect=requests.exceptions.Timeout,
        )
        patcher.start()
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert not result.is_valid
        assert result.error == "Lookup timed out"

    def test_lookup_empty_postcode(self):
        result = AddressLookupService.lookup("  ")
        assert not result.is_valid
        assert result.error == "Empty postcode"

    @override_settings(POSTCODES_API_URL="")
    def test_lookup_not_configured(self):
        result = AddressLookupService.lookup("SW1A 1AA")
        assert not result.is_valid
        assert result.error == "Address lookup not configured"

    @override_settings(
        ADDRESS_LOOKUP_API_URL="https://api.os.uk/search/places/v1/find",
        ADDRESS_LOOKUP_API_KEY="addr-key",
    )
    def test_address_api_overrides_postcodes_api(self):
        patcher, mock = _service_response(
            payload={
                "results": [
                    {
                        "DPA": {
                            "ADDRESS": "10 DOWNING STREET, WESTMINSTER, LONDON, SW1A 1AA",
                            "POST_TOWN": "LONDON",
                            "POSTCODE": "SW1A 1AA",
                        }
                    }
                ]
            }
        )
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert result.is_valid
        # OS-style URLs: normalised to the dedicated postcode endpoint, with
        # key and postcode as query parameters
        assert mock.call_args[0][0] == "https://api.os.uk/search/places/v1/postcode"
        assert mock.call_args.kwargs["params"] == {
            "postcode": "SW1A 1AA",
            "maxresults": "100",
            "key": "addr-key",
        }
        addr = result.addresses[0]
        assert addr["line_1"] == "10 DOWNING STREET"
        assert addr["town_city"] == "LONDON"
        assert addr["postcode"] == "SW1A 1AA"

    @override_settings(
        ADDRESS_LOOKUP_API_URL="https://api.os.uk/search/places/v1/{path}?key=embedded-key",
        ADDRESS_LOOKUP_API_KEY="addr-key",
    )
    def test_os_url_template_with_embedded_key_is_normalised(self):
        """The OS Data Hub docs hand out URLs like
        https://api.os.uk/search/places/v1/{path}?key=... — the {path}
        placeholder resolves to 'find' and the embedded key is dropped in
        favour of the per-request key parameter."""
        patcher, mock = _service_response(
            payload={
                "results": [
                    {
                        "DPA": {
                            "ADDRESS": "1 HIGH STREET, LONDON, SW1A 1AA",
                            "POST_TOWN": "LONDON",
                            "POSTCODE": "SW1A 1AA",
                        }
                    }
                ]
            }
        )
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert result.is_valid
        url = mock.call_args[0][0]
        assert "{path}" not in url
        assert "embedded-key" not in url
        assert url == "https://api.os.uk/search/places/v1/postcode"
        assert mock.call_args.kwargs["params"]["key"] == "addr-key"
        assert result.addresses[0]["line_1"] == "1 HIGH STREET"

    @override_settings(
        ADDRESS_LOOKUP_API_URL="https://api.os.uk/search/places/v1/",
        ADDRESS_LOOKUP_API_KEY="addr-key",
    )
    def test_bare_os_places_base_gets_postcode_endpoint(self):
        patcher, mock = _service_response(payload={"results": []})
        AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert mock.call_args[0][0] == "https://api.os.uk/search/places/v1/postcode"
        assert mock.call_args.kwargs["params"]["postcode"] == "SW1A 1AA"

    def test_lookup_os_places_metadata_only_returns_no_addresses(self):
        # The open postcodes.io / RCPCH shape: postcode metadata, no addresses
        patcher, _mock = _service_response(
            payload={
                "status": 200,
                "result": {
                    "postcode": "SW1A 1AA",
                    "admin_district": "Westminster",
                    "index_of_multiple_deprivation": 24862,
                },
            }
        )
        result = AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert not result.is_valid
        assert result.error == "No addresses found for this postcode"

    def test_lookup_uses_api_key_header(self):
        patcher, mock = _service_response(
            payload={"status": 200, "result": TWO_ADDRESSES}
        )
        with override_settings(POSTCODES_API_KEY="test-key-123"):
            AddressLookupService.lookup("SW1A 1AA")
        patcher.stop()
        assert mock.call_args.kwargs["headers"] == {
            "Ocp-Apim-Subscription-Key": "test-key-123"
        }


# ============================================================================
# HTMX endpoint tests
# ============================================================================


@pytest.mark.django_db
class TestAddressLookupView:
    def test_find_address_returns_prefilled_widget(self, client):
        with patch("checktick_app.surveys.views.AddressLookupService.lookup") as lookup:
            lookup.return_value = AddressLookupResult(
                postcode="SW1A 1AA", addresses=TWO_ADDRESSES_NORMALISED
            )
            resp = client.post(
                reverse("surveys:address_lookup"),
                {"prefix": "q_12", "q_12_post_code": "SW1A 1AA"},
            )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'name="q_12_address_line_1"' in content
        assert 'name="q_12_post_code"' in content
        assert "Select your address" in content
        lookup.assert_called_once_with("SW1A 1AA")

    def test_single_address_prefills_fields(self, client):
        with patch("checktick_app.surveys.views.AddressLookupService.lookup") as lookup:
            lookup.return_value = AddressLookupResult(
                postcode="SW1A 1AA",
                addresses=TWO_ADDRESSES_NORMALISED[:1],
            )
            resp = client.post(
                reverse("surveys:address_lookup"),
                {"prefix": "q_7", "q_7_post_code": "SW1A 1AA"},
            )
        content = resp.content.decode()
        assert 'value="1 High Street"' in content
        assert "Select your address" not in content

    def test_selected_index_prefills_that_address(self, client):
        with patch("checktick_app.surveys.views.AddressLookupService.lookup") as lookup:
            lookup.return_value = AddressLookupResult(
                postcode="SW1A 1AA", addresses=TWO_ADDRESSES_NORMALISED
            )
            resp = client.post(
                reverse("surveys:address_lookup"),
                {
                    "prefix": "q_7",
                    "q_7_post_code": "SW1A 1AA",
                    "q_7_address_index": "1",
                },
            )
        content = resp.content.decode()
        assert 'value="2 High Street"' in content
        assert 'value="1" selected' in content

    def test_empty_postcode_shows_error(self, client):
        resp = client.post(
            reverse("surveys:address_lookup"),
            {"prefix": "q_7", "q_7_post_code": ""},
        )
        content = resp.content.decode()
        assert "Enter a postcode" in content

    def test_invalid_prefix_is_sanitised(self, client):
        with patch("checktick_app.surveys.views.AddressLookupService.lookup") as lookup:
            lookup.return_value = AddressLookupResult(
                postcode="SW1A 1AA", addresses=TWO_ADDRESSES_NORMALISED
            )
            resp = client.post(
                reverse("surveys:address_lookup"),
                {"prefix": "../evil", "q_7_post_code": "SW1A 1AA"},
            )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "../evil" not in content

    def test_not_configured_shows_manual_entry_hint(self, client):
        with override_settings(POSTCODES_API_URL="", ADDRESS_LOOKUP_API_URL=""):
            resp = client.post(reverse("surveys:address_lookup"), {"prefix": "q_7"})
        content = resp.content.decode()
        assert "not available" in content
        assert 'name="q_7_address_line_1"' in content


TWO_ADDRESSES_NORMALISED = [
    {
        "line_1": "1 High Street",
        "line_2": "",
        "town_city": "LONDON",
        "county": "Greater London",
        "postcode": "SW1A 1AA",
        "summary": "1 High Street LONDON",
    },
    {
        "line_1": "2 High Street",
        "line_2": "Flat B Rear Entrance",
        "town_city": "LONDON",
        "county": "",
        "postcode": "SW1A 1AA",
        "summary": "2 High Street Flat B Rear Entrance LONDON",
    },
]


# ============================================================================
# Builder option persistence
# ============================================================================


@pytest.mark.django_db
def test_patient_template_address_lookup_toggle(client, pro_owner):
    survey = Survey.objects.create(owner=pro_owner, name="AL", slug="al-patient")
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)
    client.force_login(pro_owner)
    client.post(
        reverse(
            "surveys:builder_group_template_add",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        {"template": "patient_details_encrypted"},
    )
    question = SurveyQuestion.objects.get(survey=survey, group=group)
    assert not question.options.get("address_lookup")

    update_url = reverse(
        "surveys:builder_group_question_template_patient_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )
    resp = client.post(
        update_url,
        {"fields": ["first_name", "post_code"], "address_lookup": "on"},
    )
    assert resp.status_code == 200
    question.refresh_from_db()
    assert question.options["address_lookup"] is True

    resp = client.post(update_url, {"fields": ["first_name", "post_code"]})
    assert resp.status_code == 200
    question.refresh_from_db()
    assert question.options["address_lookup"] is False


@pytest.mark.django_db
def test_professional_template_address_lookup_toggle(client, pro_owner):
    survey = Survey.objects.create(owner=pro_owner, name="AL2", slug="al-professional")
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)
    client.force_login(pro_owner)
    client.post(
        reverse(
            "surveys:builder_group_template_add",
            kwargs={"slug": survey.slug, "gid": group.id},
        ),
        {"template": "professional_details"},
    )
    question = SurveyQuestion.objects.get(survey=survey, group=group)

    update_url = reverse(
        "surveys:builder_group_question_template_professional_update",
        kwargs={"slug": survey.slug, "gid": group.id, "qid": question.id},
    )
    resp = client.post(
        update_url,
        {"fields": ["job_title"], "address_lookup": "on"},
    )
    assert resp.status_code == 200
    question.refresh_from_db()
    assert question.options["address_lookup"] is True


# ============================================================================
# Respondent rendering
# ============================================================================


@pytest.mark.django_db
def test_patient_template_renders_address_widget(
    client, patient_template_survey, respondent
):
    survey, question = patient_template_survey
    client.force_login(respondent)
    resp = client.get(reverse("surveys:detail", kwargs={"slug": survey.slug}))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "data-address-lookup" in content
    assert f'name="q_{question.id}_address_line_1"' in content
    assert f'name="q_{question.id}_town_city"' in content
    # The plain post_code grid input is replaced by the widget's postcode input
    assert f'name="q_{question.id}_post_code"' in content


@pytest.mark.django_db
def test_professional_template_renders_address_widget(client, pro_owner, respondent):
    survey = Survey.objects.create(
        owner=pro_owner,
        name="AL3",
        slug="al-prof-render",
        visibility=Survey.Visibility.AUTHENTICATED,
        status=Survey.Status.PUBLISHED,
    )
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(
        survey=survey, user=respondent, role=SurveyMembership.Role.VIEWER
    )
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)
    SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Professional details",
        type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
        options={
            "template": "professional_details",
            "fields": [
                {"key": "job_title", "label": "Job title", "selected": True},
            ],
            "address_lookup": True,
        },
        order=1,
    )
    client.force_login(respondent)
    resp = client.get(reverse("surveys:detail", kwargs={"slug": survey.slug}))
    content = resp.content.decode()
    assert "data-address-lookup" in content


# ============================================================================
# Answer capture on submission
# ============================================================================


@pytest.mark.django_db
def test_patient_submission_captures_address_fields(
    client, patient_template_survey, respondent
):
    survey, question = patient_template_survey
    client.force_login(respondent)
    resp = client.post(
        reverse("surveys:detail", kwargs={"slug": survey.slug}),
        {
            f"q_{question.id}_first_name": "Ada",
            f"q_{question.id}_post_code": "SW1A 1AA",
            f"q_{question.id}_address_line_1": "1 High Street",
            f"q_{question.id}_town_city": "LONDON",
        },
    )
    assert resp.status_code == 302
    response = SurveyResponse.objects.get(survey=survey)
    answer = response.answers[str(question.id)]
    assert "address_line_1" in answer["fields"]
    assert "town_city" in answer["fields"]
    assert "post_code" in answer["fields"]


@pytest.mark.django_db
def test_professional_submission_captures_address_fields(client, pro_owner, respondent):
    survey = Survey.objects.create(
        owner=pro_owner,
        name="AL4",
        slug="al-prof-submit",
        visibility=Survey.Visibility.AUTHENTICATED,
        status=Survey.Status.PUBLISHED,
    )
    from checktick_app.surveys.models import SurveyMembership

    SurveyMembership.objects.create(
        survey=survey, user=respondent, role=SurveyMembership.Role.VIEWER
    )
    group = QuestionGroup.objects.create(name="Group", owner=pro_owner)
    survey.question_groups.add(group)
    question = SurveyQuestion.objects.create(
        survey=survey,
        group=group,
        text="Professional details",
        type=SurveyQuestion.Types.TEMPLATE_PROFESSIONAL,
        options={
            "template": "professional_details",
            "fields": [
                {"key": "job_title", "label": "Job title", "selected": True},
            ],
            "address_lookup": True,
        },
        order=1,
    )
    client.force_login(respondent)
    resp = client.post(
        reverse("surveys:detail", kwargs={"slug": survey.slug}),
        {
            f"q_{question.id}_job_title": "Consultant",
            f"q_{question.id}_post_code": "SW1A 1AA",
            f"q_{question.id}_address_line_1": "1 High Street",
            f"q_{question.id}_county": "Greater London",
        },
    )
    assert resp.status_code == 302
    response = SurveyResponse.objects.get(survey=survey)
    prof = response.answers["professional"]
    assert prof["post_code"] == "SW1A 1AA"
    assert prof["address_line_1"] == "1 High Street"
    assert prof["county"] == "Greater London"
