"""Логіка діалогів і повідомлень: списки, історія, статуси прочитання."""

import uuid
from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from matching.models import Match
from messaging.models import Conversation, Message
from profiles.models import SearchMode
from profiles.services import ALLOWED_PHOTO_TYPES, MAX_PHOTO_BYTES

PHOTO_PREVIEW = '📷 Фото'


def get_or_create_conversation_for_match(match):
    """Один чат на матч; створюється разом з матчем, але підстраховуємось."""
    conversation, _ = Conversation.objects.get_or_create(match=match)
    return conversation


def is_participant(user, conversation):
    """Чи є користувач учасником чату матчу або зустрічі."""
    if conversation.match_id:
        match = conversation.match
        return user.id in (match.user_a_id, match.user_b_id)
    if conversation.meeting_id:
        from meetings.models import MeetingParticipant
        return MeetingParticipant.objects.filter(
            meeting_id=conversation.meeting_id, user=user,
        ).exists()
    return False


def can_access_conversation(user, conversation):
    """Учасник + для meeting-чату ще не закритий термін."""
    if not is_participant(user, conversation):
        return False
    if conversation.is_meeting_chat:
        meeting = conversation.meeting
        meeting.ensure_completed_if_due()
        return meeting.is_chat_open
    return True


def participant_user_ids(conversation):
    """Список id усіх учасників чату (2 для матчу, N для зустрічі)."""
    if conversation.match_id:
        match = conversation.match
        return [match.user_a_id, match.user_b_id]
    from meetings.models import MeetingParticipant
    return list(
        MeetingParticipant.objects
        .filter(meeting_id=conversation.meeting_id)
        .values_list('user_id', flat=True)
    )


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


def message_preview(text='', image_url=''):
    """Текст для списку діалогів: підпис або позначка, що надіслано фото."""
    text = (text or '').strip()
    if text:
        return text
    if image_url:
        return PHOTO_PREVIEW
    return ''


def serialize_message(message, viewer):
    """Повідомлення для JSON: текст, фото, час, чи моє, чи прочитане."""
    return {
        'id': message.id,
        'conversation_id': message.conversation_id,
        'text': message.text,
        'image_url': message.image_url or '',
        'sender_id': message.sender_id,
        'is_mine': message.sender_id == viewer.id,
        'is_read': message.read_at is not None,
        'is_edited': message.edited_at is not None,
        'created_at': message.created_at.isoformat(),
        'time_label': _format_timestamp(message.created_at),
    }


def _match_dialog_item(conversation, user, messages):
    other = conversation.match.other_user(user)
    last_message = messages[-1] if messages else None
    unread_count = sum(
        1 for message in messages
        if message.sender_id != user.id and message.read_at is None
    )
    last_at = last_message.created_at if last_message else conversation.created_at
    profile = getattr(other, 'profile', None)
    return {
        'conversation_id': conversation.id,
        'kind': 'match',
        'match_id': conversation.match_id,
        'meeting_id': None,
        'other_user_id': other.id,
        'other_display_name': profile.display_name if profile else other.username,
        'other_age': profile.age if profile else None,
        'avatar_url': _avatar_url(other),
        'last_message_preview': (
            message_preview(last_message.text, last_message.image_url)
            if last_message else ''
        ),
        'last_message_time': _format_timestamp(last_at),
        'last_message_is_mine': bool(last_message and last_message.sender_id == user.id),
        'last_message_is_read': bool(last_message and last_message.read_at is not None),
        'unread_count': unread_count,
        '_sort_ts': last_at,
    }


def _meeting_dialog_item(conversation, user, messages):
    meeting = conversation.meeting
    meeting.ensure_completed_if_due()
    if not meeting.is_chat_open:
        return None
    last_message = messages[-1] if messages else None
    unread_count = sum(
        1 for message in messages
        if message.sender_id != user.id and message.read_at is None
    )
    last_at = last_message.created_at if last_message else conversation.created_at
    return {
        'conversation_id': conversation.id,
        'kind': 'meeting',
        'match_id': None,
        'meeting_id': meeting.id,
        'other_user_id': None,
        'other_display_name': meeting.title,
        'other_age': None,
        'avatar_url': None,
        'last_message_preview': (
            message_preview(last_message.text, last_message.image_url)
            if last_message else ''
        ),
        'last_message_time': _format_timestamp(last_at),
        'last_message_is_mine': bool(last_message and last_message.sender_id == user.id),
        'last_message_is_read': bool(last_message and last_message.read_at is not None),
        'unread_count': unread_count,
        '_sort_ts': last_at,
    }


