"""Signal handlers for core app models."""

from datetime import datetime
import logging

from axes.signals import user_locked_out
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create UserProfile automatically when a new user is created."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Ensure UserProfile exists and is saved when user is saved."""
    if not hasattr(instance, "profile"):
        UserProfile.objects.create(user=instance)
    else:
        instance.profile.save()


@receiver(post_save, sender=User)
def process_pending_invitations(sender, instance, created, **kwargs):
    """Process any pending team/org invitations for newly created users.

    When a user signs up, check if they have any pending invitations
    and automatically add them to the relevant teams/organizations.
    """
    if not created:
        return

    # Import here to avoid circular imports
    from checktick_app.surveys.models import OrgInvitation, TeamInvitation

    email = instance.email.lower() if instance.email else ""
    if not email:
        return

    # Process team invitations
    team_invites = TeamInvitation.objects.filter(
        email__iexact=email,
        accepted_at__isnull=True,
    ).select_related("team")

    for invite in team_invites:
        if invite.is_valid():
            try:
                membership = invite.accept(instance)
                logger.info(
                    f"Accepted team invitation for {email} to team {invite.team.name} "
                    f"with role {membership.role}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to process team invitation {invite.id} for {email}: {e}"
                )

    # Process organization invitations
    org_invites = OrgInvitation.objects.filter(
        email__iexact=email,
        accepted_at__isnull=True,
    ).select_related("organization")

    for invite in org_invites:
        if invite.is_valid():
            try:
                membership = invite.accept(instance)
                logger.info(
                    f"Accepted org invitation for {email} to org {invite.organization.name} "
                    f"with role {membership.role}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to process org invitation {invite.id} for {email}: {e}"
                )


@receiver(user_locked_out)
def send_lockout_notification(sender, request, username, credentials, **kwargs):
    """Send email notification when a user account is locked out.

    This helps users know their account was targeted (possibly by an attacker)
    and provides information about when they can try again.
    """
    from .email_utils import send_security_email

    # Try to find the user by username (which is email in our system)
    try:
        user = User.objects.get(email__iexact=username)
    except User.DoesNotExist:
        # Don't reveal whether user exists - just log and return
        logger.info(f"Lockout for non-existent user: {username}")
        return

    # Get client IP for security context
    ip_address = _get_client_ip(request)

    # Calculate when lockout expires
    cooloff_time = getattr(settings, "AXES_COOLOFF_TIME", 1)  # hours
    lockout_until = datetime.now().strftime("%H:%M") + f" + {cooloff_time} hour(s)"

    # Send notification email
    try:
        send_security_email(
            user=user,
            subject="Security Alert: Account Temporarily Locked",
            template_name="emails/security/account_lockout.md",
            context={
                "user": user,
                "ip_address": ip_address,
                "lockout_until": lockout_until,
                "cooloff_hours": cooloff_time,
                "failure_limit": getattr(settings, "AXES_FAILURE_LIMIT", 5),
            },
        )
        logger.info(f"Sent lockout notification to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send lockout notification to {user.email}: {e}")

    # Log the lockout event
    from checktick_app.surveys.models import AuditLog

    AuditLog.log_security_event(
        action=AuditLog.Action.ACCOUNT_LOCKED,
        actor=user,
        request=request,
        message=f"Account locked after {getattr(settings, 'AXES_FAILURE_LIMIT', 5)} failed login attempts",
        username_attempted=username,
    )


def _get_client_ip(request) -> str:
    """Extract client IP address from request, handling proxies."""
    if request is None:
        return "Unknown"

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        # Take the first IP in the chain (original client)
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "Unknown")


