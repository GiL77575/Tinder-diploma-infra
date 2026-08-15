"""Лайки, матчі, блокування та скарги (окремо для Dating і BFF)."""

from django.conf import settings
from django.db import models

from profiles.models import SearchMode


class Like(models.Model):
    """Свайп: лайк або пас від одного користувача до іншого в одному режимі."""

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes_sent',
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes_received',
    )
    mode = models.CharField(max_length=10, choices=SearchMode.choices)
    is_positive = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['from_user', 'to_user', 'mode'],
                name='unique_like_per_mode',
            ),
            models.CheckConstraint(
                check=~models.Q(from_user=models.F('to_user')),
                name='like_different_users',
            ),
        ]
        indexes = [
            models.Index(fields=['from_user', 'mode']),
            models.Index(fields=['to_user', 'mode', 'is_positive']),
        ]

    def __str__(self):
        action = 'like' if self.is_positive else 'pass'
        return f'{self.from_user} → {self.to_user} ({action}, {self.mode})'


class Match(models.Model):
    """Взаємний лайк у одному режимі; user_a.id завжди менший за user_b.id."""

    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='matches_as_a',
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='matches_as_b',
    )
    mode = models.CharField(max_length=10, choices=SearchMode.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user_a', 'user_b', 'mode'],
                name='unique_match_per_mode',
            ),
            models.CheckConstraint(
                check=models.Q(user_a__lt=models.F('user_b')),
                name='match_canonical_user_order',
            ),
        ]

    def __str__(self):
        return f'Match: {self.user_a} ↔ {self.user_b} ({self.mode})'

    def other_user(self, user):
        """Друга сторона матчу відносно переданого користувача."""
        return self.user_b if user == self.user_a else self.user_a


class Block(models.Model):
    """Блок: blocker більше не бачить blocked і навпаки."""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocks_sent',
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocks_received',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['blocker', 'blocked'],
                name='unique_block',
            ),
            models.CheckConstraint(
                check=~models.Q(blocker=models.F('blocked')),
                name='block_different_users',
            ),
        ]

    def __str__(self):
        return f'{self.blocker} blocked {self.blocked}'


class ReportReason(models.TextChoices):
    SPAM = 'spam', 'Спам'
    HARASSMENT = 'harassment', 'Переслідування'
    FAKE_PROFILE = 'fake_profile', 'Фейковий профіль'
    INAPPROPRIATE = 'inappropriate_content', 'Неприйнятний контент'
    OTHER = 'other', 'Інше'


class ReportStatus(models.TextChoices):
    PENDING = 'pending', 'Очікує'
    RESOLVED = 'resolved', 'Розглянуто'
    DISMISSED = 'dismissed', 'Відхилено'


class Report(models.Model):
    """Скарга на користувача для модерації."""

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_sent',
    )
    reported = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
    )
    reason = models.CharField(max_length=30, choices=ReportReason.choices)
    details = models.TextField(max_length=1000, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Report {self.pk}: {self.reporter} → {self.reported}'
