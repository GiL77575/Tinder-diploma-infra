"""Тестові анкети для демо: портрети, живі описи, лайки Tyrion.

Не чіпає акаунти поза @crushme.test (Tyrion, адміни — цілі).

    python manage.py seed_demo_profiles --reset --like-target tyrion@gmail.com
    python manage.py seed_demo_profiles --meetings-only
"""

from datetime import date, timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from matching.models import Like
from meetings.services import MeetingError, create_meeting, get_active_meeting
from profiles.models import (
    BffLookingFor,
    Gender,
    LookingFor,
    Orientation,
    Photo,
    PhotoStatus,
    Profile,
    ProfileMode,
    ProfileTag,
    SearchMode,
    Tag,
    TagCategory,
)

User = get_user_model()

DEMO_EMAIL_SUFFIX = '@crushme.test'
DEMO_PASSWORD = 'DemoPass!1'
DEFAULT_LIKE_TARGET = 'tyrion@gmail.com'
TARGET_CITY = 'Київ'
FALLBACK_INTERESTS = ['Кава', 'Кіно', 'Музика', 'Подорожі', 'Спорт']
FALLBACK_HOBBIES = [('Малювання', 'novice'), ('Біг', 'intermediate')]
FALLBACK_LANGUAGES = [('Англійська', 'b2')]

PHOTO_SETS = {
    'sofia': ['sofia-1.jpg', 'sofia-2.jpg', 'sofia-3.jpg'],
    'maria': ['maria-1.jpg', 'maria-2.jpg', 'maria-3.jpg'],
    'anna': ['anna-1.jpg', 'anna-2.jpg', 'anna-3.jpg'],
    'maksym': ['maksym-1.jpg', 'maksym-2.jpg', 'maksym-3.jpg'],
    'artem': ['artem-1.jpg', 'artem-2.jpg', 'artem-3.jpg'],
    'dmytro': ['dmytro-1.jpg', 'dmytro-2.jpg', 'dmytro-3.jpg'],
}

PERSONAS = [
    {
        'username': 'sofia',
        'display_name': 'Софія',
        'gender': Gender.FEMALE,
        'age': 24,
        'job': 'Дизайнерка',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Мистецтво', 'Фотографія', 'Кава'],
        'dating_bio': (
            'Малюю інтерфейси вдень і людей у скетчбуку ввечері. '
            'Шукаю когось, з ким можна затишно помовчати в кав’ярні '
            'і так само легко піти на нічну прогулянку містом.'
        ),
        'bff_bio': (
            'Шукаю компанію для скетчів у парку, велопрогулянок '
            'і невимушеної англійської без оцінок і дедлайнів.'
        ),
    },
    {
        'username': 'maria',
        'display_name': 'Марія',
        'gender': Gender.FEMALE,
        'age': 26,
        'job': 'Викладачка',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Читання', 'Кулінарія', 'Подорожі'],
        'dating_bio': (
            'Вчу літературу, готую для друзів і збираю квитки в нові міста. '
            'Ціную теплі розмови, почуття гумору і людей, які не зникають '
            'після трьох повідомлень.'
        ),
        'bff_bio': (
            'Буду рада друзям для кіно, спільної кухні й мовного обміну. '
            'Можна приходити навіть якщо трохи соромишся — тут без драми.'
        ),
    },
    {
        'username': 'anna',
        'display_name': 'Анна',
        'gender': Gender.FEMALE,
        'age': 23,
        'job': 'Маркетологиня',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Танці', 'Музика', 'Фітнес'],
        'dating_bio': (
            'Спорт зранку, плейлисти ввечері. Шукаю людину, з якою можна '
            'і помовчати в метро, і сміятись до сліз на кухні о другій ночі.'
        ),
        'bff_bio': (
            'Люблю танці, фото і вивчати мови. Шукаю однодумців на прогулянки, '
            'настілки й інколи просто помовчати в навушниках поруч.'
        ),
    },
    {
        'username': 'maksym',
        'display_name': 'Максим',
        'gender': Gender.MALE,
        'age': 25,
        'job': 'Розробник',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Ігри', 'Технології', 'Спорт'],
        'dating_bio': (
            'Пишу код, після роботи — спорт або настілки. Ціную чесність, '
            'спокій і людей, які вміють сміятись із себе, а не лише з мемів.'
        ),
        'bff_bio': (
            'Шукаю компанію для бігу, велопрогулянок і мовного обміну. '
            'Можна приходити новачком — темп підлаштуємо.'
        ),
    },
    {
        'username': 'artem',
        'display_name': 'Артем',
        'gender': Gender.MALE,
        'age': 27,
        'job': 'Архітектор',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Мистецтво', 'Кіно', 'Подорожі'],
        'dating_bio': (
            'Малюю міста й люблю кіно, де нічого не вибухає перші сорок хвилин. '
            'Відкритий до знайомств без поспіху: спочатку кава, потім — як піде.'
        ),
        'bff_bio': (
            'Радий новим друзям для походів, настілок і спільного навчання мов. '
            'Можна просто походити містом і показувати одне одному улюблені двори.'
        ),
    },
    {
        'username': 'dmytro',
        'display_name': 'Дмитро',
        'gender': Gender.MALE,
        'age': 24,
        'job': 'Фотограф',
        'orientation': Orientation.STRAIGHT,
        'extra_interests': ['Фотографія', 'Подорожі', 'Музика'],
        'dating_bio': (
            'Фотографую місто на світанку, коли ще ніхто не позує. '
            'Шукаю когось, з ким можна зірватись на вихідні в нове місце '
            'і повернутись з історіями, а не лише зі сторіс.'
        ),
        'bff_bio': (
            'Відкритий до дружби: фотопрогулянки, кіно, настілки. '
            'Камера не обов’язкова — головне бажання вийти з дому.'
        ),
    },
]

