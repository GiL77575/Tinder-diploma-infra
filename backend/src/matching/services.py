"""Логіка свайпів, матчів і списку метчів (окремо для dating і bff)."""

from django.db.models import Q

from matching.models import Block, Like, Match
from profiles.models import ModerationStatus, Profile, SearchMode


def _avatar_url(profile):
    photo = profile.photos.first()
    return photo.url if photo else None


def _canonical_pair(user_a, user_b):
    """user_a.id завжди менший — так, як того вимагає обмеження моделі Match."""
    return (user_a, user_b) if user_a.id < user_b.id else (user_b, user_a)


def serialize_candidate(profile, mode):
    """Картка кандидата для свайпу: фото, ім'я, вік, біо цього режиму."""
    profile_mode = profile.get_mode(mode)
    photos = list(profile.photos.all())
    return {
        'user_id': profile.user_id,
        'display_name': profile.display_name,
        'age': profile.age,
        'city': profile.city,
        'bio': profile_mode.bio if profile_mode else '',
        'photos': [photo.url for photo in photos] if photos else ([_avatar_url(profile)] if _avatar_url(profile) else []),
    }


def discover_candidates_queryset(user, mode):
    """Профілі, доступні для свайпу: без себе, вже свайпнутих і заблокованих."""
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
        .prefetch_related('photos', 'modes')
        .distinct()
    )


def next_candidate(user, mode):
    """Перший доступний кандидат для свайпу у режимі, або None."""
    return discover_candidates_queryset(user, mode).order_by('?').first()


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
