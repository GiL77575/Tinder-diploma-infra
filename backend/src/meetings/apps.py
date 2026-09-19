from django.apps import AppConfig


class MeetingsConfig(AppConfig):
    """Зустрічі (BFF): створення, учасники, груповий чат."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'meetings'
