"""Моделі профілю: спільна анкета, окремі контури Dating/BFF, фото і теги."""

from datetime import date

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def calculate_age(birth_date):
    """Повних років на сьогодні за датою народження."""
    if birth_date is None:
        return None
    today = date.today()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


class Gender(models.TextChoices):
    MALE = 'male', 'Чоловік'
    FEMALE = 'female', 'Жінка'
    NON_BINARY = 'non_binary', 'Небінарний'
    OTHER = 'other', 'Інше'


class Orientation(models.TextChoices):
    STRAIGHT = 'straight', 'Гетеро'
    GAY = 'gay', 'Гей / лесбійка'
    BISEXUAL = 'bisexual', 'Бісексуал'
    OTHER = 'other', 'Інше'


class LookingFor(models.TextChoices):
    MALE = 'male', 'Хлопця'
    FEMALE = 'female', 'Дівчину'
    EVERYONE = 'everyone', 'Обох'


class RelationshipGoal(models.TextChoices):
    """Мета знайомства — що людина шукає в романтичному режимі."""
    SERIOUS = 'serious', 'Серйозні стосунки'
    DATING = 'dating', 'Побачення та флірт'
    CASUAL = 'casual', 'Вільні стосунки'


class PartnerHabitAttitude(models.TextChoices):
    """Ставлення до звички партнера (курить / вживає алкоголь)."""
    NEGATIVE = 'negative', 'Негативне'
    NEUTRAL = 'neutral', 'Нейтральне'
    POSITIVE = 'positive', 'Позитивне'


class MeetingFormat(models.TextChoices):
    """Формат майбутніх зустрічей із партнером."""
    IN_PERSON = 'in_person', 'Особисті зустрічі'
    ONLINE = 'online', 'Спілкування онлайн'
    BOTH = 'both', 'Обидва варіанти'


class AgePreference(models.TextChoices):
    """Вибагливість щодо віку партнера — обмежує чи розширює діапазон min/max."""
    NO_LIMIT = 'no_limit', 'Без обмежень'
    PEERS = 'peers', 'Однолітки'


class BffLookingFor(models.TextChoices):
    """Цілі спілкування в пошуку друзів («Що шукаєш») — можна обрати декілька."""
    HOBBY = 'hobby', 'Компанія для хобі'
    LANGUAGE = 'language', 'Мовний обмін'
    TRAVEL = 'travel', 'Подорожі'
    COWORKING = 'coworking', 'Коворкінг'
    WALKS = 'walks', 'Прогулянки'
    SOCIALIZING = 'socializing', 'Спілкування'
    BOARD_GAMES = 'board_games', 'Настілки/ігри'
    HANGOUT = 'hangout', 'Просто друзі'
    CULTURE = 'culture', 'Культурний відпочинок'


class SearchMode(models.TextChoices):
    DATING = 'dating', 'Знайомства'
    BFF = 'bff', 'Пошук друзів'


class SmokingHabit(models.TextChoices):
    NO = 'no', 'Не курю'
    SOMETIMES = 'sometimes', 'Інколи'
    YES = 'yes', 'Курю'


class ChildrenStatus(models.TextChoices):
    NO = 'no', 'Немає'
    HAVE = 'have', 'Є діти'
    WANT = 'want', 'Хочу дітей'
    UNSURE = 'unsure', 'Поки не знаю'


class AlcoholHabit(models.TextChoices):
    NO = 'no', "Не п'ю"
    SOMETIMES = 'sometimes', 'Інколи'
    YES = 'yes', 'Часто'


class SportFrequency(models.TextChoices):
    NO = 'no', 'Не займаюсь'
    SOMETIMES = 'sometimes', 'Інколи'
    YES = 'yes', 'Часто'


class PetsStatus(models.TextChoices):
    NO = 'no', 'Немає'
    HAVE = 'have', 'Є домашні тварини'


class ZodiacSign(models.TextChoices):
    ARIES = 'aries', 'Овен'
    TAURUS = 'taurus', 'Телець'
    GEMINI = 'gemini', 'Близнюки'
    CANCER = 'cancer', 'Рак'
    LEO = 'leo', 'Лев'
    VIRGO = 'virgo', 'Діва'
    LIBRA = 'libra', 'Терези'
    SCORPIO = 'scorpio', 'Скорпіон'
    SAGITTARIUS = 'sagittarius', 'Стрілець'
    CAPRICORN = 'capricorn', 'Козерог'
    AQUARIUS = 'aquarius', 'Водолій'
    PISCES = 'pisces', 'Риби'


class HobbyLevel(models.TextChoices):
    NOVICE = 'novice', 'Початківець'
    INTERMEDIATE = 'intermediate', 'Середній'
    PRO = 'pro', 'Профі'


class LanguageLevel(models.TextChoices):
    A1 = 'a1', 'A1'
    A2 = 'a2', 'A2'
    B1 = 'b1', 'B1'
    B2 = 'b2', 'B2'
    C1 = 'c1', 'C1'
    C2 = 'c2', 'C2'
    NATIVE = 'native', 'Рідна'


class ModerationStatus(models.TextChoices):
    PENDING = 'pending', 'На модерації'
    APPROVED = 'approved', 'Схвалено'
    SUSPENDED = 'suspended', 'Призупинено'


