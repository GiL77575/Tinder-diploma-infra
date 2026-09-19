"""Чат за матчем або за зустріччю, і підписки на push-сповіщення."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from matching.models import Match
from profiles.models import SearchMode


class Conversation(models.Model):
    """Чат 1-to-1 за матчем або груповий чат зустрічі (BFF)."""

    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name='conversation',
        null=True,
        blank=True,
    )
    meeting = models.OneToOneField(
        'meetings.Meeting',
        on_delete=models.CASCADE,
        related_name='conversation',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    (Q(match__isnull=False) & Q(meeting__isnull=True))
                    | (Q(match__isnull=True) & Q(meeting__isnull=False))
                ),
                name='conversation_exactly_one_owner',
            ),
        ]

    def __str__(self):
        if self.match_id:
            return f'Conversation for match {self.match_id}'
        return f'Conversation for meeting {self.meeting_id}'

    @property
    def mode(self):
        """Режим чату: знайомства/друзі для матчу; завжди BFF для зустрічі."""
        if self.meeting_id:
            return SearchMode.BFF
        return self.match.mode

    @property
    def is_meeting_chat(self):
        return self.meeting_id is not None


class Message(models.Model):
    """Повідомлення в чаті: текст і/або фото."""

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
    edited_at = models.DateTimeField(null=True, blank=True)
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
