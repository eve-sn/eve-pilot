from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.finance"
    verbose_name = "Finance"

    def ready(self):
        # Connecte les signaux d'auto-generation des ecritures comptables.
        from apps.finance import signals  # noqa: F401
