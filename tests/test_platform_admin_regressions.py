from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
import pytest

from checktick_app.core.billing import create_subscription_for_user
from checktick_app.core.models import PricingOverride
from checktick_app.surveys.models import Organization

User = get_user_model()

TEST_PASSWORD = "x"


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="superadmin_regression",
        email="superadmin-regression@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def regular_user(db):
    return User.objects.create_user(
        username="regular_regression",
        email="regular-regression@test.com",
        password=TEST_PASSWORD,
    )


@pytest.fixture
def test_organization(db, superuser):
    owner = User.objects.create_user(
        username="orgowner_regression",
        email="orgowner-regression@test.com",
        password=TEST_PASSWORD,
    )
    return Organization.objects.create(
        name="Regression Test Organization",
        owner=owner,
        billing_type=Organization.BillingType.PER_SEAT,
        price_per_seat="10.00",
        subscription_status=Organization.SubscriptionStatus.PENDING,
        created_by=superuser,
    )


@pytest.mark.django_db
def test_checkout_uses_active_pricing_override(monkeypatch):
    user = User.objects.create_user(
        username="billing_regression",
        email="billing-regression@test.com",
        password=TEST_PASSWORD,
    )
    overridden_amount = settings.SUBSCRIPTION_TIERS["pro"]["amount"] + 111
    overridden_amount_ex_vat = settings.SUBSCRIPTION_TIERS["pro"]["amount_ex_vat"] + 93
    PricingOverride.objects.create(
        tier="pro",
        amount=overridden_amount,
        amount_ex_vat=overridden_amount_ex_vat,
        is_active=True,
    )

    captured = {}

    def fake_create_subscription(**kwargs):
        captured.update(kwargs)
        return {"id": "SUB_123"}

    monkeypatch.setattr(
        "checktick_app.core.billing.payment_client.create_subscription",
        fake_create_subscription,
    )

    subscription_id = create_subscription_for_user(
        user=user,
        tier="pro",
        mandate_id="MD123",
    )

    assert subscription_id == "SUB_123"
    assert captured["amount"] == overridden_amount


@pytest.mark.django_db
def test_organization_create_invalid_numeric_input_returns_form(client, superuser):
    client.force_login(superuser)

    response = client.post(
        reverse("core:platform_admin_org_create"),
        {
            "name": "Broken Numeric Org",
            "owner_email": "broken-numeric@example.com",
            "billing_type": Organization.BillingType.PER_SEAT,
            "price_per_seat": "not-a-number",
        },
    )

    assert response.status_code == 200
    assert not Organization.objects.filter(name="Broken Numeric Org").exists()


@pytest.mark.django_db
def test_organization_create_rejects_invalid_billing_type(client, superuser):
    client.force_login(superuser)

    response = client.post(
        reverse("core:platform_admin_org_create"),
        {
            "name": "Invalid Billing Type Org",
            "owner_email": "invalid-billing-type@example.com",
            "billing_type": "bogus-tier",
            "price_per_seat": "12.50",
        },
    )

    assert response.status_code == 200
    assert not Organization.objects.filter(name="Invalid Billing Type Org").exists()


@pytest.mark.django_db
def test_organization_edit_rejects_invalid_subscription_status(
    client, superuser, test_organization
):
    client.force_login(superuser)

    response = client.post(
        reverse(
            "core:platform_admin_org_edit", kwargs={"org_id": test_organization.id}
        ),
        {
            "name": test_organization.name,
            "billing_type": Organization.BillingType.PER_SEAT,
            "price_per_seat": "10.00",
            "subscription_status": "definitely-not-valid",
            "billing_contact_email": "billing@example.com",
            "is_active": "on",
        },
    )

    test_organization.refresh_from_db()

    assert response.status_code == 200
    assert (
        test_organization.subscription_status == Organization.SubscriptionStatus.PENDING
    )
