"""Наповнює базу тестовими анкетами, щоб перевірити фільтрацію Dating/BFF.

Кожен запуск ДОДАЄ нову партію анкет (не торкаючись раніше створених) із
заздалегідь продуманим розподілом:
- частина підходить під Dating-фільтри цільового користувача (те саме місто,
  вік у діапазоні, 2+ спільні інтереси) — вони з'являться у стрічці свайпів;
- частина навмисно НЕ підходить (інше місто / замало спільних інтересів) —
  щоб перевірити, що фільтр і справді їх приховує;
- аналогічно для BFF: частина збігається темою пошуку + хобі/мовою й рівнем,
  частина — з іншою темою пошуку (щоб перевірити відсіювання);
- кілька анкет одразу лайкають цільового користувача, щоб після взаємного
  лайку в застосунку відразу з'явився метч.

Аватарки — нейтральні абстрактні іконки (геометричні фігури, DiceBear),
без зображення людей: питання зовнішності/раси на тестових даних не виникає.

Приклади запуску:
    python manage.py seed_demo_profiles --like-target luzluz@gmail.com --count 20
    python manage.py seed_demo_profiles --count 30          # додати ще 30
    python manage.py seed_demo_profiles --reset --count 20  # почати з чистого листа
"""

import re
from datetime import date
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from matching.models import Like
from profiles.models import (
    Gender,
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
DEMO_EMAIL_RE = re.compile(r'^demo(\d+)@crushme\.test$')

CITIES_OTHER = ['Львів', 'Одеса', 'Харків', 'Дніпро', 'Вінниця']
TARGET_CITY = 'Київ'

FEMALE_NAMES = ['Софія', 'Марія', 'Анна', 'Оксана', 'Юлія', 'Дарина', 'Катерина', 'Вікторія', 'Ольга', 'Ірина']
MALE_NAMES = ['Максим', 'Артем', 'Богдан', 'Дмитро', 'Іван', 'Олег', 'Тарас', 'Роман', 'Назар', 'Владислав']

DATING_BIOS = [
    'Люблю активні вихідні та нові знайомства. Кава — must have ☕',
    'У пошуках когось, з ким можна обговорити улюблений серіал і піти в похід.',
    'Життя — це пригода. Приєднуйся!',
    'Волонтерю, читаю фантастику, обожнюю тварин.',
    'Спорт зранку, наука ввечері — баланс у всьому.',
    'Шукаю щирого спілкування без переписок у нікуди.',
]
BFF_BIOS = [
    'Шукаю компанію для мовної практики та спільних хобі.',
    'Люблю малювати й вивчати мови — буду рада знайти однодумців.',
    'Відкрита до нових друзів по інтересах, без драми.',
    'Мандрую, коли є можливість, і завжди рада компанії.',
]

# Нейтральні абстрактні іконки (геометричні фігури) замість фото людей —
# аватарки не зображають жодної людини, тож зовнішність/раса тут не задіяні.
AVATAR_URL = 'https://api.dicebear.com/9.x/shapes/svg?seed={seed}'

DATING_MATCH_INTERESTS = ['Ігри', 'Волонтерство', 'Наука', 'Спорт', 'Тварини', 'Читання']
EXTRA_INTERESTS = ['Музика', 'Кіно', 'Подорожі', 'Фітнес', 'Мистецтво', 'Фотографія', 'Танці']
FEW_SHARED_INTERESTS = ['Музика', 'Кіно', 'Мистецтво', 'Фотографія', 'Танці']
BFF_HOBBY_OPTIONS = ['Йога', 'Біг', 'Гітара', 'Шахи', 'Плавання', 'Велосипед']
BFF_LANGUAGE_OPTIONS = ['Польська', 'Французька', 'Іспанська', 'Шведська']
BFF_LEVELS = ['novice', 'intermediate', 'pro']
LANGUAGE_LEVELS = ['a1', 'a2', 'b1']
OTHER_TOPICS = ['hobby', 'travel', 'coworking', 'hangout']

# Розподіл однієї партії (сума часток = 1.0), масштабується під --count.
GROUP_SHARES = {
    'dating_match': 0.30,        # місто + вік + 2+ інтереси Luz — з'явиться в Dating
    'dating_wrong_city': 0.20,   # інше місто — має бути прибрано фільтром
    'dating_few_shared': 0.13,   # Київ і вік підходять, та інтересів < 2
    'bff_match': 0.23,           # та сама тема + хобі/мова з рівнем Luz — з'явиться в BFF
    'bff_wrong_topic': 0.14,     # інша тема пошуку — має бути прибрано фільтром
}


def _avatar_pair(seed_base):
    """Дві різні URL-адреси абстрактних іконок для галереї тестового профілю."""
    return [
        AVATAR_URL.format(seed=f'{seed_base}-a'),
        AVATAR_URL.format(seed=f'{seed_base}-b'),
    ]


def _birth_date_for_age(age):
    """Дата народження (15 березня), що дає точний вік на сьогодні."""
    today = date.today()
    return date(today.year - age, 3, 15)


def _tag(category, name):
    return Tag.objects.get(category=category, name=name)


class Command(BaseCommand):
    help = "Додає нову партію тестових анкет для перевірки фільтрації Dating/BFF."

    def add_arguments(self, parser):
        parser.add_argument(
            '--like-target',
            dest='like_target',
            default='luzluz@gmail.com',
            help='Email користувача, якому частина нових анкет одразу поставить лайк.',
        )
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Скільки нових анкет додати цим запуском (за замовчуванням 20).',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Перед створенням видалити ВСІ попередньо створені демо-анкети.',
        )

    def handle(self, *args, **options):
        like_target_email = options['like_target']
        count = options['count']
        try:
            target_user = User.objects.get(email=like_target_email)
        except User.DoesNotExist:
            raise CommandError(
                f'Користувача з email "{like_target_email}" не знайдено. '
                'Вкажи інший --like-target або спочатку заповни його анкету.',
            )

        if options['reset']:
            removed, _ = User.objects.filter(email__endswith=DEMO_EMAIL_SUFFIX).delete()
            self.stdout.write(self.style.WARNING(f'Видалено попередніх демо-користувачів: {removed}'))

        start_index = self._next_start_index()
        specs = self._build_specs(count, seed=start_index)

        created = 0
        liked_dating = 0
        liked_bff = 0

        with transaction.atomic():
            for offset, spec in enumerate(specs):
                index = start_index + offset
                user = self._create_user(spec, index)
                profile = self._create_profile(user, spec, index)
                self._create_modes(profile, spec)
                self._create_tags(profile, spec)
                self._set_avatar_photos(profile, seed=f'demo{index:02d}')
                created += 1

                if spec.get('like_target_mode'):
                    Like.objects.get_or_create(
                        from_user=user,
                        to_user=target_user,
                        mode=spec['like_target_mode'],
                        defaults={'is_positive': True},
                    )
                    if spec['like_target_mode'] == SearchMode.DATING:
                        liked_dating += 1
                    else:
                        liked_bff += 1

            refreshed = self._refresh_avatars_for_existing_demo_users(start_index)

        self.stdout.write(self.style.SUCCESS(
            f'Створено {created} нових тестових анкет (демо-пошта на {DEMO_EMAIL_SUFFIX}, '
            f'пароль {DEMO_PASSWORD}).',
        ))
        if refreshed:
            self.stdout.write(f'Оновлено аватарки на нейтральні іконки ще у {refreshed} раніше створених анкет.')
        self.stdout.write(
            f'Уже лайкнули {like_target_email}: {liked_dating} у Dating, {liked_bff} у BFF '
            '— увійди і побачиш їх у стрічці, лайкни у відповідь, щоб отримати метч.',
        )

    # ------------------------------------------------------------------
    # Індексація демо-користувачів (щоб додавання не перетирало старих)
    # ------------------------------------------------------------------

    def _next_start_index(self):
        """Перший вільний номер demoNN — щоб нова партія не перетерла попередню."""
        existing = [
            int(match.group(1))
            for match in (
                DEMO_EMAIL_RE.match(email)
                for email in User.objects.filter(
                    email__endswith=DEMO_EMAIL_SUFFIX,
                ).values_list('email', flat=True)
            )
            if match
        ]
        return max(existing, default=0) + 1

    def _refresh_avatars_for_existing_demo_users(self, before_index):
        """Перезаписує фото на нейтральні іконки в усіх раніше створених демо-анкетах."""
        refreshed = 0
        for user in User.objects.filter(email__endswith=DEMO_EMAIL_SUFFIX).select_related('profile'):
            match = DEMO_EMAIL_RE.match(user.email)
            if not match or int(match.group(1)) >= before_index:
                continue  # це анкета з поточної (нової) партії — вже має свіжу іконку
            profile = getattr(user, 'profile', None)
            if profile is None:
                continue
            self._set_avatar_photos(profile, seed=user.username or user.email)
            refreshed += 1
        return refreshed

    # ------------------------------------------------------------------
    # Побудова специфікацій анкет
    # ------------------------------------------------------------------

    def _build_specs(self, count, seed):
        """Список анкет для нової партії, розподілений за GROUP_SHARES."""
        rng = Random(seed)
        group_counts = self._split_counts(count)

        specs = []
        for group, group_size in group_counts.items():
            for _ in range(group_size):
                specs.append(self._spec_for_group(group, rng))

        rng.shuffle(specs)
        for spec in specs:
            spec['gender'] = rng.choice([Gender.FEMALE, Gender.MALE])
            spec['orientation'] = rng.choice([
                Orientation.STRAIGHT, Orientation.BISEXUAL, Orientation.GAY, Orientation.OTHER,
            ])

        # Позначаємо лайки цілі: половина dating_match і bff_match анкет — щоб
        # після взаємного лайку в застосунку одразу з'явився метч.
        dating_match_specs = [s for s in specs if s['group'] == 'dating_match']
        bff_match_specs = [s for s in specs if s['group'] == 'bff_match']
        for spec in dating_match_specs[:max(1, len(dating_match_specs) // 2)]:
            spec['like_target_mode'] = SearchMode.DATING
        for spec in bff_match_specs[:max(1, len(bff_match_specs) // 2)]:
            spec['like_target_mode'] = SearchMode.BFF

        return specs

    def _split_counts(self, count):
        """Ділить count на групи за GROUP_SHARES, зберігаючи точну суму."""
        raw = {group: share * count for group, share in GROUP_SHARES.items()}
        counts = {group: int(value) for group, value in raw.items()}
        remainder = count - sum(counts.values())
        # Залишок (через округлення) віддаємо групам із найбільшою дробовою частиною.
        fractions = sorted(raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True)
        for group, _ in fractions:
            if remainder <= 0:
                break
            counts[group] += 1
            remainder -= 1
        return counts

    def _spec_for_group(self, group, rng):
        """Дані анкети для конкретної групи (див. GROUP_SHARES вище)."""
        if group == 'dating_match':
            return {
                'group': group,
                'like_target_mode': None,
                'city': TARGET_CITY,
                'age': rng.randint(19, 29),
                'dating_interests': rng.sample(DATING_MATCH_INTERESTS, k=2) + rng.sample(EXTRA_INTERESTS, k=1),
                'bff_looking_for': rng.choice(OTHER_TOPICS),
                'bff_hobbies': [(rng.choice(BFF_HOBBY_OPTIONS), rng.choice(BFF_LEVELS))],
                'bff_languages': [(rng.choice(BFF_LANGUAGE_OPTIONS), rng.choice(LANGUAGE_LEVELS))],
            }
        if group == 'dating_wrong_city':
            return {
                'group': group,
                'like_target_mode': None,
                'city': rng.choice(CITIES_OTHER),
                'age': rng.randint(19, 29),
                'dating_interests': rng.sample(DATING_MATCH_INTERESTS, k=2),
                'bff_looking_for': rng.choice(OTHER_TOPICS),
                'bff_hobbies': [(rng.choice(BFF_HOBBY_OPTIONS), 'novice')],
                'bff_languages': [(rng.choice(BFF_LANGUAGE_OPTIONS), 'a1')],
            }
        if group == 'dating_few_shared':
            return {
                'group': group,
                'like_target_mode': None,
                'city': TARGET_CITY,
                'age': rng.randint(19, 29),
                'dating_interests': rng.sample(FEW_SHARED_INTERESTS, k=1),
                'bff_looking_for': rng.choice(OTHER_TOPICS),
                'bff_hobbies': [(rng.choice(BFF_HOBBY_OPTIONS), 'novice')],
                'bff_languages': [(rng.choice(BFF_LANGUAGE_OPTIONS), 'a1')],
            }
        if group == 'bff_match':
            return {
                'group': group,
                'like_target_mode': None,
                'city': rng.choice([TARGET_CITY] + CITIES_OTHER),
                'age': rng.randint(19, 35),
                'dating_interests': rng.sample(EXTRA_INTERESTS, k=1),
                'bff_looking_for': 'language',
                'bff_hobbies': [('Малювання', 'novice'), (rng.choice(BFF_HOBBY_OPTIONS), 'intermediate')],
                'bff_languages': [('Англійська', 'b2'), (rng.choice(BFF_LANGUAGE_OPTIONS), 'a2')],
            }
        # bff_wrong_topic
        return {
            'group': group,
            'like_target_mode': None,
            'city': rng.choice([TARGET_CITY] + CITIES_OTHER),
            'age': rng.randint(19, 35),
            'dating_interests': rng.sample(EXTRA_INTERESTS, k=1),
            'bff_looking_for': rng.choice(OTHER_TOPICS),
            'bff_hobbies': [('Малювання', 'novice')],
            'bff_languages': [('Англійська', 'b2')],
        }

    # ------------------------------------------------------------------
    # Створення записів у БД
    # ------------------------------------------------------------------

    def _create_user(self, spec, index):
        email = f'demo{index:02d}{DEMO_EMAIL_SUFFIX}'
        username = f'demo{index:02d}'
        user, _ = User.objects.update_or_create(
            email=email,
            defaults={'username': username, 'is_profile_complete': True},
        )
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user

    def _create_profile(self, user, spec, index):
        names = FEMALE_NAMES if spec['gender'] == Gender.FEMALE else MALE_NAMES
        display_name = names[index % len(names)]
        profile, _ = Profile.objects.update_or_create(
            user=user,
            defaults={
                'display_name': display_name,
                'birth_date': _birth_date_for_age(spec['age']),
                'gender': spec['gender'],
                'orientation': spec['orientation'],
                'city': spec['city'],
                'is_discoverable': True,
            },
        )
        return profile

    def _create_modes(self, profile, spec):
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.DATING,
            defaults={
                'bio': DATING_BIOS[hash(profile.display_name) % len(DATING_BIOS)],
                'looking_for': 'everyone',
                'min_age': 18,
                'max_age': 40,
            },
        )
        ProfileMode.objects.update_or_create(
            profile=profile,
            mode=SearchMode.BFF,
            defaults={
                'bio': BFF_BIOS[hash(profile.display_name) % len(BFF_BIOS)],
                'looking_for': spec['bff_looking_for'],
                'min_age': 18,
                'max_age': 99,
            },
        )

    def _create_tags(self, profile, spec):
        profile.profile_tags.all().delete()
        for name in spec['dating_interests']:
            ProfileTag.objects.create(
                profile=profile,
                tag=_tag(TagCategory.INTEREST, name),
                mode=SearchMode.DATING,
            )
        for name, level in spec['bff_hobbies']:
            ProfileTag.objects.create(
                profile=profile,
                tag=_tag(TagCategory.HOBBY, name),
                mode=SearchMode.BFF,
                level=level,
            )
        for name, level in spec['bff_languages']:
            ProfileTag.objects.create(
                profile=profile,
                tag=_tag(TagCategory.LANGUAGE, name),
                mode=SearchMode.BFF,
                level=level,
            )

    def _set_avatar_photos(self, profile, seed):
        """Дві нейтральні абстрактні іконки замість фото — без зображення людей."""
        profile.photos.all().delete()
        for order, url in enumerate(_avatar_pair(seed)):
            Photo.objects.create(
                profile=profile,
                cloudinary_public_id=f'demo-avatar:{seed}:{order}',
                url=url,
                order=order,
                is_primary=order == 0,
                status=PhotoStatus.APPROVED,
            )
