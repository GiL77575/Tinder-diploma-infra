"""Логіка свайпів, матчів і відбору анкет (окремо для dating і bff)."""

from django.db.models import Q

from matching.models import Block, Like, Match
from profiles.models import ModerationStatus, Profile, SearchMode, TagCategory

# Скільки спільних інтересів потрібно для показу анкети в режимі знайомств.
MIN_SHARED_DATING_INTERESTS = 2


def _avatar_url(profile):
    """Посилання на головне фото профілю або None, якщо фото не завантажені."""
    photo = profile.photos.first()
    return photo.url if photo else None


def _canonical_pair(user_a, user_b):
    """user_a.id завжди менший — так, як того вимагає обмеження моделі Match."""
    return (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)


def _tag_level_maps(profile):
    """
    Один прохід по всіх тегах профілю: {(режим, категорія): {tag_id: level}}.
    Дозволяє далі порівнювати анкети без повторних запитів до бази.
    """
    maps = {}
    for item in profile.profile_tags.all():
        key = (item.mode, item.tag.category)
        maps.setdefault(key, {})[item.tag_id] = item.level
    return maps


def _shared_tag_ids(tags_a, tags_b, require_same_level=False):
    """
    ID тегів, спільних для двох словників {tag_id: level}.
    Якщо require_same_level=True — тег рахується збігом лише тоді, коли
    рівень (наприклад, B1 або «Профі») однаковий в обох профілях.
    """
    shared = []
    for tag_id, level_a in tags_a.items():
        if tag_id not in tags_b:
            continue
        if require_same_level and level_a != tags_b[tag_id]:
            continue
        shared.append(tag_id)
    return shared


def _dating_match(viewer_profile, viewer_tags, candidate_profile, candidate_tags):
    """
    Критерії показу анкети в режимі знайомств:
    - те саме місто, що й у переглядача;
    - вік кандидата в межах діапазону, вказаного переглядачем при реєстрації;
    - 2 і більше спільних інтереси.
    Повертає список id спільних інтересів або None, якщо анкета не підходить.
    """
    viewer_mode = viewer_profile.get_mode(SearchMode.DATING)
    if viewer_mode is None:
        return None

    if not viewer_profile.city or not candidate_profile.city:
        return None
    if viewer_profile.city.strip().lower() != candidate_profile.city.strip().lower():
        return None

    candidate_age = candidate_profile.age
    if candidate_age is None:
        return None
    if not (viewer_mode.min_age <= candidate_age <= viewer_mode.max_age):
        return None

    viewer_interests = viewer_tags.get((SearchMode.DATING, TagCategory.INTEREST), {})
    candidate_interests = candidate_tags.get((SearchMode.DATING, TagCategory.INTEREST), {})
    shared = _shared_tag_ids(viewer_interests, candidate_interests)
    if len(shared) < MIN_SHARED_DATING_INTERESTS:
        return None
    return shared


def _bff_match(viewer_profile, viewer_tags, candidate_profile, candidate_tags):
    """
    Критерії показу анкети в режимі пошуку друзів:
    - хоча б одна спільна ціль спілкування («Що шукаєш», напр. «Прогулянки»);
      кожен профіль може обрати декілька цілей — досить перетину множин;
    - хоча б одне спільне хобі з тим самим рівнем;
    - хоча б одна спільна мова з тим самим рівнем.
    Місто не враховується — BFF-анкети можуть бути з різних міст.
    Повертає {'hobbies': [...], 'languages': [...]} спільних id або None.
    """
    viewer_mode = viewer_profile.get_mode(SearchMode.BFF)
    candidate_mode = candidate_profile.get_mode(SearchMode.BFF)
    if viewer_mode is None or candidate_mode is None:
        return None

    viewer_goals = set(filter(None, (viewer_mode.looking_for or '').split(',')))
    candidate_goals = set(filter(None, (candidate_mode.looking_for or '').split(',')))
    if not viewer_goals or not (viewer_goals & candidate_goals):
        return None

    viewer_hobbies = viewer_tags.get((SearchMode.BFF, TagCategory.HOBBY), {})
    candidate_hobbies = candidate_tags.get((SearchMode.BFF, TagCategory.HOBBY), {})
    shared_hobbies = _shared_tag_ids(viewer_hobbies, candidate_hobbies, require_same_level=True)
    if not shared_hobbies:
        return None

    viewer_languages = viewer_tags.get((SearchMode.BFF, TagCategory.LANGUAGE), {})
    candidate_languages = candidate_tags.get((SearchMode.BFF, TagCategory.LANGUAGE), {})
    shared_languages = _shared_tag_ids(viewer_languages, candidate_languages, require_same_level=True)
    if not shared_languages:
        return None

    return {'hobbies': shared_hobbies, 'languages': shared_languages}


def _match_for_mode(viewer_profile, viewer_tags, candidate_profile, mode):
    """
    Диспетчер правил показу за режимом. Повертає словник спільних тегів
    кандидата, якщо анкета підходить переглядачу, інакше None.
    """
    candidate_tags = _tag_level_maps(candidate_profile)
    if mode == SearchMode.DATING:
        shared = _dating_match(viewer_profile, viewer_tags, candidate_profile, candidate_tags)
        return None if shared is None else {'interests': shared}
    if mode == SearchMode.BFF:
        return _bff_match(viewer_profile, viewer_tags, candidate_profile, candidate_tags)
    return None


