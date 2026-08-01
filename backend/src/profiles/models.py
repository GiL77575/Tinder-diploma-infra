from django.conf import settings
from django.db import models


class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'
    NON_BINARY = 'non_binary', 'Non-binary'
    OTHER = 'other', 'Other'


class Orientation(models.TextChoices):
    STRAIGHT = 'straight', 'Straight'
    GAY = 'gay', 'Gay'
    BISEXUAL = 'bisexual', 'Bisexual'
    OTHER = 'other', 'Other'


class LookingFor(models.TextChoices):
    MALE = 'male', 'Men'
    FEMALE = 'female', 'Women'
    EVERYONE = 'everyone', 'Everyone'


class SearchMode(models.TextChoices):
    DATING = 'dating', 'Dating'
    BFF = 'bff', 'Friend Finder'


class ModerationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    APPROVED = 'approved', 'Approved'
    SUSPENDED = 'suspended', 'Suspended'


class PhotoStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class TagCategory(models.TextChoices):
    INTEREST = 'interest', 'Interest'
    LANGUAGE = 'language', 'Language'
    HOBBY = 'hobby', 'Hobby'
    ACTIVITY = 'activity', 'Activity'


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    display_name = models.CharField(max_length=100)
    bio = models.TextField(max_length=500, blank=True)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    orientation = models.CharField(max_length=20, choices=Orientation.choices)
    job = models.CharField(max_length=100, blank=True)
    active_mode = models.CharField(
        max_length=10,
        choices=SearchMode.choices,
        default=SearchMode.DATING,
    )
    looking_for = models.CharField(
        max_length=20,
        choices=LookingFor.choices,
        blank=True,
    )
    min_age = models.PositiveSmallIntegerField(default=18)
    max_age = models.PositiveSmallIntegerField(default=99)
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.APPROVED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name

    @property
    def age(self):
        from datetime import date

        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - (
                (today.month, today.day)
                < (self.birth_date.month, self.birth_date.day)
            )
        )

    @property
    def is_visible(self):
        return self.moderation_status == ModerationStatus.APPROVED


class Photo(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    cloudinary_public_id = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=PhotoStatus.choices,
        default=PhotoStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['profile', 'order']),
        ]

    def __str__(self):
        return f'Photo {self.pk} — {self.profile}'


class Tag(models.Model):
    name = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=TagCategory.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'category'],
                name='unique_tag_name_per_category',
            ),
        ]
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'


class ProfileTag(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='profile_tags',
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name='profile_tags',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'tag'],
                name='unique_profile_tag',
            ),
        ]
        indexes = [
            models.Index(fields=['profile']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f'{self.profile} — {self.tag}'
