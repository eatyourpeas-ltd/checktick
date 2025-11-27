from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "checktick_app.core"
    verbose_name = "Core"

    def ready(self):
        """Import signal handlers when app is ready."""
        import checktick_app.core.signals  # noqa: F401
