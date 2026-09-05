"""Сторінки профілю: анкета, перегляд і редагування."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import redirect, render

from profiles.forms import ProfileSetupForm
from profiles.models import (
    AgePreference,
    AlcoholHabit,
    BffLookingFor,
    ChildrenStatus,
    Gender,
    HobbyLevel,
    LanguageLevel,
    LookingFor,
    MeetingFormat,
    Orientation,
    PartnerHabitAttitude,
    PetsStatus,
    RelationshipGoal,
    SearchMode,
    SmokingHabit,
    SportFrequency,
    Tag,
    TagCategory,
    ZodiacSign,
)
from profiles.services import (
    clear_draft_photos,
    form_initial_from_profile,
    get_draft_photos,
    photo_slots_for_form,
    save_profile,
    sync_draft_photos,
)


# Порядок показу тегів у формі — так само, як у макеті Figma (не за алфавітом).
# Теги, яких немає в списку (додані пізніше), показуються після нього за
# алфавітом, щоб жоден новий тег не загубився.
INTEREST_TAG_ORDER = [
    'Ігри', 'Подорожі', 'Кіно', 'Музика',
    'Прогулянки', 'Спорт', 'Кава', 'Тварини',
    'Їжа', 'Кулінарія', 'Мистецтво', 'Фотографія',
    'Фітнес', 'Танці', 'Читання', 'Психологія',
    'Настільні ігри', 'Технології', 'Шопінг', 'Мода',
    'Наука', 'Волонтерство', 'Татуювання', "Кар'єра та бізнес",
    'Йога', 'Велосипед', 'Авто / Мото', 'Стендап',
    'Аніме', 'Веганство', 'Кемпінг',
]

# «Хобі та рівень» на кроці «Друзі» — макет показує анкету у 2 колонки, тож
# порядок тут «рядковий» (перший і другий елемент — один рядок, і т.д.).
HOBBY_TAG_ORDER = [
    'Велосипед', 'Біг',
    'Гітара', 'Йога',
    'Кулінарія', 'Малювання',
    'Настільні ігри', 'Плавання',
    'Походи', 'Шахи',
    'Фотографія', 'Відео',
    'Танці', 'IT',
]

# «Мови» на кроці «Друзі» — так само 2 колонки, порядок рядковий.
LANGUAGE_TAG_ORDER = [
    'Англійська', 'Іспанська',
    'Німецька', 'Польська',
    'Українська', 'Французька',
    'Шведська', 'Італійська',
    'Китайська', 'Японська',
    'Корейська', 'Чеська',
]


def _ordered_tags(category, order):
    """Теги однієї категорії у фіксованому порядку за макетом (не за алфавітом).

    Лишається справжнім QuerySet (а не списком), бо ModelMultipleChoiceField
    у формі викликає .all() на переданому queryset.
    """
    order_cases = [
        When(name=name, then=Value(index))
        for index, name in enumerate(order)
    ]
    return Tag.objects.filter(category=category).annotate(
        _display_order=Case(
            *order_cases,
            default=Value(len(order)),
            output_field=IntegerField(),
        ),
    ).order_by('_display_order', 'name')


def _tag_querysets():
    """Довідники тегів для чекбоксів форми."""
    return {
        'interest_qs': _ordered_tags(TagCategory.INTEREST, INTEREST_TAG_ORDER),
        'hobby_qs': _ordered_tags(TagCategory.HOBBY, HOBBY_TAG_ORDER),
        'language_qs': _ordered_tags(TagCategory.LANGUAGE, LANGUAGE_TAG_ORDER),
    }


def _selected_bff_goals(request, profile):
    """Обрані цілі «Що шукаєш» у пошуку друзів — з POST або зі збереженого профілю."""
    if request.method == 'POST':
        return set(request.POST.getlist('bff_looking_for'))
    if profile is None:
        return set()
    bff = profile.get_mode(SearchMode.BFF)
    if not bff or not bff.looking_for:
        return set()
    return set(bff.looking_for.split(','))


def _bff_looking_for_options(request, profile):
    """Список цілей «Що шукаєш» для чекбоксів-чіпів (значення, підпис, обрано)."""
    selected = _selected_bff_goals(request, profile)
    return [
        {'value': value, 'label': label, 'selected': value in selected}
        for value, label in BffLookingFor.choices
    ]


def _completed_profile(user):
    """Збережений профіль після анкети, або None."""
    if not user.is_profile_complete:
        return None
    try:
        return user.profile
    except ObjectDoesNotExist:
        return None


def _selected_ids(request, field_name, profile, mode, category):
    """ID обраних тегів: з POST або зі збереженого профілю."""
    if request.method == 'POST':
        return request.POST.getlist(field_name)
    if profile is None:
        return []
    return [str(item.tag_id) for item in profile.tags_for(mode, category)]


def _level_map(request, prefix, profile, category):
    """Рівні хобі/мов: hobby_level_12 → {'12': 'novice'}."""
    if request.method == 'POST':
        return {
            key[len(prefix):]: value
            for key, value in request.POST.items()
            if key.startswith(prefix)
        }
    if profile is None:
        return {}
    return {
        str(item.tag_id): item.level
        for item in profile.tags_for(SearchMode.BFF, category)
    }


def _tag_options(queryset, selected_ids, levels=None):
    """Список тегів для шаблону: сам тег, чи обраний, який рівень."""
    selected = {str(pk) for pk in selected_ids}
    levels = levels or {}
    return [
        {
            'tag': tag,
            'selected': str(tag.pk) in selected,
            'level': levels.get(str(tag.pk), ''),
        }
        for tag in queryset
    ]


def _mode_tag_options(
    request,
    profile,
    field_name,
    queryset,
    mode,
    category,
    level_prefix=None,
):
    """Теги одного контуру (знайомства або друзі) для чекбоксів форми."""
    levels = None
    if level_prefix:
        levels = _level_map(request, level_prefix, profile, category)
    return _tag_options(
        queryset,
        _selected_ids(request, field_name, profile, mode, category),
        levels,
    )


def _form_page_context(request, form, tag_qs, profile=None):
    """Контекст спільної форми анкети / редагування."""
    error_step = form.first_error_step() if form.is_bound and form.errors else 0
    return {
        'form': form,
        'error_step': error_step,
        'photo_slots': photo_slots_for_form(request, profile),
        'dating_interest_options': _mode_tag_options(
            request,
            profile,
            'dating_interests',
            tag_qs['interest_qs'],
            SearchMode.DATING,
            TagCategory.INTEREST,
        ),
        'bff_interest_options': _mode_tag_options(
            request,
            profile,
            'bff_interests',
            tag_qs['interest_qs'],
            SearchMode.BFF,
            TagCategory.INTEREST,
        ),
        'hobby_options': _mode_tag_options(
            request,
            profile,
            'bff_hobbies',
            tag_qs['hobby_qs'],
            SearchMode.BFF,
            TagCategory.HOBBY,
            'hobby_level_',
        ),
        'language_options': _mode_tag_options(
            request,
            profile,
            'bff_languages',
            tag_qs['language_qs'],
            SearchMode.BFF,
            TagCategory.LANGUAGE,
            'language_level_',
        ),
        'genders': Gender.choices,
        'orientations': Orientation.choices,
        'looking_for_choices': LookingFor.choices,
        'bff_looking_for_options': _bff_looking_for_options(request, profile),
        'smoking_choices': SmokingHabit.choices,
        'children_choices': ChildrenStatus.choices,
        'alcohol_choices': AlcoholHabit.choices,
        'sport_choices': SportFrequency.choices,
        'pets_choices': PetsStatus.choices,
        'zodiac_choices': ZodiacSign.choices,
        'age_preference_choices': AgePreference.choices,
        'relationship_goal_choices': RelationshipGoal.choices,
        'partner_attitude_choices': PartnerHabitAttitude.choices,
        'meeting_format_choices': MeetingFormat.choices,
        'hobby_levels': HobbyLevel.choices,
        'language_levels': LanguageLevel.choices,
    }


def _try_save_profile(request, form, draft_photos=None):
    """Зберігає профіль; False, якщо завантаження фото впало."""
    try:
        with transaction.atomic():
            save_profile(
                request.user,
                form.cleaned_data,
                draft_photos=draft_photos,
            )
    except ValueError as exc:
        messages.error(request, str(exc))
        return False
    return True


def _profile_form_page(request, template, *, is_edit=False, profile=None, initial=None):
    """Спільна обробка GET/POST для анкети та редагування."""
    tag_qs = _tag_querysets()
    draft_photos = None
    if request.method == 'POST':
        if not is_edit:
            try:
                draft_photos = sync_draft_photos(request, request.user)
            except ValueError as exc:
                messages.error(request, str(exc))
                draft_photos = get_draft_photos(request.session)
        form = ProfileSetupForm(request.POST, request.FILES, **tag_qs)
        if form.is_valid() and _try_save_profile(request, form, draft_photos):
            if not is_edit:
                clear_draft_photos(request.session)
            return redirect('profile_me')
    else:
        form = ProfileSetupForm(initial=initial, **tag_qs)
    return render(
        request,
        template,
        _form_page_context(request, form, tag_qs, profile),
    )


@login_required
def setup_view(request):
    """Перше заповнення анкети після реєстрації."""
    if request.user.is_profile_complete:
        return redirect('profile_me')
    return _profile_form_page(
        request,
        'profiles/setup.html',
        initial={'display_name': request.user.username or ''},
    )


@login_required
def me_view(request):
    """Перегляд власного профілю з усіма заповненими полями."""
    profile = _completed_profile(request.user)
    if profile is None:
        return redirect('profile_setup')

    return render(
        request,
        'profiles/detail.html',
        {
            'profile': profile,
            'dating': profile.get_mode(SearchMode.DATING),
            'bff': profile.get_mode(SearchMode.BFF),
            'dating_interests': profile.tags_for(
                SearchMode.DATING,
                TagCategory.INTEREST,
            ),
            'bff_interests': profile.tags_for(SearchMode.BFF, TagCategory.INTEREST),
            'bff_hobbies': profile.tags_for(SearchMode.BFF, TagCategory.HOBBY),
            'bff_languages': profile.tags_for(SearchMode.BFF, TagCategory.LANGUAGE),
        },
    )


@login_required
def edit_view(request):
    """Редагування вже створеного профілю (та сама форма, що й анкета)."""
    profile = _completed_profile(request.user)
    if profile is None:
        return redirect('profile_setup')
    return _profile_form_page(
        request,
        'profiles/edit.html',
        is_edit=True,
        profile=profile,
        initial=form_initial_from_profile(profile),
    )
