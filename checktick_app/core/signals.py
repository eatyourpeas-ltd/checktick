"""Signal handlers for core app models."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile

User = get_user_model()


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
