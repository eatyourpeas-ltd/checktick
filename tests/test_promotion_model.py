"""Promotion model validation tests."""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
import pytest

from checktick_app.core.models import Promotion


@pytest.mark.django_db
class TestPromotionImmutability:
    def test_started_promotion_blocks_billing_term_edits(self):
        """Billing-impacting fields become immutable once promotion has started."""
        promotion = Promotion.objects.create(
            name="Started Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() - timedelta(days=1),
            is_active=True,
        )

        promotion.effect_value = 20
        with pytest.raises(ValidationError):
            promotion.full_clean()

    def test_started_promotion_allows_metadata_edits(self):
        """Non-billing metadata can still be updated for started promotions."""
        promotion = Promotion.objects.create(
            name="Metadata Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() - timedelta(hours=1),
            is_active=True,
            internal_notes="Initial note",
        )

        promotion.internal_notes = "Updated support note"
        promotion.full_clean()
        promotion.save(update_fields=["internal_notes", "updated_at"])

        promotion.refresh_from_db()
        assert promotion.internal_notes == "Updated support note"

    def test_future_promotion_can_be_edited_before_start(self):
        """Future scheduled promotions can still be edited before start time."""
        promotion = Promotion.objects.create(
            name="Future Promo",
            scope_type=Promotion.ScopeType.PLATFORM,
            effect_type=Promotion.EffectType.PERCENT_DISCOUNT,
            effect_value=10,
            starts_at=timezone.now() + timedelta(days=2),
            is_active=True,
        )

        promotion.effect_value = 15
        promotion.full_clean()
        promotion.save(update_fields=["effect_value", "updated_at"])

        promotion.refresh_from_db()
        assert str(promotion.effect_value) == "15.00"
