from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from checktick_app.core.billing import PaymentAPIError, PaymentClient
from checktick_app.core.email_utils import (
    send_promotion_activated_email,
    send_promotion_ending_soon_email,
    send_promotion_expired_email,
)
from checktick_app.core.models import Promotion, UserProfile
from checktick_app.core.services.promotion_resolver import (
    resolve_effective_pricing_for_organization,
    resolve_effective_pricing_for_team,
    resolve_effective_pricing_for_user,
)
from checktick_app.surveys.models import AuditLog, Organization, Team

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send promotion lifecycle emails and reconcile subscription amounts"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument(
            "--ending-soon-days",
            type=int,
            default=7,
            help="Days before expiry to send ending-soon notifications",
        )
        parser.add_argument(
            "--recent-expiry-days",
            type=int,
            default=2,
            help="Lookback window for recently expired promotions",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbose = options["verbose"]
        ending_soon_days = options["ending_soon_days"]
        recent_expiry_days = options["recent_expiry_days"]

        payment_client = PaymentClient()
        now = timezone.now()
        ending_cutoff = now + timedelta(days=ending_soon_days)
        recent_expiry_cutoff = now - timedelta(days=recent_expiry_days)

        self.stdout.write(
            self.style.SUCCESS(f"Processing promotion lifecycle at {now}")
        )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - no API or email changes")
            )

        stats = {
            "subscriptions_checked": 0,
            "subscriptions_updated": 0,
            "activation_emails": 0,
            "ending_soon_emails": 0,
            "expired_emails": 0,
        }

        for profile in UserProfile.objects.exclude(payment_subscription_id=""):
            if profile.account_tier == UserProfile.AccountTier.FREE:
                continue
            stats["subscriptions_checked"] += 1
            self._process_user_profile(
                payment_client,
                profile,
                now,
                ending_cutoff,
                recent_expiry_cutoff,
                dry_run,
                verbose,
                stats,
            )

        for team in Team.objects.exclude(subscription_id=""):
            stats["subscriptions_checked"] += 1
            self._process_team(
                payment_client,
                team,
                now,
                ending_cutoff,
                recent_expiry_cutoff,
                dry_run,
                verbose,
                stats,
            )

        for org in Organization.objects.exclude(payment_subscription_id=""):
            stats["subscriptions_checked"] += 1
            self._process_organization(
                payment_client,
                org,
                now,
                ending_cutoff,
                recent_expiry_cutoff,
                dry_run,
                verbose,
                stats,
            )

        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")

    def _log_once_exists(
        self, action: str, promotion_id: int, target_type: str, target_id: str
    ) -> bool:
        return AuditLog.objects.filter(
            action=action,
            metadata__promotion_id=str(promotion_id),
            metadata__target_type=target_type,
            metadata__target_id=target_id,
        ).exists()

    def _create_lifecycle_log(
        self,
        action: str,
        message: str,
        promotion: Promotion | None,
        target_type: str,
        target_id: str,
    ):
        AuditLog.objects.create(
            actor=None,
            scope=AuditLog.Scope.ACCOUNT,
            action=action,
            severity=AuditLog.Severity.INFO,
            message=message,
            metadata={
                "promotion_id": str(promotion.id) if promotion else "",
                "promotion_name": promotion.name if promotion else "",
                "target_type": target_type,
                "target_id": target_id,
            },
        )

    def _process_user_profile(
        self,
        payment_client,
        profile,
        now,
        ending_cutoff,
        recent_expiry_cutoff,
        dry_run,
        verbose,
        stats,
    ):
        user = profile.user
        resolution = resolve_effective_pricing_for_user(user, at_time=now)
        current_amount = self._fetch_current_amount(
            payment_client, profile.payment_subscription_id
        )
        if (
            current_amount is not None
            and current_amount != resolution.effective_amount_pence
        ):
            self._reconcile_subscription(
                payment_client,
                subscription_id=profile.payment_subscription_id,
                effective_amount=resolution.effective_amount_pence,
                applied_promotion=resolution.applied_promotion,
                target_label=f"user {user.email}",
                dry_run=dry_run,
                verbose=verbose,
            )
            stats["subscriptions_updated"] += 1

        self._send_lifecycle_notifications(
            to_email=user.email,
            recipient_name=user.first_name or user.username,
            target_type="user",
            target_id=str(user.id),
            current_resolution=resolution,
            next_resolution=resolve_effective_pricing_for_user(
                user, at_time=ending_cutoff + timedelta(minutes=1)
            ),
            ended_promotion=self._find_recently_ended_promotion_for_user(
                user, now, recent_expiry_cutoff
            ),
            now=now,
            ending_cutoff=ending_cutoff,
            dry_run=dry_run,
            stats=stats,
        )

    def _process_team(
        self,
        payment_client,
        team,
        now,
        ending_cutoff,
        recent_expiry_cutoff,
        dry_run,
        verbose,
        stats,
    ):
        resolution = resolve_effective_pricing_for_team(team, at_time=now)
        current_amount = self._fetch_current_amount(
            payment_client, team.subscription_id
        )
        if (
            current_amount is not None
            and current_amount != resolution.effective_amount_pence
        ):
            self._reconcile_subscription(
                payment_client,
                subscription_id=team.subscription_id,
                effective_amount=resolution.effective_amount_pence,
                applied_promotion=resolution.applied_promotion,
                target_label=f"team {team.name}",
                dry_run=dry_run,
                verbose=verbose,
            )
            stats["subscriptions_updated"] += 1

        self._send_lifecycle_notifications(
            to_email=team.owner.email,
            recipient_name=team.owner.first_name or team.owner.username,
            target_type="team",
            target_id=str(team.id),
            current_resolution=resolution,
            next_resolution=resolve_effective_pricing_for_team(
                team, at_time=ending_cutoff + timedelta(minutes=1)
            ),
            ended_promotion=self._find_recently_ended_promotion_for_team(
                team, now, recent_expiry_cutoff
            ),
            now=now,
            ending_cutoff=ending_cutoff,
            dry_run=dry_run,
            stats=stats,
        )

    def _process_organization(
        self,
        payment_client,
        org,
        now,
        ending_cutoff,
        recent_expiry_cutoff,
        dry_run,
        verbose,
        stats,
    ):
        resolution = resolve_effective_pricing_for_organization(org, at_time=now)
        current_amount = self._fetch_current_amount(
            payment_client, org.payment_subscription_id
        )
        if (
            current_amount is not None
            and current_amount != resolution.effective_amount_pence
        ):
            self._reconcile_subscription(
                payment_client,
                subscription_id=org.payment_subscription_id,
                effective_amount=resolution.effective_amount_pence,
                applied_promotion=resolution.applied_promotion,
                target_label=f"organisation {org.name}",
                dry_run=dry_run,
                verbose=verbose,
            )
            stats["subscriptions_updated"] += 1

        contact_email = org.billing_contact_email or (
            org.owner.email if org.owner else ""
        )
        if not contact_email:
            return
        contact_name = org.name
        self._send_lifecycle_notifications(
            to_email=contact_email,
            recipient_name=contact_name,
            target_type="organization",
            target_id=str(org.id),
            current_resolution=resolution,
            next_resolution=resolve_effective_pricing_for_organization(
                org, at_time=ending_cutoff + timedelta(minutes=1)
            ),
            ended_promotion=self._find_recently_ended_promotion_for_organization(
                org, now, recent_expiry_cutoff
            ),
            now=now,
            ending_cutoff=ending_cutoff,
            dry_run=dry_run,
            stats=stats,
        )

    def _fetch_current_amount(self, payment_client, subscription_id: str) -> int | None:
        try:
            subscription = payment_client.get_subscription(subscription_id)
        except PaymentAPIError as exc:
            logger.error("Failed to fetch subscription %s: %s", subscription_id, exc)
            return None
        amount = subscription.get("amount")
        try:
            return int(amount) if amount is not None else None
        except (TypeError, ValueError):
            return None

    def _reconcile_subscription(
        self,
        payment_client,
        *,
        subscription_id: str,
        effective_amount: int,
        applied_promotion,
        target_label: str,
        dry_run: bool,
        verbose: bool,
    ):
        metadata = {
            "applied_promotion_id": (
                str(applied_promotion.id) if applied_promotion else ""
            ),
        }
        if verbose or dry_run:
            self.stdout.write(
                f"Reconcile {target_label}: {subscription_id} -> {effective_amount}"
            )
        if not dry_run:
            payment_client.update_subscription(
                subscription_id,
                amount=effective_amount,
                metadata=metadata,
            )
            self._create_lifecycle_log(
                AuditLog.Action.PROMOTION_RECONCILED,
                f"Promotion pricing reconciled for {target_label}.",
                applied_promotion,
                "subscription",
                subscription_id,
            )

    def _send_lifecycle_notifications(
        self,
        *,
        to_email: str,
        recipient_name: str,
        target_type: str,
        target_id: str,
        current_resolution,
        next_resolution,
        ended_promotion,
        now,
        ending_cutoff,
        dry_run: bool,
        stats: dict,
    ):
        promotion = current_resolution.applied_promotion
        if (
            promotion
            and promotion.starts_at
            and promotion.starts_at <= now
            and not self._log_once_exists(
                AuditLog.Action.PROMOTION_ACTIVATED,
                promotion.id,
                target_type,
                target_id,
            )
        ):
            if not dry_run:
                send_promotion_activated_email(
                    to_email=to_email,
                    recipient_name=recipient_name,
                    promotion_name=promotion.name,
                    effective_amount=f"£{current_resolution.effective_amount_pence / 100:.2f}",
                    effective_tier=current_resolution.effective_tier.replace(
                        "_", " "
                    ).title(),
                    ends_at_text=(
                        promotion.ends_at.strftime("%d %B %Y")
                        if promotion.ends_at
                        else ""
                    ),
                )
            if not dry_run:
                self._create_lifecycle_log(
                    AuditLog.Action.PROMOTION_ACTIVATED,
                    f"Promotion '{promotion.name}' activated notification sent.",
                    promotion,
                    target_type,
                    target_id,
                )
            stats["activation_emails"] += 1

        if (
            promotion
            and promotion.ends_at
            and now <= promotion.ends_at <= ending_cutoff
            and not self._log_once_exists(
                AuditLog.Action.PROMOTION_ENDING_SOON,
                promotion.id,
                target_type,
                target_id,
            )
        ):
            if not dry_run:
                send_promotion_ending_soon_email(
                    to_email=to_email,
                    recipient_name=recipient_name,
                    promotion_name=promotion.name,
                    current_amount=f"£{current_resolution.effective_amount_pence / 100:.2f}",
                    next_amount=f"£{next_resolution.effective_amount_pence / 100:.2f}",
                    effective_tier=current_resolution.effective_tier.replace(
                        "_", " "
                    ).title(),
                    ends_at_text=promotion.ends_at.strftime("%d %B %Y"),
                )
            if not dry_run:
                self._create_lifecycle_log(
                    AuditLog.Action.PROMOTION_ENDING_SOON,
                    f"Promotion '{promotion.name}' ending soon notification sent.",
                    promotion,
                    target_type,
                    target_id,
                )
            stats["ending_soon_emails"] += 1

        if ended_promotion and not self._log_once_exists(
            AuditLog.Action.PROMOTION_EXPIRED,
            ended_promotion.id,
            target_type,
            target_id,
        ):
            if not dry_run:
                send_promotion_expired_email(
                    to_email=to_email,
                    recipient_name=recipient_name,
                    promotion_name=ended_promotion.name,
                    effective_tier=current_resolution.effective_tier.replace(
                        "_", " "
                    ).title(),
                    new_amount=f"£{current_resolution.effective_amount_pence / 100:.2f}",
                )
            if not dry_run:
                self._create_lifecycle_log(
                    AuditLog.Action.PROMOTION_EXPIRED,
                    f"Promotion '{ended_promotion.name}' expiry notification sent.",
                    ended_promotion,
                    target_type,
                    target_id,
                )
            stats["expired_emails"] += 1

    def _find_recently_ended_promotion_for_user(self, user, now, cutoff):
        return (
            Promotion.objects.filter(
                Q(scope_type=Promotion.ScopeType.PLATFORM)
                | Q(
                    scope_type=Promotion.ScopeType.TIER,
                    target_tier=user.profile.account_tier,
                )
                | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_user=user),
                ends_at__lt=now,
                ends_at__gte=cutoff,
            )
            .order_by("-ends_at")
            .first()
        )

    def _find_recently_ended_promotion_for_team(self, team, now, cutoff):
        return (
            Promotion.objects.filter(
                Q(scope_type=Promotion.ScopeType.PLATFORM)
                | Q(
                    scope_type=Promotion.ScopeType.TIER,
                    target_tier=team.owner.profile.account_tier,
                )
                | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_team=team),
                ends_at__lt=now,
                ends_at__gte=cutoff,
            )
            .order_by("-ends_at")
            .first()
        )

    def _find_recently_ended_promotion_for_organization(self, org, now, cutoff):
        return (
            Promotion.objects.filter(
                Q(scope_type=Promotion.ScopeType.PLATFORM)
                | Q(
                    scope_type=Promotion.ScopeType.TIER,
                    target_tier=UserProfile.AccountTier.ORGANIZATION,
                )
                | Q(scope_type=Promotion.ScopeType.ACCOUNT, target_organization=org),
                ends_at__lt=now,
                ends_at__gte=cutoff,
            )
            .order_by("-ends_at")
            .first()
        )