class PhotoStatus(models.TextChoices):
    PENDING = 'pending', 'На модерації'
    APPROVED = 'approved', 'Схвалено'
    REJECTED = 'rejected', 'Відхилено'


class TagCategory(models.TextChoices):
    INTEREST = 'interest', 'Інтерес'
    LANGUAGE = 'language', 'Мова'
    HOBBY = 'hobby', 'Хобі'


class Profile(models.Model):
    """Спільна анкета. Біо і теги по режимах — у ProfileMode / ProfileTag."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    display_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20, choices=Gender.choices)
    orientation = models.CharField(max_length=20, choices=Orientation.choices)
    job = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, default='')
    height_cm = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(120), MaxValueValidator(230)],
    )
    smoking = models.CharField(
        max_length=20,
        choices=SmokingHabit.choices,
        blank=True,
    )
    children = models.CharField(
        max_length=20,
        choices=ChildrenStatus.choices,
        blank=True,
    )
    alcohol = models.CharField(
        max_length=20,
        choices=AlcoholHabit.choices,
        blank=True,
    )
    sport = models.CharField(
        max_length=20,
        choices=SportFrequency.choices,
        blank=True,
    )
    pets = models.CharField(
        max_length=20,
        choices=PetsStatus.choices,
        blank=True,
    )
    zodiac_sign = models.CharField(
        max_length=20,
        choices=ZodiacSign.choices,
        blank=True,
    )
    active_mode = models.CharField(
        max_length=10,
        choices=SearchMode.choices,
        default=SearchMode.DATING,
    )
    is_discoverable = models.BooleanField(default=True)
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
        """Вік користувача для картки профілю."""
        return calculate_age(self.birth_date)

    def get_mode(self, mode):
        """Контур Dating або BFF, або None."""
        return self.modes.filter(mode=mode).first()

    def tags_for(self, mode, category):
        """Теги профілю в одному режимі й категорії (інтереси / хобі / мови)."""
        return self.profile_tags.filter(
            mode=mode,
            tag__category=category,
        ).select_related('tag')


class ProfileMode(models.Model):
    """Окремий контур профілю: знайомства або пошук друзів."""
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='modes',
    )
    mode = models.CharField(max_length=10, choices=SearchMode.choices)
    bio = models.TextField(max_length=500, blank=True)
    # Для Dating — одне значення (LookingFor). Для BFF — декілька цілей
    # спілкування (BffLookingFor), збережені через кому, напр. "hobby,walks".
    looking_for = models.CharField(max_length=150, blank=True)
    min_age = models.PositiveSmallIntegerField(default=18)
    max_age = models.PositiveSmallIntegerField(default=99)
    # Додаткові критерії романтичного контуру (заповнюються лише для Dating,
    # для BFF лишаються порожніми — за тим самим принципом, що і looking_for).
    age_preference = models.CharField(
        max_length=20,
        choices=AgePreference.choices,
        blank=True,
    )
    relationship_goal = models.CharField(
        max_length=20,
        choices=RelationshipGoal.choices,
        blank=True,
    )
    smoking_attitude = models.CharField(
        max_length=20,
        choices=PartnerHabitAttitude.choices,
        blank=True,
    )
    alcohol_attitude = models.CharField(
        max_length=20,
        choices=PartnerHabitAttitude.choices,
        blank=True,
    )
    meeting_format = models.CharField(
        max_length=20,
        choices=MeetingFormat.choices,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'mode'],
                name='unique_profile_mode',
            ),
        ]

    def __str__(self):
        return f'{self.profile} — {self.mode}'

    def looking_for_label(self):
        """Людською мовою: кого / що шукає в цьому режимі.

        Dating зберігає одне значення. BFF може мати декілька обраних цілей
        спілкування через кому — повертаємо їх підписи через кому.
        """
        if self.mode == SearchMode.DATING:
            return dict(LookingFor.choices).get(self.looking_for, '')
        labels = dict(BffLookingFor.choices)
        selected = [value for value in self.looking_for.split(',') if value]
        return ', '.join(labels.get(value, value) for value in selected)


class Photo(models.Model):
    """Фото профілю (Cloudinary або локальний /media/)."""
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='photos',
    )
    cloudinary_public_id = models.CharField(max_length=255)
    url = models.CharField(max_length=500)
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
    """Довідник інтересів, хобі та мов."""
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
    """Зв'язок профілю з тегом у конкретному режимі (+ рівень для хобі/мов)."""
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
    mode = models.CharField(
        max_length=10,
        choices=SearchMode.choices,
        default=SearchMode.DATING,
    )
    level = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['profile', 'tag', 'mode'],
                name='unique_profile_tag_per_mode',
            ),
        ]
        indexes = [
            models.Index(fields=['profile', 'mode']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f'{self.profile} — {self.tag} ({self.mode})'

    def level_label(self):
        """Підпис рівня: початківець/профі або A1–C2."""
        if self.tag.category == TagCategory.HOBBY:
            return dict(HobbyLevel.choices).get(self.level, self.level)
        if self.tag.category == TagCategory.LANGUAGE:
            return dict(LanguageLevel.choices).get(self.level, self.level)
        return self.level
