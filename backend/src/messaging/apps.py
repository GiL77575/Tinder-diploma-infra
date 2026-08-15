from django.apps import AppConfig


class MessagingConfig(AppConfig):
    """Додаток повідомлень: чат матчу і push."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'messaging'
