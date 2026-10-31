"""Tests for the Tokens-page 360 conveniences (issues #354, #355, #356).

- #354: token-level category value override — unused invitations only,
  audit-logged; a used invitation's values are part of the audit trail
  and stay read-only.
- #355: "Generate full 360 set for a subject" — one batch per rater_role
  value, every invitation carrying the subject; offered only when the
  survey carries the 360 convention (token-source subject + rater_role
  dimensions).
- #356: filter the flat token list by the subject value so organisers
  can scan completion per subject; the CSV export stays flat and
  unchanged.
"""

from django.urls import reverse
from django.utils import timezone
import pytest

from checktick_app.surveys.models import (
    AuditLog,
    Organization,
    RespondentCategory,
    Survey,
    SurveyAccessToken,
)

TEST_PASSWORD = "x"
SUBJECT_A = "Dr Jane Smith"
SUBJECT_B = "Dr Bob Jones"
# Roughly 0.9 similarity — trips the 0.8 fuzzy cutoff (issue #353 pattern).
NEAR_DUPLICATE = "Dr Jane Smith"
NEAR_TYPO = "Dr Jane Smyth"


@pytest.fixture(autouse=True)
def disable_rate_limiting(settings):
    settings.RATELIMIT_ENABLE = False


@pytest.fixture
def owner(django_user_model):
    user = django_user_model.objects.create_user(
        username="owner@example.com", password=TEST_PASSWORD
    )
    user.profile.account_tier = "pro"
    user.profile.subscription_status = "active"
    user.profile.save()
    return user


@pytest.fixture
def org(owner):
    return Organization.objects.create(name="Org", owner=owner)


def _make_360_survey(
    owner,
    org,
    *,
    slug,
    subject_free_text=False,
    subject_source=RespondentCategory.ResolutionSource.TOKEN,
):
    """A token-visibility survey carrying the 360 convention.

    Token-source ``subject`` + ``rater_role`` dimensions by default; the
    knobs exist to build the non-360 variants the action must reject.
    """
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="S",
        slug=slug,
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="subject",
        label="Subject",
        allowed_values=[] if subject_free_text else [SUBJECT_A, SUBJECT_B],
        free_text=subject_free_text,
        resolution_source=subject_source,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        label="Rater role",
        allowed_values=["self", "peer", "supervisor"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    return s


@pytest.fixture
def survey(owner, org):
    return _make_360_survey(owner, org, slug="s")


def _tokens_url(survey):
    return reverse("surveys:tokens", kwargs={"slug": survey.slug})


def _token_categories_edit_url(survey, token):
    return reverse(
        "surveys:token_categories_edit",
        kwargs={"slug": survey.slug, "token_id": token.id},
    )


def _messages_texts(response):
    return [str(m) for m in response.context["messages"]]


def _make_token(survey, owner, *, category_values, used=False, token="tok"):
    return SurveyAccessToken.objects.create(
        survey=survey,
        token=token,
        created_by=owner,
        category_values=category_values,
        used_at=timezone.now() if used else None,
    )


# --- Issue #354: token-level category value override ----------------------


@pytest.mark.django_db
def test_token_category_edit_updates_values(client, survey, owner):
    t = _make_token(
        survey,
        owner,
        category_values={"subject": SUBJECT_A, "rater_role": "self"},
        token="tok-edit",
    )
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(survey, t),
        {"category_subject": SUBJECT_B, "category_rater_role": "peer"},
    )
    assert res.status_code == 302
    t.refresh_from_db()
    assert t.category_values == {"subject": SUBJECT_B, "rater_role": "peer"}


@pytest.mark.django_db
def test_token_category_edit_blank_clears_value(client, survey, owner):
    """A blank dimension falls back to its next resolution source."""
    t = _make_token(
        survey,
        owner,
        category_values={"subject": SUBJECT_A, "rater_role": "peer"},
        token="tok-clear",
    )
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(survey, t),
        {"category_subject": SUBJECT_A, "category_rater_role": ""},
    )
    assert res.status_code == 302
    t.refresh_from_db()
    assert t.category_values == {"subject": SUBJECT_A}


