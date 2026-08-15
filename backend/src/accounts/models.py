"""Користувач crush: вхід по email, прапорець завершеної анкети."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Акаунт: вхід по email, унікальний username для посилання на профіль."""

    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    is_profile_complete = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.email
