"""Моделі зустрічей (BFF): Meeting та учасники."""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class MeetingStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Meeting(models.Model):
    """Одна активна зустріч на користувача; груповий чат через Conversation."""

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_meetings',
    )
    title = models.CharField(max_length=120)
    location = models.CharField(max_length=200)
    description = models.TextField(max_length=1000)
    starts_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=MeetingStatus.choices,
        default=MeetingStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['creator'],
                condition=models.Q(status=MeetingStatus.ACTIVE),
                name='uniq_active_meeting_per_creator',
            ),
        ]
        indexes = [
            models.Index(fields=['creator', 'status']),
            models.Index(fields=['status', 'starts_at']),
        ]

    def __str__(self):
        return f'Meeting {self.pk}: {self.title} ({self.status})'

    @property
    def is_past(self):
        return self.starts_at <= timezone.now()

    @property
    def chat_closes_at(self):
        """Кінець календарного дня наступного після дати зустрічі (локальний TZ)."""
        local_start = timezone.localtime(self.starts_at)
        close_date = local_start.date() + timedelta(days=1)
        naive_end = datetime.combine(close_date, time(23, 59, 59))
        return timezone.make_aware(naive_end, timezone.get_current_timezone())

    @property
    def is_chat_open(self):
        if self.status == MeetingStatus.CANCELLED:
            return False
        return timezone.now() <= self.chat_closes_at

    def ensure_completed_if_due(self):
        """Якщо ACTIVE і час зустрічі минув — перевести в COMPLETED."""
        if self.status == MeetingStatus.ACTIVE and self.is_past:
            self.status = MeetingStatus.COMPLETED
            self.save(update_fields=['status', 'updated_at'])
        return self


class MeetingParticipant(models.Model):
    """Учасник зустрічі; creator додається при створенні."""

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name='participants',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meeting_participations',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['meeting', 'user'],
                name='uniq_meeting_participant',
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'meeting']),
        ]

    def __str__(self):
        return f'Participant {self.user_id} in meeting {self.meeting_id}'