@pytest.mark.django_db
def test_token_category_edit_drops_unknown_dimensions(client, survey, owner):
    t = _make_token(survey, owner, category_values={}, token="tok-unknown")
    client.force_login(owner)
    client.post(
        _token_categories_edit_url(survey, t),
        {"category_subject": SUBJECT_A, "category_typo_dim": "x"},
    )
    t.refresh_from_db()
    assert t.category_values == {"subject": SUBJECT_A}


@pytest.mark.django_db
def test_token_category_edit_rejects_used_token(client, survey, owner):
    """A used invitation's values are part of the audit trail."""
    t = _make_token(
        survey,
        owner,
        category_values={"subject": SUBJECT_A},
        used=True,
        token="tok-used",
    )
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(survey, t), {"category_subject": SUBJECT_B}
    )
    assert res.status_code == 302
    t.refresh_from_db()
    assert t.category_values == {"subject": SUBJECT_A}
    assert not AuditLog.objects.filter(survey=survey).exists()


@pytest.mark.django_db
def test_token_category_edit_audits(client, survey, owner):
    t = _make_token(
        survey, owner, category_values={"subject": SUBJECT_A}, token="tok-audit"
    )
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(survey, t),
        {"category_subject": SUBJECT_B},
        follow=True,
    )
    assert res.status_code == 200
    log = AuditLog.objects.get(survey=survey, action=AuditLog.Action.UPDATE)
    assert log.actor_id == owner.id
    assert log.metadata["token_id"] == t.id
    assert log.metadata["dimensions"] == ["subject"]
    # Metadata only — never the values (subject names are personal data,
    # AGENTS.md logging rules) and never the token string (a credential).
    assert SUBJECT_A not in str(log.metadata)
    assert SUBJECT_B not in str(log.metadata)
    assert SUBJECT_B not in log.message
    assert t.token not in log.message


@pytest.mark.django_db
def test_token_category_edit_no_audit_when_unchanged(client, survey, owner):
    t = _make_token(
        survey, owner, category_values={"subject": SUBJECT_A}, token="tok-same"
    )
    client.force_login(owner)
    client.post(_token_categories_edit_url(survey, t), {"category_subject": SUBJECT_A})
    assert not AuditLog.objects.filter(survey=survey).exists()


@pytest.mark.django_db
def test_token_category_edit_requires_editor(client, survey, owner, django_user_model):
    outsider = django_user_model.objects.create_user(
        username="outsider@example.com", password=TEST_PASSWORD
    )
    t = _make_token(survey, owner, category_values={}, token="tok-perm")
    client.force_login(outsider)
    res = client.post(
        _token_categories_edit_url(survey, t), {"category_subject": SUBJECT_A}
    )
    assert res.status_code == 403
    t.refresh_from_db()
    assert t.category_values == {}


@pytest.mark.django_db
def test_token_category_edit_404_for_other_survey(client, survey, owner, org):
    """The token id must belong to this survey — no cross-survey edits."""
    other = _make_360_survey(owner, org, slug="other")
    t_other = _make_token(other, owner, category_values={}, token="tok-other")
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(survey, t_other), {"category_subject": SUBJECT_A}
    )
    assert res.status_code == 404


