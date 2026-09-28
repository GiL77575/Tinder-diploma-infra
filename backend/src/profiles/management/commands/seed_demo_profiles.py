"""Демо-анкети: 20 Dating + 20 BFF з зустрічами. Усі лайкають Tyrion.

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
    ModerationStatus,
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
DEFAULT_DATING_COUNT = 20
DEFAULT_BFF_COUNT = 20
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

# 20 унікальних людей; фото циклюються з 6 портретних сетів.
NAME_POOL = [
    {'slug': 'sofia', 'display_name': 'Софія', 'gender': Gender.FEMALE, 'age': 24, 'job': 'Дизайнерка', 'photo': 'sofia'},
    {'slug': 'maria', 'display_name': 'Марія', 'gender': Gender.FEMALE, 'age': 26, 'job': 'Викладачка', 'photo': 'maria'},
    {'slug': 'anna', 'display_name': 'Анна', 'gender': Gender.FEMALE, 'age': 23, 'job': 'Маркетологиня', 'photo': 'anna'},
    {'slug': 'olena', 'display_name': 'Олена', 'gender': Gender.FEMALE, 'age': 27, 'job': 'Аналітикиня', 'photo': 'maria'},
    {'slug': 'iryna', 'display_name': 'Ірина', 'gender': Gender.FEMALE, 'age': 25, 'job': 'HR', 'photo': 'sofia'},
    {'slug': 'nastya', 'display_name': 'Настя', 'gender': Gender.FEMALE, 'age': 22, 'job': 'Ілюстраторка', 'photo': 'anna'},
    {'slug': 'katya', 'display_name': 'Катя', 'gender': Gender.FEMALE, 'age': 28, 'job': 'Журналістка', 'photo': 'maria'},
    {'slug': 'yulia', 'display_name': 'Юля', 'gender': Gender.FEMALE, 'age': 24, 'job': 'Бариста', 'photo': 'sofia'},
    {'slug': 'vika', 'display_name': 'Віка', 'gender': Gender.FEMALE, 'age': 26, 'job': 'Продюсерка', 'photo': 'anna'},
    {'slug': 'dasha', 'display_name': 'Даша', 'gender': Gender.FEMALE, 'age': 23, 'job': 'Студентка', 'photo': 'maria'},
    {'slug': 'maksym', 'display_name': 'Максим', 'gender': Gender.MALE, 'age': 25, 'job': 'Розробник', 'photo': 'maksym'},
    {'slug': 'artem', 'display_name': 'Артем', 'gender': Gender.MALE, 'age': 27, 'job': 'Архітектор', 'photo': 'artem'},
    {'slug': 'dmytro', 'display_name': 'Дмитро', 'gender': Gender.MALE, 'age': 24, 'job': 'Фотограф', 'photo': 'dmytro'},
    {'slug': 'andriy', 'display_name': 'Андрій', 'gender': Gender.MALE, 'age': 26, 'job': 'Інженер', 'photo': 'maksym'},
    {'slug': 'oleg', 'display_name': 'Олег', 'gender': Gender.MALE, 'age': 29, 'job': 'Менеджер', 'photo': 'artem'},
    {'slug': 'taras', 'display_name': 'Тарас', 'gender': Gender.MALE, 'age': 23, 'job': 'Музикант', 'photo': 'dmytro'},
    {'slug': 'bohdan', 'display_name': 'Богдан', 'gender': Gender.MALE, 'age': 28, 'job': 'Тренер', 'photo': 'maksym'},
    {'slug': 'ivan', 'display_name': 'Іван', 'gender': Gender.MALE, 'age': 25, 'job': 'Юрист', 'photo': 'artem'},
    {'slug': 'pavlo', 'display_name': 'Павло', 'gender': Gender.MALE, 'age': 22, 'job': 'Дизайнер', 'photo': 'dmytro'},
    {'slug': 'denys', 'display_name': 'Денис', 'gender': Gender.MALE, 'age': 27, 'job': 'Кухар', 'photo': 'maksym'},
]

BIO_TEMPLATES = [
    {
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
    {'title': 'Кава і розмова англійською', 'place': 'кав’ярня в центрі', 'hour': 18,
     'description': 'Невимушена зустріч: попрактикуємо мову і просто познайомимось.'},
    {'title': 'Малювання в парку', 'place': 'парк', 'hour': 16,
     'description': 'Беремо скетчбуки і малюємо все, що бачимо. Можна просто посидіти поруч.'},
    {'title': 'Настілки ввечері', 'place': 'антикафе', 'hour': 19,
     'description': 'Колода ігор уже є. Шукаю 2–4 людей на кооперативну партію.'},
    {'title': 'Вечір кіно', 'place': 'кінотеатр', 'hour': 20,
     'description': 'Йдемо на вечірній сеанс і після — коротко обговорити, що сподобалось.'},
    {'title': 'Прогулянка набережною', 'place': 'набережна', 'hour': 17,
     'description': 'Неспішна прогулянка, кава з собою і розмови без порядку денного.'},
    {'title': 'Ранкова пробіжка', 'place': 'парк', 'hour': 8,
     'description': 'Легкий темп, можна йти пішки. Головне — вийти з дому.'},
    {'title': 'Настільний теніс', 'place': 'спортклуб', 'hour': 18,
     'description': 'Пара партій і чай після. Рівень будь-який.'},
    {'title': 'Книжковий клуб', 'place': 'книгарня', 'hour': 19,
     'description': 'Коротко про улюблені книжки. Можна прийти навіть без прочитаного.'},
    {'title': 'Фотопрогулянка', 'place': 'поділ', 'hour': 16,
     'description': 'Шукаємо цікаве світло у дворах. Камера чи телефон — як зручно.'},
    {'title': 'Настілки і чай', 'place': 'антикафе', 'hour': 15,
     'description': 'Кооператив на денний час. Буде тепло і без поспіху.'},
    {'title': 'Велопрогулянка', 'place': 'гідропарк', 'hour': 11,
     'description': 'Кілька кілометрів рівним темпом і пікнік на траві.'},
    {'title': 'Мовний обмін', 'place': 'кав’ярня', 'hour': 18,
     'description': 'По 20 хвилин українською та англійською. Без оцінок.'},
    {'title': 'Настілки: мафія', 'place': 'антикафе', 'hour': 20,
     'description': 'Класика на вечір. Шукаю 4–8 людей, новачкам теж раді.'},
    {'title': 'Виставка в музеї', 'place': 'музей', 'hour': 14,
     'description': 'Дивимось експозицію і після — кава з враженнями.'},
    {'title': 'Настільний футбол', 'place': 'бар', 'hour': 19,
     'description': 'Кілька партій і розмови. Можна приходити компанією.'},
    {'title': 'Йога в парку', 'place': 'парк', 'hour': 9,
     'description': 'Короткий сет на килимках. Килимок матиму з собою запасний.'},
    {'title': 'Настілки: квіз', 'place': 'паб', 'hour': 19,
     'description': 'Командна вікторина. Приходь навіть якщо не все знаєш.'},
    {'title': 'Вечір настілок', 'place': 'коворкінг', 'hour': 18,
     'description': 'Після роботи — партія і чай. Місця за столом є.'},
    {'title': 'Скетч у кав’ярні', 'place': 'кав’ярня', 'hour': 17,
     'description': 'Малюємо людей і чашки. Можна просто посидіти поруч.'},
    {'title': 'Нічна прогулянка', 'place': 'центр', 'hour': 21,
     'description': 'Тихе місто після дощу. Йдемо повільно і багато говоримо.'},
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


def _ensure_tag(category, name):
    name = (name or '').strip()
    if not name:
        return None
    tag, _ = Tag.objects.get_or_create(category=category, name=name)
    return tag


class Command(BaseCommand):
    help = (
        'Створює 20 анкет Dating і 20 анкет BFF з зустрічами. '
        'Усі лайкають --like-target (за замовчуванням tyrion@gmail.com). '
        'Видаляє лише користувачів @crushme.test.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--like-target',
            dest='like_target',
            default=DEFAULT_LIKE_TARGET,
            help='Email, якому всі демо-анкети ставлять лайк.',
        )
        parser.add_argument(
            '--dating-count',
            type=int,
            default=DEFAULT_DATING_COUNT,
            help=f'Скільки анкет романтики (за замовчуванням {DEFAULT_DATING_COUNT}).',
        )
        parser.add_argument(
            '--bff-count',
            type=int,
            default=DEFAULT_BFF_COUNT,
            help=f'Скільки анкет дружби зі зустрічами (за замовчуванням {DEFAULT_BFF_COUNT}).',
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
        dating_count = max(0, options['dating_count'])
        bff_count = max(0, options['bff_count'])
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
        personas = []

        if not meetings_only:
            compat = self._compat_from_target(target_user)
            personas = (
                [self._persona_at(index, SearchMode.DATING) for index in range(dating_count)]
                + [self._persona_at(index, SearchMode.BFF) for index in range(bff_count)]
            )
            with transaction.atomic():
                for persona in personas:
                    user = self._upsert_user(persona)
                    profile = self._upsert_profile(user, persona, compat)
                    self._upsert_modes(profile, persona, compat)
                    self._upsert_tags(profile, persona, compat)
                    self._set_photos(profile, persona)
                    created += 1
                    liked += self._like_target(user, target_user, persona['track'])

            self.stdout.write(self.style.SUCCESS(
                f'Створено/оновлено {created} анкет '
                f'({dating_count} романтика, {bff_count} дружба). Пароль: {DEMO_PASSWORD}',
            ))
            self.stdout.write(
                f'Усі поставили лайк {like_target_email} ({liked} записів). '
                'Лайкни у відповідь — буде метч.',
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
            for persona in personas:
                label = 'BFF' if persona['track'] == SearchMode.BFF else 'Dating'
                self.stdout.write(f'  [{label}] {persona["display_name"]}  {persona["email"]}')

        meetings_created = self._ensure_bff_meetings()
        if meetings_created:
            self.stdout.write(self.style.SUCCESS(
                f'Додано {meetings_created} зустрічей — у BFF з’явиться кнопка «Зустріч».',
            ))
        else:
            self.stdout.write('Нових зустрічей не додано: вони вже є або немає BFF-демо.')

    def _persona_at(self, index, track):
        person = NAME_POOL[index % len(NAME_POOL)]
        bio = BIO_TEMPLATES[index % len(BIO_TEMPLATES)]
        cycle = index // len(NAME_POOL)
        slug = person['slug'] if cycle == 0 else f'{person["slug"]}{cycle + 1}'
        prefix = 'bff' if track == SearchMode.BFF else 'dating'
        display = person['display_name'] if cycle == 0 else f'{person["display_name"]} {cycle + 1}'
        return {
            'track': track,
            'slug': person['photo'],
            'username': f'{prefix}_{slug}'[:30],
            'email': f'{prefix}-{slug}{DEMO_EMAIL_SUFFIX}',
            'display_name': display,
            'gender': person['gender'],
            'age': person['age'],
            'job': person['job'],
            'orientation': Orientation.STRAIGHT,
            'extra_interests': bio['extra_interests'],
            'dating_bio': bio['dating_bio'],
            'bff_bio': bio['bff_bio'],
        }

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
                'moderation_status': ModerationStatus.APPROVED,
                'active_mode': persona['track'],
            },
        )
        return profile

    def _upsert_modes(self, profile, persona, compat):
        if persona['track'] == SearchMode.DATING:
            ProfileMode.objects.filter(profile=profile, mode=SearchMode.BFF).delete()
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
            return
        ProfileMode.objects.filter(profile=profile, mode=SearchMode.DATING).delete()
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
        if persona['track'] == SearchMode.DATING:
            dating_names = _unique(
                list(compat['dating_interests']) + list(persona.get('extra_interests') or []),
            )
            for name in dating_names:
                tag = _ensure_tag(TagCategory.INTEREST, name)
                if tag is None:
                    continue
                ProfileTag.objects.create(
                    profile=profile, tag=tag, mode=SearchMode.DATING,
                )
            return
        seen_hobbies = set()
        for name, level in compat['bff_hobbies']:
            if name in seen_hobbies:
                continue
            seen_hobbies.add(name)
            tag = _ensure_tag(TagCategory.HOBBY, name)
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
            tag = _ensure_tag(TagCategory.LANGUAGE, name)
            if tag is None:
                continue
            ProfileTag.objects.create(
                profile=profile, tag=tag, mode=SearchMode.BFF, level=level or 'a1',
            )

    def _set_photos(self, profile, persona):
        photo_key = persona.get('slug') or 'sofia'
        filenames = PHOTO_SETS.get(photo_key) or PHOTO_SETS['sofia']
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

    def _like_target(self, user, target_user, mode):
        if user.id == target_user.id:
            return 0
        Like.objects.update_or_create(
            from_user=user,
            to_user=target_user,
            mode=mode,
            defaults={'is_positive': True},
        )
        return 1

    def _ensure_bff_meetings(self):
        candidates = list(
            User.objects
            .filter(email__iendswith=DEMO_EMAIL_SUFFIX)
            .filter(email__istartswith='bff-')
            .filter(profile__modes__mode=SearchMode.BFF)
            .select_related('profile')
            .prefetch_related('profile__photos')
            .distinct()
            .order_by('id')
        )
        created = 0
        for index, user in enumerate(candidates):
            if get_active_meeting(user) is not None:
                continue
            template = MEETING_TEMPLATES[index % len(MEETING_TEMPLATES)]
            city = (getattr(user.profile, 'city', None) or TARGET_CITY).strip() or TARGET_CITY
            starts_at = self._future_meeting_start(
                days_ahead=2 + (index % 12),
                hour=template['hour'],
            )
            title = template['title']
            if index >= len(MEETING_TEMPLATES):
                title = f'{template["title"]} ({index + 1})'
            try:
                meeting = create_meeting(
                    user,
                    title=title,
                    location=f'{city}, {template["place"]}',
                    description=template['description'],
                    starts_at=starts_at,
                )
                self._attach_meeting_cover(meeting, user)
                created += 1
            except MeetingError as exc:
                self.stdout.write(self.style.WARNING(
                    f'Не вдалося створити зустріч для {user.email}: {exc}',
                ))
        for user in candidates:
            meeting = get_active_meeting(user)
            if meeting is not None:
                self._attach_meeting_cover(meeting, user)
        return created

    def _attach_meeting_cover(self, meeting, user):
        if meeting.photo_url:
            return
        profile = getattr(user, 'profile', None)
        if profile is None:
            return
        photo = (
            profile.photos.filter(is_primary=True).first()
            or profile.photos.first()
        )
        if photo is None or not photo.url:
            return
        meeting.photo_url = photo.url
        meeting.save(update_fields=['photo_url', 'updated_at'])

    def _future_meeting_start(self, days_ahead, hour):
        now = timezone.localtime(timezone.now())
        starts = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=0, second=0, microsecond=0,
        )
        if starts <= now:
            starts = starts + timedelta(days=1)
        return starts
