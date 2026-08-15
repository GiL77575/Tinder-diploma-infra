from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Додаток акаунтів: User, вхід і реєстрація."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
