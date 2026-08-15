"""Вхід за email або username (без урахування регістру)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """Стандартний Django backend, але логін може бути email або username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        """Повертає користувача, якщо пароль правильний."""
        if username is None:
            username = kwargs.get('email')
        try:
            user = User.objects.get(
                Q(username__iexact=username) | Q(email__iexact=username)
            )
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