@pytest.mark.django_db
def test_token_category_edit_warns_on_near_duplicate(client, owner, org):
    """The edit path shares the batch form's free-text typo warning."""
    s = _make_360_survey(owner, org, slug="s-ft-edit", subject_free_text=True)
    t = _make_token(
        s, owner, category_values={"subject": NEAR_DUPLICATE}, token="tok-ftedit"
    )
    client.force_login(owner)
    res = client.post(
        _token_categories_edit_url(s, t),
        {"category_subject": NEAR_TYPO},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    assert any(NEAR_DUPLICATE in m and NEAR_TYPO in m for m in msgs)
    # Non-blocking: the edit still goes through.
    t.refresh_from_db()
    assert t.category_values == {"subject": NEAR_TYPO}


@pytest.mark.django_db
def test_tokens_page_edit_form_only_for_unused_tokens(client, survey, owner):
    used = _make_token(
        survey,
        owner,
        category_values={"subject": SUBJECT_A},
        used=True,
        token="tok-used-row",
    )
    unused = _make_token(
        survey, owner, category_values={"subject": SUBJECT_A}, token="tok-unused-row"
    )
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert f"/tokens/{unused.id}/categories" in html
    assert f"/tokens/{used.id}/categories" not in html


# --- Issue #355: "Generate full 360 set for a subject" --------------------


@pytest.mark.django_db
def test_generate_360_set_creates_batch_per_role(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {
            "action": "generate_360_set",
            "subject": SUBJECT_A,
            "count_self": "1",
            "count_peer": "2",
            "count_supervisor": "1",
        },
    )
    assert res.status_code == 302
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 4
    by_role: dict[str, list] = {}
    for t in tokens:
        assert t.category_values["subject"] == SUBJECT_A
        by_role.setdefault(t.category_values["rater_role"], []).append(t)
    assert set(by_role) == {"self", "peer", "supervisor"}
    assert len(by_role["self"]) == 1
    assert len(by_role["peer"]) == 2
    assert len(by_role["supervisor"]) == 1


@pytest.mark.django_db
def test_generate_360_set_skips_zero_count_roles(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {
            "action": "generate_360_set",
            "subject": SUBJECT_A,
            "count_self": "1",
            "count_peer": "0",
            "count_supervisor": "",
        },
    )
    assert res.status_code == 302
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 1
    assert tokens[0].category_values == {"subject": SUBJECT_A, "rater_role": "self"}


@pytest.mark.django_db
def test_generate_360_set_clamps_bad_counts(client, survey, owner):
    """Counts share the batch form's 0..1000 clamp; junk counts as 0."""
    client.force_login(owner)
    client.post(
        _tokens_url(survey),
        {
            "action": "generate_360_set",
            "subject": SUBJECT_A,
            "count_self": "1000",
            "count_peer": "-5",
            "count_supervisor": "not-a-number",
        },
    )
    tokens = list(SurveyAccessToken.objects.filter(survey=survey))
    assert len(tokens) == 1000
    assert all(t.category_values["rater_role"] == "self" for t in tokens)


@pytest.mark.django_db
def test_generate_360_set_requires_subject(client, survey, owner):
    client.force_login(owner)
    res = client.post(
        _tokens_url(survey),
        {"action": "generate_360_set", "subject": "", "count_self": "1"},
        follow=True,
    )
    assert res.status_code == 200
    assert not SurveyAccessToken.objects.filter(survey=survey).exists()
    assert any("subject" in m.lower() for m in _messages_texts(res))


@pytest.mark.django_db
def test_generate_360_set_rejected_without_360_dims(client, owner, org):
    """A direct POST against a non-360 survey creates nothing."""
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain360",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="rater_role",
        allowed_values=["peer"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    client.force_login(owner)
    res = client.post(
        _tokens_url(s),
        {"action": "generate_360_set", "subject": SUBJECT_A, "count_peer": "2"},
        follow=True,
    )
    assert res.status_code == 200
    assert not SurveyAccessToken.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_generate_360_set_rejected_when_subject_not_token_source(client, owner, org):
    """The action needs the token-source subject dimension specifically."""
    s = _make_360_survey(
        owner,
        org,
        slug="s-selfselect",
        subject_source=RespondentCategory.ResolutionSource.SELF_SELECT,
    )
    client.force_login(owner)
    client.post(
        _tokens_url(s),
        {"action": "generate_360_set", "subject": SUBJECT_A, "count_self": "1"},
    )
    assert not SurveyAccessToken.objects.filter(survey=s).exists()


@pytest.mark.django_db
def test_generate_360_set_warns_on_near_duplicate_subject(client, owner, org):
    """A free-text subject gets the same typo warning as the batch form."""
    s = _make_360_survey(owner, org, slug="s-ft360", subject_free_text=True)
    _make_token(
        s, owner, category_values={"subject": NEAR_DUPLICATE}, token="tok-ft360"
    )
    client.force_login(owner)
    res = client.post(
        _tokens_url(s),
        {"action": "generate_360_set", "subject": NEAR_TYPO, "count_self": "1"},
        follow=True,
    )
    assert res.status_code == 200
    msgs = _messages_texts(res)
    assert any(NEAR_DUPLICATE in m and NEAR_TYPO in m for m in msgs)
    # Non-blocking: the 360 set is still created.
    assert SurveyAccessToken.objects.filter(
        survey=s, category_values__subject=NEAR_TYPO
    ).exists()


@pytest.mark.django_db
def test_tokens_page_shows_360_action(client, survey, owner):
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Generate full 360 set for a subject" in html
    # One count input per role value, and the subject roster select.
    assert 'name="count_self"' in html
    assert 'name="count_peer"' in html
    assert 'name="count_supervisor"' in html
    assert f'<option value="{SUBJECT_A}">' in html


@pytest.mark.django_db
def test_tokens_page_hides_360_action_without_dims(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Plain",
        slug="plain-tokens",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    client.force_login(owner)
    res = client.get(_tokens_url(s))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Generate full 360 set" not in html


# --- Issue #356: filter the token list by subject -------------------------


@pytest.mark.django_db
def test_tokens_page_subject_filter(client, survey, owner):
    a1 = _make_token(
        survey, owner, category_values={"subject": SUBJECT_A}, token="tok-a1"
    )
    a2 = _make_token(
        survey,
        owner,
        category_values={"subject": SUBJECT_A, "rater_role": "peer"},
        token="tok-a2",
    )
    b1 = _make_token(
        survey, owner, category_values={"subject": SUBJECT_B}, token="tok-b1"
    )
    client.force_login(owner)
    res = client.get(_tokens_url(survey), {"subject": SUBJECT_A})
    assert res.status_code == 200
    html = res.content.decode()
    assert a1.token in html
    assert a2.token in html
    assert b1.token not in html


@pytest.mark.django_db
def test_tokens_page_subject_filter_dropdown_lists_values(client, survey, owner):
    _make_token(survey, owner, category_values={"subject": SUBJECT_A}, token="tok-d1")
    _make_token(survey, owner, category_values={"subject": SUBJECT_B}, token="tok-d2")
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Filter by subject" in html
    assert f'<option value="{SUBJECT_A}"' in html
    assert f'<option value="{SUBJECT_B}"' in html


@pytest.mark.django_db
def test_tokens_page_subject_filter_dropdown_hidden_without_values(
    client, survey, owner
):
    """Nothing to filter by until a batch carries a subject value."""
    client.force_login(owner)
    res = client.get(_tokens_url(survey))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Filter by subject" not in html


@pytest.mark.django_db
def test_tokens_page_no_subject_filter_without_subject_dim(client, owner, org):
    s = Survey.objects.create(
        owner=owner,
        organization=org,
        name="Site only",
        slug="site-only",
        visibility=Survey.Visibility.TOKEN,
        status=Survey.Status.PUBLISHED,
    )
    RespondentCategory.objects.create(
        survey=s,
        name="site",
        allowed_values=["Chelsea", "Westminster"],
        resolution_source=RespondentCategory.ResolutionSource.TOKEN,
    )
    _make_token(s, owner, category_values={"site": "Chelsea"}, token="tok-site")
    client.force_login(owner)
    res = client.get(_tokens_url(s))
    assert res.status_code == 200
    html = res.content.decode()
    assert "Filter by subject" not in html
