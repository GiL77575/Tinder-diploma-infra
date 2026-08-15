from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """Додаток профілів: анкета, фото, теги, dual-mode."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'