def serialize_candidate(profile, mode, shared_tags=None):
    """
    Картка кандидата для свайпу: фото, ім'я, вік, біо цього режиму та
    список тегів із позначкою is_shared — щоб фронтенд підсвітив кольором
    ті хобі/інтереси/мови, що збігаються з профілем переглядача.
    """
    shared_tags = shared_tags or {}
    profile_mode = profile.get_mode(mode)
    photos = list(profile.photos.all())

    if mode == SearchMode.DATING:
        shared_ids = set(shared_tags.get('interests') or [])
        tags = [
            {'id': item.tag_id, 'name': item.tag.name, 'is_shared': item.tag_id in shared_ids}
            for item in profile.tags_for(SearchMode.DATING, TagCategory.INTEREST)
        ]
    else:
        shared_hobby_ids = set(shared_tags.get('hobbies') or [])
        shared_language_ids = set(shared_tags.get('languages') or [])
        tags = [
            {
                'id': item.tag_id,
                'name': item.tag.name,
                'level': item.level_label(),
                'is_shared': item.tag_id in shared_hobby_ids,
            }
            for item in profile.tags_for(SearchMode.BFF, TagCategory.HOBBY)
        ] + [
            {
                'id': item.tag_id,
                'name': item.tag.name,
                'level': item.level_label(),
                'is_shared': item.tag_id in shared_language_ids,
            }
            for item in profile.tags_for(SearchMode.BFF, TagCategory.LANGUAGE)
        ]

    return {
        'user_id': profile.user_id,
        'display_name': profile.display_name,
        'age': profile.age,
        'city': profile.city,
        'bio': profile_mode.bio if profile_mode else '',
        'photos': [photo.url for photo in photos] if photos else ([_avatar_url(profile)] if _avatar_url(profile) else []),
        'tags': tags,
    }


def discover_candidates_queryset(user, mode):
    """
    Базовий пул профілів для свайпу: доступні для показу, мають анкету
    в потрібному режимі, без самого користувача, вже свайпнутих і
    заблокованих (з обох сторін). Точний відбір за містом/віком/хобі
    та мовами — у next_candidate, бо він залежить від конкретної пари.
    """
    swiped_ids = Like.objects.filter(from_user=user, mode=mode).values_list('to_user_id', flat=True)
    blocked_ids = Block.objects.filter(blocker=user).values_list('blocked_id', flat=True)
    blocked_by_ids = Block.objects.filter(blocked=user).values_list('blocker_id', flat=True)

    return (
        Profile.objects
        .filter(is_discoverable=True, moderation_status=ModerationStatus.APPROVED)
        .filter(modes__mode=mode)
        .exclude(user=user)
        .exclude(user_id__in=list(swiped_ids))
        .exclude(user_id__in=list(blocked_ids))
        .exclude(user_id__in=list(blocked_by_ids))
        .select_related('user')
        .prefetch_related('photos', 'modes', 'profile_tags__tag')
        .distinct()
    )


def next_candidate(user, mode):
    """
    Перший кандидат для свайпу, що проходить фільтри обраного режиму:
    - Dating: те саме місто, вік у діапазоні переглядача, 2+ спільні інтереси;
    - BFF: та сама тема пошуку, спільне хобі й мова з тим самим рівнем.
    Повертає (профіль, спільні_теги) або (None, None), якщо нікого немає.
    """
    viewer_profile = getattr(user, 'profile', None)
    if viewer_profile is None:
        return None, None

    viewer_tags = _tag_level_maps(viewer_profile)
    candidates = discover_candidates_queryset(user, mode).order_by('?')

    for candidate_profile in candidates:
        shared_tags = _match_for_mode(viewer_profile, viewer_tags, candidate_profile, mode)
        if shared_tags is not None:
            return candidate_profile, shared_tags

    return None, None


def record_swipe(from_user, to_user_id, mode, is_positive):
    """Записує лайк/дизлайк; повертає (like, match_or_none)."""
    if from_user.id == int(to_user_id):
        raise ValueError('Не можна свайпнути самого себе.')

    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        to_user = User.objects.get(pk=to_user_id)
    except User.DoesNotExist:
        raise ValueError('Користувача не знайдено.')

    like, _ = Like.objects.update_or_create(
        from_user=from_user,
        to_user=to_user,
        mode=mode,
        defaults={'is_positive': is_positive},
    )

    match = None
    if is_positive:
        mutual = Like.objects.filter(
            from_user=to_user, to_user=from_user, mode=mode, is_positive=True,
        ).exists()
        if mutual:
            user_a, user_b = _canonical_pair(from_user, to_user)
            match, _ = Match.objects.get_or_create(user_a=user_a, user_b=user_b, mode=mode)
            from messaging.services import get_or_create_conversation_for_match
            get_or_create_conversation_for_match(match)

    return like, match


def matches_for_user(user, mode):
    """Список метчів користувача в режимі для панелі «Метчі»."""
    matches = (
        Match.objects
        .filter(mode=mode)
        .filter(Q(user_a=user) | Q(user_b=user))
        .select_related('user_a', 'user_b', 'conversation')
        .order_by('-created_at')
    )

    items = []
    for match in matches:
        other = match.other_user(user)
        profile = getattr(other, 'profile', None)
        conversation = getattr(match, 'conversation', None)
        items.append({
            'match_id': match.id,
            'other_user_id': other.id,
            'display_name': profile.display_name if profile else other.username,
            'age': profile.age if profile else None,
            'avatar_url': _avatar_url(profile) if profile else None,
            'conversation_id': conversation.id if conversation else None,
            'created_at': match.created_at.isoformat(),
        })
    return items


def serialize_match(match):
    """Матч для відповіді після успішного взаємного лайку."""
    conversation = getattr(match, 'conversation', None)
    return {
        'match_id': match.id,
        'mode': match.mode,
        'conversation_id': conversation.id if conversation else None,
    }