def conversations_for_user(user, mode):
    """Список діалогів користувача в режимі: непрочитані спершу, потім свіжіші."""
    items = []

    match_conversations = (
        Conversation.objects
        .filter(match__mode=mode, match__isnull=False)
        .filter(Q(match__user_a=user) | Q(match__user_b=user))
        .select_related('match', 'match__user_a', 'match__user_b')
        .prefetch_related('messages')
    )
    for conversation in match_conversations:
        messages = list(conversation.messages.all())
        items.append(_match_dialog_item(conversation, user, messages))

    if mode == SearchMode.BFF:
        from meetings.models import MeetingParticipant

        meeting_ids = MeetingParticipant.objects.filter(user=user).values_list(
            'meeting_id', flat=True,
        )
        meeting_conversations = (
            Conversation.objects
            .filter(meeting_id__in=meeting_ids, meeting__isnull=False)
            .select_related('meeting')
            .prefetch_related('messages')
        )
        for conversation in meeting_conversations:
            messages = list(conversation.messages.all())
            item = _meeting_dialog_item(conversation, user, messages)
            if item is not None:
                items.append(item)

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


def save_chat_image(conversation_id, user_id, uploaded_file):
    """Завантажує фото чату в Cloudinary або локально; повертає (public_id, url)."""
    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise ValueError('Фото має бути JPEG, PNG або WebP.')
    if uploaded_file.size > MAX_PHOTO_BYTES:
        raise ValueError('Фото має бути не більше 5 МБ.')

    if settings.CLOUDINARY_URL:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            uploaded_file,
            folder=f'crushme/chat/{conversation_id}',
            resource_type='image',
        )
        return result['public_id'], result['secure_url']

    ext = Path(uploaded_file.name or '').suffix.lower()
    if ext not in {'.jpg', '.jpeg', '.png', '.webp'}:
        ext = '.jpg'
    filename = f'{user_id}_{uuid.uuid4().hex}{ext}'
    rel_dir = Path('chat') / str(conversation_id)
    dest_dir = Path(settings.MEDIA_ROOT) / rel_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    uploaded_file.seek(0)
    with dest.open('wb+') as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)
    public_id = f'local:{rel_dir.as_posix()}/{filename}'
    url = f'{settings.MEDIA_URL}{rel_dir.as_posix()}/{filename}'
    return public_id, url


def create_message(conversation, sender, text, image_url='', image_public_id=''):
    """Створює повідомлення від sender у чаті (текст і/або фото)."""
    if conversation.is_meeting_chat:
        from meetings.services import assert_conversation_writable
        assert_conversation_writable(conversation)

    text = (text or '').strip()
    image_url = (image_url or '').strip()
    image_public_id = (image_public_id or '').strip()
    if not text and not image_url:
        raise ValueError('Повідомлення не може бути порожнім.')
    if len(text) > 2000:
        raise ValueError('Повідомлення занадто довге.')
    return Message.objects.create(
        conversation=conversation,
        sender=sender,
        text=text,
        image_url=image_url,
        image_public_id=image_public_id,
    )


def _channel_layer():
    from channels.layers import get_channel_layer
    return get_channel_layer()


def _group_send(group, event):
    layer = _channel_layer()
    if layer is None:
        return
    from asgiref.sync import async_to_sync
    async_to_sync(layer.group_send)(group, event)


def _dialog_event(conversation, preview, time_label, sender_id):
    return {
        'type': 'dialog.update',
        'conversation_id': conversation.id,
        'preview': preview,
        'time_label': time_label,
        'sender_id': sender_id,
        'mode': conversation.mode,
    }


def _notify_dialog_preview(conversation, actor, last_message=None):
    """Оновлює прев’ю діалогу в inbox усіх учасників."""
    if last_message is None:
        last_message = conversation.messages.order_by('created_at').last()
    if last_message:
        event = _dialog_event(
            conversation,
            message_preview(last_message.text, last_message.image_url),
            _format_timestamp(last_message.created_at),
            last_message.sender_id,
        )
    else:
        event = _dialog_event(conversation, '', '', actor.id)
    for user_id in participant_user_ids(conversation):
        _group_send(f'user_{user_id}', event)


def _owned_message(conversation, user, message_id):
    """Повідомлення користувача в цьому чаті або None."""
    return conversation.messages.filter(pk=message_id, sender=user).first()


