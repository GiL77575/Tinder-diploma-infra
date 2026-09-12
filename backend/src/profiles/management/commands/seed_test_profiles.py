"""Очищає тестові акаунти й створює 6 повних анкет (3 дівчини + 3 хлопці).

Анкеті мають максимальний набір інтересів/хобі/мов з однаковими рівнями,
тож вони проходять фільтри Dating і BFF і з’являються одне в одного в стрічці.

    python manage.py seed_test_profiles
"""

from datetime import date

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction

from matching.models import Block, Like, Match, Report
from profiles.models import (
    AgePreference,
    AlcoholHabit,
    BffLookingFor,
    ChildrenStatus,
    Gender,
    LookingFor,
    MeetingFormat,
    Orientation,
    PartnerHabitAttitude,
    PetsStatus,
    Photo,
    PhotoStatus,
    Profile,
    ProfileMode,
    ProfileTag,
    RelationshipGoal,
    SearchMode,
    SmokingHabit,
    SportFrequency,
    Tag,
    TagCategory,
)

User = get_user_model()

TEST_PASSWORD = 'Test1234!'
TEST_EMAIL_SUFFIX = '@crushme.test'

# Локальні HD-портрети (≈2000px), щоб на широких екранах не милилися.
PHOTO_SETS = {
    'sofia': ['sofia-1.jpg', 'sofia-2.jpg', 'sofia-3.jpg'],
    'maria': ['maria-1.jpg', 'maria-2.jpg', 'maria-3.jpg'],
    'anna': ['anna-1.jpg', 'anna-2.jpg', 'anna-3.jpg'],
    'maksym': ['maksym-1.jpg', 'maksym-2.jpg', 'maksym-3.jpg'],
    'artem': ['artem-1.jpg', 'artem-2.jpg', 'artem-3.jpg'],
    'dmytro': ['dmytro-1.jpg', 'dmytro-2.jpg', 'dmytro-3.jpg'],
}


def _birth_date_for_age(age):
    today = date.today()
    return date(today.year - age, 3, 15)


def _portrait_url(filename):
    return f'/static/img/test-portraits/{filename}'


PROFILES = [
    {
        'email': f'sofia{TEST_EMAIL_SUFFIX}',
        'username': 'sofia',
        'display_name': 'Софія',
        'gender': Gender.FEMALE,
        'age': 24,
        'job': 'Дизайнерка',
        'height_cm': 168,
        'zodiac_sign': 'libra',
        'looking_for': LookingFor.MALE,
        'relationship_goal': RelationshipGoal.SERIOUS,
        'dating_bio': 'Люблю каву, кіно і довгі прогулянки містом. Шукаю щире спілкування без поспіху.',
        'bff_bio': 'Шукаю компанію для мовної практики, велопрогулянок і настілок у вихідні.',
    },
    {
        'email': f'maria{TEST_EMAIL_SUFFIX}',
        'username': 'maria',
        'display_name': 'Марія',
        'gender': Gender.FEMALE,
        'age': 26,
        'job': 'Викладачка',
        'height_cm': 165,
        'zodiac_sign': 'taurus',
        'looking_for': LookingFor.MALE,
        'relationship_goal': RelationshipGoal.DATING,
        'dating_bio': 'Читаю, готую і обожнюю подорожі. Відкрита до нових знайомств і теплих розмов.',
        'bff_bio': 'Буду рада друзям для прогулянок, кіно й спільної кулінарії.',
    },
    {
        'email': f'anna{TEST_EMAIL_SUFFIX}',
        'username': 'anna',
        'display_name': 'Анна',
        'gender': Gender.FEMALE,
        'age': 23,
        'job': 'Маркетологиня',
        'height_cm': 170,
        'zodiac_sign': 'gemini',
        'looking_for': LookingFor.MALE,
        'relationship_goal': RelationshipGoal.SERIOUS,
        'dating_bio': 'Спорт зранку, музика ввечері. Шукаю людину, з якою можна і помовчати, і посміятись.',
        'bff_bio': 'Люблю танці, фотографію і вивчати мови — шукаю однодумців без драми.',
    },
    {
        'email': f'maksym{TEST_EMAIL_SUFFIX}',
        'username': 'maksym',
        'display_name': 'Максим',
        'gender': Gender.MALE,
        'age': 25,
        'job': 'Розробник',
        'height_cm': 182,
        'zodiac_sign': 'leo',
        'looking_for': LookingFor.FEMALE,
        'relationship_goal': RelationshipGoal.SERIOUS,
        'dating_bio': 'Працюю в IT, після роботи — спорт або настілки. Ціную чесність і почуття гумору.',
        'bff_bio': 'Шукаю компанію для бігу, велопрогулянок і мовного обміну.',
    },
    {
        'email': f'artem{TEST_EMAIL_SUFFIX}',
        'username': 'artem',
        'display_name': 'Артем',
        'gender': Gender.MALE,
        'age': 27,
        'job': 'Архітектор',
        'height_cm': 178,
        'zodiac_sign': 'scorpio',
        'looking_for': LookingFor.FEMALE,
        'relationship_goal': RelationshipGoal.DATING,
        'dating_bio': 'Люблю мистецтво, кіно і тихі вечори з хорошою розмовою. Відкритий до знайомств.',
        'bff_bio': 'Радий новим друзям для походів, настілок і спільного навчання мов.',
    },
    {
        'email': f'dmytro{TEST_EMAIL_SUFFIX}',
        'username': 'dmytro',
        'display_name': 'Дмитро',
        'gender': Gender.MALE,
        'age': 24,
        'job': 'Фотограф',
        'height_cm': 180,
        'zodiac_sign': 'aries',
        'looking_for': LookingFor.FEMALE,
        'relationship_goal': RelationshipGoal.DATING,
        'dating_bio': 'Фотографую місто і людей. Шукаю когось, з ким можна поїхати на вихідні кудись нове.',
        'bff_bio': 'Відкритий до дружби: прогулянки, фотопрогулянки, кіно й настільні ігри.',
    },
]