MEETING_TEMPLATES = [
    {
        'title': 'Кава і розмова англійською',
        'place': 'кав’ярня в центрі',
        'description': (
            'Невимушена зустріч: попрактикуємо мову і просто познайомимось. '
            'Приходь, навіть якщо трохи хвилюєшся — без оцінок і драми.'
        ),
        'hour': 18,
    },
    {
        'title': 'Малювання в парку',
        'place': 'парк',
        'description': (
            'Беремо скетчбуки і малюємо все, що бачимо. Можна просто посидіти '
            'поруч, потеревенити і поділитися порадами.'
        ),
        'hour': 16,
    },
    {
        'title': 'Настілки ввечері',
        'place': 'антикафе',
        'description': (
            'Колода ігор уже є. Шукаю 2–4 людей на кооперативну партію '
            'і теплі розмови допізна.'
        ),
        'hour': 19,
    },
]


def _birth_date_for_age(age):
    today = date.today()
    return date(today.year - age, 3, 15)


def _portrait_url(filename):
    return f'/static/img/test-portraits/{filename}'


def _unique(names):
    seen = set()
    result = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _tag(category, name):
    return Tag.objects.filter(category=category, name=name).first()


class Command(BaseCommand):
    help = (
        'Створює 6 показових анкет з портретами й описами. '
        'Усі лайкають --like-target (за замовчуванням tyrion@gmail.com). '
        'Видаляє лише користувачів @crushme.test.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--like-target',
            dest='like_target',
            default=DEFAULT_LIKE_TARGET,
            help='Email, якому ВСІ демо-анкети ставлять лайк у Dating і BFF.',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=len(PERSONAS),
            help=f'Скільки анкет (за замовчуванням {len(PERSONAS)}).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Спочатку видалити всіх користувачів @crushme.test (Tyrion не чіпає).',
        )
        parser.add_argument(
            '--meetings-only',
            action='store_true',
            help='Не створювати анкети, лише додати зустрічі наявним BFF-демо.',
        )

    def handle(self, *args, **options):
        like_target_email = (options['like_target'] or DEFAULT_LIKE_TARGET).strip()
        count = max(1, options['count'])
        meetings_only = options['meetings_only']
        target_user = None

        if not meetings_only:
            try:
                target_user = User.objects.get(email__iexact=like_target_email)
            except User.DoesNotExist as exc:
                raise CommandError(
                    f'Користувача "{like_target_email}" немає. '
                    'Спочатку зареєструй Tyrion на проді або вкажи інший --like-target.'
                ) from exc
            if not getattr(target_user, 'is_profile_complete', False):
                self.stdout.write(self.style.WARNING(
                    f'{like_target_email} ще не заповнив анкету — стрічка може бути порожня, '
                    'доки не збережеш профіль.',
                ))

        if options['reset'] and not meetings_only:
            removed, _ = User.objects.filter(email__iendswith=DEMO_EMAIL_SUFFIX).delete()
            self.stdout.write(self.style.WARNING(
                f'Видалено попередніх демо (@crushme.test): {removed}',
            ))

        created = 0
        liked = 0

        if not meetings_only:
            compat = self._compat_from_target(target_user)
            with transaction.atomic():
                for index in range(count):
                    persona = self._persona_at(index)
                    user = self._upsert_user(persona)
                    profile = self._upsert_profile(user, persona, compat)
                    self._upsert_modes(profile, persona, compat)
                    self._upsert_tags(profile, persona, compat)
                    self._set_photos(profile, persona)
                    created += 1
                    liked += self._like_target(user, target_user)

            self.stdout.write(self.style.SUCCESS(
                f'Створено/оновлено {created} анкет. Пароль: {DEMO_PASSWORD}',
            ))
            self.stdout.write(
                f'Усі поставили лайк {like_target_email} '
                f'({liked} записів Dating+BFF). Лайкни у відповідь — буде метч.',
            )
            self.stdout.write(
                f'Сумісність зі стрічкою: місто «{compat["city"]}», '
                f'інтересів Dating {len(compat["dating_interests"])}, '
                f'хобі BFF {len(compat["bff_hobbies"])}, '
                f'мов BFF {len(compat["bff_languages"])}.',
            )
            if compat['used_fallback']:
                self.stdout.write(self.style.WARNING(
                    'У цілі мало тегів — підставлено запасний набір. '
                    'Щоб картки точно були в стрічці Tyrion, додай в його анкету '
                    'ті самі інтереси/хобі/мови (або будь-які 2 інтереси з каталогу '
                    'та хобі+мову з тим самим рівнем).',
                ))
            for index in range(count):
                persona = self._persona_at(index)
                self.stdout.write(f'  {persona["display_name"]}  {persona["email"]}')

        meetings_created = self._ensure_bff_meetings()
        if meetings_created:
            self.stdout.write(self.style.SUCCESS(
                f'Додано {meetings_created} зустрічей — у BFF з’явиться кнопка «Зустріч».',
            ))
        else:
            self.stdout.write('Нових зустрічей не додано: вони вже є або немає BFF-демо.')

    def _persona_at(self, index):
        base = PERSONAS[index % len(PERSONAS)]
        persona = dict(base)
        cycle = index // len(PERSONAS)
        if cycle == 0:
            persona['email'] = f'{base["username"]}{DEMO_EMAIL_SUFFIX}'
        else:
            suffix = cycle + 1
            persona['username'] = f'{base["username"]}{suffix}'
            persona['email'] = f'{base["username"]}{suffix}{DEMO_EMAIL_SUFFIX}'
        return persona

    def _compat_from_target(self, target_user):
        profile = getattr(target_user, 'profile', None)
        city = TARGET_CITY
        min_age, max_age = 18, 40
        dating_interests = []
        bff_hobbies = []
        bff_languages = []
        bff_looking_for = ''
        used_fallback = False

        if profile is not None:
            city = (profile.city or TARGET_CITY).strip() or TARGET_CITY
            dating_mode = profile.get_mode(SearchMode.DATING)
            bff_mode = profile.get_mode(SearchMode.BFF)
            if dating_mode:
                min_age = dating_mode.min_age or 18
                max_age = dating_mode.max_age or 40
            if bff_mode:
                bff_looking_for = (bff_mode.looking_for or '').strip()
            dating_interests = list(
                ProfileTag.objects.filter(
                    profile=profile,
                    mode=SearchMode.DATING,
                    tag__category=TagCategory.INTEREST,
                ).values_list('tag__name', flat=True)
            )
            bff_hobbies = list(
                ProfileTag.objects.filter(
                    profile=profile,
                    mode=SearchMode.BFF,
                    tag__category=TagCategory.HOBBY,
                ).values_list('tag__name', 'level')
            )
            bff_languages = list(
                ProfileTag.objects.filter(
                    profile=profile,
                    mode=SearchMode.BFF,
                    tag__category=TagCategory.LANGUAGE,
                ).values_list('tag__name', 'level')
            )

        if len(dating_interests) < 2:
            dating_interests = _unique(dating_interests + FALLBACK_INTERESTS)
            used_fallback = True
        if not bff_hobbies:
            bff_hobbies = list(FALLBACK_HOBBIES)
            used_fallback = True
        if not bff_languages:
            bff_languages = list(FALLBACK_LANGUAGES)
            used_fallback = True
        if not bff_looking_for:
            bff_looking_for = ','.join(value for value, _ in BffLookingFor.choices)
            used_fallback = True

        return {
            'city': city,
            'min_age': min_age,
            'max_age': max_age,
            'dating_interests': dating_interests,
            'bff_hobbies': bff_hobbies,
            'bff_languages': bff_languages,
            'bff_looking_for': bff_looking_for,
            'used_fallback': used_fallback,
        }

    def _upsert_user(self, persona):
        user, _ = User.objects.update_or_create(
            email=persona['email'],
            defaults={
                'username': persona['username'],
                'is_profile_complete': True,
            },
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        EmailAddress.objects.update_or_create(
            user=user,
            email=persona['email'].lower(),
            defaults={'verified': True, 'primary': True},
        )
        return user

    def _upsert_profile(self, user, persona, compat):
        age = persona['age']
        if age < compat['min_age']:
            age = compat['min_age']
        if age > compat['max_age']:
            age = compat['max_age']
        profile, _ = Profile.objects.update_or_create(
            user=user,
            defaults={
                'display_name': persona['display_name'],
                'birth_date': _birth_date_for_age(age),
                'gender': persona['gender'],
                'orientation': persona['orientation'],
                'job': persona.get('job') or '',
                'city': compat['city'],
                'is_discoverable': True,
                'active_mode': SearchMode.DATING,
            },
        )
        return profile

    def _upsert_modes(self, profile, persona, compat):
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.DATING,
            defaults={
                'bio': persona['dating_bio'],
                'looking_for': LookingFor.EVERYONE,
                'min_age': 18,
                'max_age': 40,
            },
        )
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.BFF,
            defaults={
                'bio': persona['bff_bio'],
                'looking_for': compat['bff_looking_for'],
                'min_age': 18,
                'max_age': 99,
            },
        )

    def _upsert_tags(self, profile, persona, compat):
        profile.profile_tags.all().delete()
        dating_names = _unique(list(compat['dating_interests']) + list(persona.get('extra_interests') or []))
        for name in dating_names:
            tag = _tag(TagCategory.INTEREST, name)
            if tag is None:
                continue
            ProfileTag.objects.create(
                profile=profile, tag=tag, mode=SearchMode.DATING,
            )
        seen_hobbies = set()
        for name, level in compat['bff_hobbies']:
            if name in seen_hobbies:
                continue
            seen_hobbies.add(name)
            tag = _tag(TagCategory.HOBBY, name)
            if tag is None:
                continue
            ProfileTag.objects.create(
                profile=profile, tag=tag, mode=SearchMode.BFF, level=level or 'novice',
            )
        seen_langs = set()
        for name, level in compat['bff_languages']:
            if name in seen_langs:
                continue
            seen_langs.add(name)
            tag = _tag(TagCategory.LANGUAGE, name)
            if tag is None:
                continue
            ProfileTag.objects.create(
                profile=profile, tag=tag, mode=SearchMode.BFF, level=level or 'a1',
            )

    def _set_photos(self, profile, persona):
        slug = persona['username']
        while slug and slug[-1].isdigit():
            slug = slug[:-1]
        filenames = PHOTO_SETS.get(slug) or PHOTO_SETS['sofia']
        profile.photos.all().delete()
        for order, filename in enumerate(filenames):
            Photo.objects.create(
                profile=profile,
                cloudinary_public_id=f'test-portrait:{persona["username"]}:{order}',
                url=_portrait_url(filename),
                order=order,
                is_primary=order == 0,
                status=PhotoStatus.APPROVED,
            )

    def _like_target(self, user, target_user):
        if user.id == target_user.id:
            return 0
        created = 0
        for mode in (SearchMode.DATING, SearchMode.BFF):
            Like.objects.update_or_create(
                from_user=user,
                to_user=target_user,
                mode=mode,
                defaults={'is_positive': True},
            )
            created += 1
        return created

    def _ensure_bff_meetings(self):
        candidates = list(
            User.objects
            .filter(email__iendswith=DEMO_EMAIL_SUFFIX)
            .filter(profile__modes__mode=SearchMode.BFF)
            .select_related('profile')
            .distinct()
            .order_by('id')
        )
        without_meeting = []
        already = 0
        for user in candidates:
            if get_active_meeting(user) is not None:
                already += 1
            else:
                without_meeting.append(user)
        want = min(len(MEETING_TEMPLATES), max(0, len(candidates)))
        need = max(0, want - already)
        created = 0
        for index, user in enumerate(without_meeting[:need]):
            template = MEETING_TEMPLATES[index % len(MEETING_TEMPLATES)]
            city = (getattr(user.profile, 'city', None) or TARGET_CITY).strip() or TARGET_CITY
            starts_at = self._future_meeting_start(days_ahead=3 + index, hour=template['hour'])
            try:
                create_meeting(
                    user,
                    title=template['title'],
                    location=f'{city}, {template["place"]}',
                    description=template['description'],
                    starts_at=starts_at,
                )
                created += 1
            except MeetingError as exc:
                self.stdout.write(self.style.WARNING(
                    f'Не вдалося створити зустріч для {user.email}: {exc}',
                ))
        return created

    def _future_meeting_start(self, days_ahead, hour):
        now = timezone.localtime(timezone.now())
        starts = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=0, second=0, microsecond=0,
        )
        if starts <= now:
            starts = starts + timedelta(days=1)
        return starts