def edit_own_message(conversation, user, message_id, text):
    """Редагує текст свого повідомлення; фото без підпису редагувати не можна."""
    if conversation.is_meeting_chat:
        from meetings.services import assert_conversation_writable
        assert_conversation_writable(conversation)

    message = _owned_message(conversation, user, message_id)
    if message is None:
        raise ValueError('Повідомлення не знайдено.')
    text = (text or '').strip()
    if not message.image_url and not text:
        raise ValueError('Повідомлення не може бути порожнім.')
    if not text:
        raise ValueError('Фото без тексту не редагується.')
    if len(text) > 2000:
        raise ValueError('Повідомлення занадто довге.')
    if text == (message.text or '').strip():
        return message
    message.text = text
    message.edited_at = timezone.now()
    message.save(update_fields=['text', 'edited_at'])
    return message


def delete_own_message(conversation, user, message_id):
    """Видаляє своє повідомлення з чату (для всіх учасників)."""
    if conversation.is_meeting_chat:
        from meetings.services import assert_conversation_writable
        assert_conversation_writable(conversation)

    message = _owned_message(conversation, user, message_id)
    if message is None:
        raise ValueError('Повідомлення не знайдено.')
    message_id = message.id
    message.delete()
    return message_id


def broadcast_message_edited(conversation, message, editor):
    """Розсилає відредаговане повідомлення в чат і оновлює прев’ю діалогу."""
    message_data = serialize_message(message, editor)
    _group_send(
        f'conversation_{conversation.id}',
        {'type': 'chat.message_edited', 'message': message_data},
    )
    _notify_dialog_preview(conversation, editor, message)
    return message_data


def broadcast_message_deleted(conversation, message_id, actor):
    """Прибирає повідомлення в клієнтах і оновлює прев’ю діалогу."""
    _group_send(
        f'conversation_{conversation.id}',
        {
            'type': 'chat.message_deleted',
            'message_id': message_id,
            'conversation_id': conversation.id,
        },
    )
    _notify_dialog_preview(conversation, actor)
    return {'message_id': message_id, 'conversation_id': conversation.id}


def broadcast_new_message(conversation, message, sender):
    """Розсилає нове повідомлення в групу чату і в inbox усіх учасників."""
    message_data = serialize_message(message, sender)
    _group_send(
        f'conversation_{conversation.id}',
        {'type': 'chat.message', 'message': message_data},
    )
    dialog_event = _dialog_event(
        conversation,
        message_preview(message.text, message.image_url),
        message_data['time_label'],
        message_data['sender_id'],
    )
    for user_id in participant_user_ids(conversation):
        _group_send(f'user_{user_id}', dialog_event)
    return message_data


def open_conversation_for_match(user, match_id):
    """Повертає чат матчу, якщо user — один з учасників; інакше None."""
    try:
        match = Match.objects.get(pk=match_id)
    except Match.DoesNotExist:
        return None
    if user.id not in (match.user_a_id, match.user_b_id):
        return None
    return get_or_create_conversation_for_match(match)


def conversation_header_payload(conversation, viewer):
    """Метадані шапки чату для match або meeting."""
    if conversation.is_meeting_chat:
        meeting = conversation.meeting
        meeting.ensure_completed_if_due()
        return {
            'conversation_id': conversation.id,
            'kind': 'meeting',
            'mode': conversation.mode,
            'match_id': None,
            'meeting_id': meeting.id,
            'is_creator': meeting.creator_id == viewer.id,
            'is_chat_open': meeting.is_chat_open,
            'other_user': {
                'id': None,
                'display_name': meeting.title,
                'age': None,
                'avatar_url': None,
            },
            'meeting': {
                'id': meeting.id,
                'title': meeting.title,
                'location': meeting.location,
                'starts_at': meeting.starts_at.isoformat(),
                'status': meeting.status,
            },
        }

    other = conversation.match.other_user(viewer)
    profile = getattr(other, 'profile', None)
    return {
        'conversation_id': conversation.id,
        'kind': 'match',
        'mode': conversation.mode,
        'match_id': conversation.match_id,
        'meeting_id': None,
        'is_creator': False,
        'is_chat_open': True,
        'other_user': {
            'id': other.id,
            'display_name': profile.display_name if profile else other.username,
            'age': profile.age if profile else None,
            'avatar_url': (
                profile.photos.first().url
                if profile and profile.photos.first()
                else None
            ),
        },
        'meeting': None,
    }