def _send_admin_login_notification(user, request, audit_log):
    """Send email notification when admin/staff user logs in.

    For healthcare apps with patient data, this provides an audit trail
    and allows admins to detect unauthorized access quickly.
    """
    from .email_utils import send_security_email

    # Get all superusers to notify (excluding the one logging in)
    superusers = User.objects.filter(is_superuser=True, is_active=True).exclude(
        id=user.id
    )

    # Extract request details
    ip_address = _get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")[:200]
    timestamp = audit_log.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Determine access level
    access_level = "Superuser" if user.is_superuser else "Staff"

    try:
        # Send notification to the user who logged in
        send_security_email(
            user=user,
            subject=f"Security Alert: Admin Login Detected - {user.email}",
            template_name="emails/security/admin_login_self.md",
            context={
                "user": user,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp": timestamp,
                "access_level": access_level,
            },
        )

        # Send notification to other superusers for monitoring
        for admin in superusers:
            send_security_email(
                user=admin,
                subject=f"Admin Access Alert: {access_level} Login - {user.email}",
                template_name="emails/security/admin_login_notification.md",
                context={
                    "admin": admin,
                    "logged_in_user": user,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "timestamp": timestamp,
                    "access_level": access_level,
                },
            )

        logger.info(
            f"Admin login notification sent for {user.email} (IP: {ip_address})"
        )
    except Exception as e:
        # Don't fail the login if email fails, but log it
        logger.error(f"Failed to send admin login notification: {e}")


def _send_admin_failed_login_notification(user, request, audit_log):
    """Send email when someone fails to log in to an admin/staff account.

    This helps detect brute force attacks or unauthorized access attempts
    against privileged accounts with access to patient data.
    """
    from .email_utils import send_security_email

    # Get all superusers to notify
    superusers = User.objects.filter(is_superuser=True, is_active=True)

    ip_address = _get_client_ip(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")[:200]
    timestamp = audit_log.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")
    access_level = "Superuser" if user.is_superuser else "Staff"

    try:
        # Notify the account owner
        send_security_email(
            user=user,
            subject=f"Security Alert: Failed Login Attempt to Your {access_level} Account",
            template_name="emails/security/admin_failed_login.md",
            context={
                "user": user,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "timestamp": timestamp,
                "access_level": access_level,
                "was_you": False,
            },
        )

        # Notify other superusers
        for admin in superusers.exclude(id=user.id):
            send_security_email(
                user=admin,
                subject=f"Security Alert: Failed {access_level} Login Attempt - {user.email}",
                template_name="emails/security/admin_failed_login_notification.md",
                context={
                    "admin": admin,
                    "targeted_user": user,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "timestamp": timestamp,
                    "access_level": access_level,
                },
            )

        logger.warning(
            f"Admin failed login notification sent for {user.email} (IP: {ip_address})"
        )
    except Exception as e:
        logger.error(f"Failed to send admin failed login notification: {e}")


# Security audit logging for authentication events
@receiver(post_save, sender=User)
def log_user_creation(sender, instance, created, **kwargs):
    """Log when a new user account is created."""
    if created:
        from checktick_app.surveys.models import AuditLog

        AuditLog.log_security_event(
            action=AuditLog.Action.USER_CREATED,
            actor=instance,
            message=f"User account created: {instance.email}",
        )


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    """Log successful login events and send admin access notifications."""
    from checktick_app.surveys.models import AuditLog

    # Log the login event
    audit_log = AuditLog.log_security_event(
        action=AuditLog.Action.LOGIN_SUCCESS,
        actor=user,
        request=request,
        message=f"Successful login for {user.email}",
    )

    # Send email notification for admin/staff logins (healthcare security requirement)
    if user.is_staff or user.is_superuser:
        _send_admin_login_notification(user, request, audit_log)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    """Log logout events."""
    if user is None:
        return

    from checktick_app.surveys.models import AuditLog

    AuditLog.log_security_event(
        action=AuditLog.Action.LOGOUT,
        actor=user,
        request=request,
        message=f"User logged out: {user.email}",
    )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempts and notify admins of suspicious activity."""
    from checktick_app.surveys.models import AuditLog

    username = credentials.get("username", "")

    # Log the failed attempt
    audit_log = AuditLog.log_security_event(
        action=AuditLog.Action.LOGIN_FAILED,
        request=request,
        message=f"Failed login attempt for username: {username}",
        username_attempted=username,
    )

    # Check if this is an admin account being targeted
    try:
        user = User.objects.get(email__iexact=username)
        if user.is_staff or user.is_superuser:
            _send_admin_failed_login_notification(user, request, audit_log)
    except User.DoesNotExist:
        # Don't reveal whether admin account exists
        pass
