"""Чат за матчем і підписки на push-сповіщення."""

from django.conf import settings
from django.db import models

from matching.models import Match


class Conversation(models.Model):
    """Один чат на один матч (Dating і BFF ізольовані)."""

    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name='conversation',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Conversation for match {self.match_id}'

    @property
    def mode(self):
        """Режим чату: знайомства або пошук друзів."""
        return self.match.mode


class Message(models.Model):
    """Повідомлення в чаті матчу: текст і/або фото."""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='messages_sent',
    )
    text = models.TextField(max_length=2000, blank=True)
    image_url = models.CharField(max_length=500, blank=True, default='')
    image_public_id = models.CharField(max_length=255, blank=True, default='')
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f'Message {self.pk} in conversation {self.conversation_id}'


class PushSubscription(models.Model):
    """Web Push підписка браузера користувача."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.TextField(unique=True)
    p256dh_key = models.CharField(max_length=255)
    auth_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f'PushSubscription for {self.user.email}'