class Command(BaseCommand):
    help = 'Видаляє всі не-адмін акаунти і створює 6 тестових анкет (3 дівчини, 3 хлопці).'

    def handle(self, *args, **options):
        with transaction.atomic():
            removed = self._wipe_user_data()
            created = [self._create_profile(spec) for spec in PROFILES]

        self.stdout.write(self.style.WARNING(f'Видалено не-адмін користувачів: {removed}'))
        self.stdout.write(self.style.SUCCESS(
            f'Створено {len(created)} анкет. Пароль для всіх: {TEST_PASSWORD}',
        ))
        for spec in PROFILES:
            self.stdout.write(f'  {spec["display_name"]}  {spec["email"]}')

    def _wipe_user_data(self):
        """Прибирає лайки, матчі, скарги, сесії і всіх користувачів без staff/superuser."""
        Like.objects.all().delete()
        Match.objects.all().delete()
        Block.objects.all().delete()
        Report.objects.all().delete()
        Session.objects.all().delete()
        stale = User.objects.filter(is_staff=False, is_superuser=False)
        count = stale.count()
        stale.delete()
        return count

    def _create_profile(self, spec):
        user = User.objects.create_user(
            email=spec['email'],
            username=spec['username'],
            password=TEST_PASSWORD,
            is_profile_complete=True,
        )
        EmailAddress.objects.update_or_create(
            user=user,
            email=spec['email'],
            defaults={'verified': True, 'primary': True},
        )

        profile = Profile.objects.create(
            user=user,
            display_name=spec['display_name'],
            birth_date=_birth_date_for_age(spec['age']),
            gender=spec['gender'],
            orientation=Orientation.STRAIGHT,
            job=spec['job'],
            city='Київ',
            height_cm=spec['height_cm'],
            smoking=SmokingHabit.NO,
            children=ChildrenStatus.NO,
            alcohol=AlcoholHabit.SOMETIMES,
            sport=SportFrequency.SOMETIMES,
            pets=PetsStatus.HAVE,
            zodiac_sign=spec['zodiac_sign'],
            active_mode=SearchMode.DATING,
            is_discoverable=True,
        )

        ProfileMode.objects.create(
            profile=profile,
            mode=SearchMode.DATING,
            bio=spec['dating_bio'],
            looking_for=spec['looking_for'],
            min_age=18,
            max_age=40,
            age_preference=AgePreference.NO_LIMIT,
            relationship_goal=spec['relationship_goal'],
            smoking_attitude=PartnerHabitAttitude.NEUTRAL,
            alcohol_attitude=PartnerHabitAttitude.NEUTRAL,
            meeting_format=MeetingFormat.BOTH,
        )
        ProfileMode.objects.create(
            profile=profile,
            mode=SearchMode.BFF,
            bio=spec['bff_bio'],
            looking_for=','.join(value for value, _ in BffLookingFor.choices),
            min_age=18,
            max_age=99,
        )

        self._add_all_tags(profile)
        self._add_photos(profile)
        return profile

    def _add_all_tags(self, profile):
        """Максимальний набір тегів з однаковими рівнями — щоб стрічка не була порожня."""
        for tag in Tag.objects.filter(category=TagCategory.INTEREST):
            ProfileTag.objects.create(profile=profile, tag=tag, mode=SearchMode.DATING)
            ProfileTag.objects.create(profile=profile, tag=tag, mode=SearchMode.BFF)

        for tag in Tag.objects.filter(category=TagCategory.HOBBY):
            ProfileTag.objects.create(
                profile=profile, tag=tag, mode=SearchMode.BFF, level='intermediate',
            )

        language_levels = {
            'Українська': 'native',
            'Англійська': 'b2',
            'Польська': 'b1',
            'Німецька': 'a2',
            'Французька': 'a2',
            'Іспанська': 'a2',
            'Італійська': 'a1',
            'Шведська': 'a1',
            'Чеська': 'a1',
            'Японська': 'a1',
            'Китайська': 'a1',
            'Корейська': 'a1',
        }
        for tag in Tag.objects.filter(category=TagCategory.LANGUAGE):
            ProfileTag.objects.create(
                profile=profile,
                tag=tag,
                mode=SearchMode.BFF,
                level=language_levels.get(tag.name, 'a1'),
            )

    def _add_photos(self, profile):
        filenames = PHOTO_SETS[profile.user.username]
        for order, filename in enumerate(filenames):
            Photo.objects.create(
                profile=profile,
                cloudinary_public_id=f'test-portrait:{profile.user.username}:{order}',
                url=_portrait_url(filename),
                order=order,
                is_primary=order == 0,
                status=PhotoStatus.APPROVED,
            )
