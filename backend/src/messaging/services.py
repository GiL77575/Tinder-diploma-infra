"""Логіка діалогів і повідомлень: списки, історія, статуси прочитання."""

from django.db.models import Q
from django.utils import timezone

from matching.models import Match
from messaging.models import Conversation, Message


def get_or_create_conversation_for_match(match):
    """Один чат на матч; створюється разом з матчем, але підстраховуємось."""
    conversation, _ = Conversation.objects.get_or_create(match=match)
    return conversation


def is_participant(user, conversation):
    """Чи є користувач одним з двох учасників чату матчу."""
    match = conversation.match
    return user.id in (match.user_a_id, match.user_b_id)


def _avatar_url(user):
    """URL головного фото користувача або None."""
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    photo = profile.photos.first()
    return photo.url if photo else None


def _format_timestamp(dt):
    """'18:38' сьогодні, інакше '20.08.2026' — як у макеті списку діалогів."""
    local = timezone.localtime(dt)
    if local.date() == timezone.localdate():
        return local.strftime('%H:%M')
    return local.strftime('%d.%m.%Y')


def serialize_message(message, viewer):
    """Повідомлення для JSON: текст, час, чи моє, чи прочитане."""
    return {
        'id': message.id,
        'conversation_id': message.conversation_id,
        'text': message.text,
        'sender_id': message.sender_id,
        'is_mine': message.sender_id == viewer.id,
        'is_read': message.read_at is not None,
        'created_at': message.created_at.isoformat(),
        'time_label': _format_timestamp(message.created_at),
    }


def conversations_for_user(user, mode):
    """Список діалогів користувача в режимі: непрочитані спершу, потім свіжіші."""
    conversations = (
        Conversation.objects
        .filter(match__mode=mode)
        .filter(Q(match__user_a=user) | Q(match__user_b=user))
        .select_related('match', 'match__user_a', 'match__user_b')
        .prefetch_related('messages')
    )

    items = []
    for conversation in conversations:
        other = conversation.match.other_user(user)
        messages = list(conversation.messages.all())
        last_message = messages[-1] if messages else None
        unread_count = sum(
            1 for message in messages
            if message.sender_id != user.id and message.read_at is None
        )
        last_at = last_message.created_at if last_message else conversation.created_at
        profile = getattr(other, 'profile', None)

        items.append({
            'conversation_id': conversation.id,
            'match_id': conversation.match_id,
            'other_user_id': other.id,
            'other_display_name': profile.display_name if profile else other.username,
            'other_age': profile.age if profile else None,
            'avatar_url': _avatar_url(other),
            'last_message_preview': last_message.text if last_message else '',
            'last_message_time': _format_timestamp(last_at),
            'last_message_is_mine': bool(last_message and last_message.sender_id == user.id),
            'last_message_is_read': bool(last_message and last_message.read_at is not None),
            'unread_count': unread_count,
            '_sort_ts': last_at,
        })

    items.sort(key=lambda item: (0 if item['unread_count'] > 0 else 1, -item['_sort_ts'].timestamp()))
    for item in items:
        item.pop('_sort_ts')
    return items


def messages_for_conversation(conversation, viewer):
    """Історія повідомлень чату, від найстарішого до найновішого."""
    messages = conversation.messages.select_related('sender').all()
    return [serialize_message(message, viewer) for message in messages]


def mark_conversation_read(conversation, viewer):
    """Позначає всі чужі непрочитані повідомлення як прочитані поточним користувачем."""
    updated = conversation.messages.filter(
        read_at__isnull=True,
    ).exclude(sender=viewer).update(read_at=timezone.now())
    return updated


def create_message(conversation, sender, text):
    """Створює повідомлення від sender у чаті (sender завжди — авторизований юзер)."""
    text = (text or '').strip()
    if not text:
        raise ValueError('Повідомлення не може бути порожнім.')
    if len(text) > 2000:
        raise ValueError('Повідомлення занадто довге.')
    return Message.objects.create(conversation=conversation, sender=sender, text=text)


def open_conversation_for_match(user, match_id):
    """Повертає чат матчу, якщо user — один з учасників; інакше None."""
    try:
        match = Match.objects.get(pk=match_id)
    except Match.DoesNotExist:
        return None
    if user.id not in (match.user_a_id, match.user_b_id):
        return None
    return get_or_create_conversation_for_match(match)
