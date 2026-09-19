"""Бізнес-логіка зустрічей: CRUD, join/leave, серіалізація."""

from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from meetings.models import Meeting, MeetingParticipant, MeetingStatus
from messaging.models import Conversation


class MeetingError(Exception):
    """Помилка бізнес-логіки зустрічі з повідомленням для клієнта."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def _parse_starts_at(value):
    """Приймає ISO datetime або окремі date+time; повертає aware datetime."""
    if isinstance(value, datetime):
        starts_at = value
    elif isinstance(value, str):
        starts_at = parse_datetime(value.strip())
        if starts_at is None:
            raise MeetingError('Невірний формат дати/часу.')
    else:
        raise MeetingError('Невірний формат дати/часу.')

    if timezone.is_naive(starts_at):
        starts_at = timezone.make_aware(starts_at, timezone.get_current_timezone())
    return starts_at


def _validate_meeting_fields(title, location, description, starts_at, *, require_future=True):
    title = (title or '').strip()
    location = (location or '').strip()
    description = (description or '').strip()
    if not title:
        raise MeetingError('Вкажіть назву зустрічі.')
    if not location:
        raise MeetingError('Вкажіть місце зустрічі.')
    if not description:
        raise MeetingError('Додайте короткий опис.')
    if len(title) > 120:
        raise MeetingError('Назва занадто довга.')
    if len(location) > 200:
        raise MeetingError('Місце занадто довге.')
    if len(description) > 1000:
        raise MeetingError('Опис занадто довгий.')
    if require_future and starts_at <= timezone.now():
        raise MeetingError('Дата і час зустрічі не можуть бути в минулому.')
    return title, location, description, starts_at


def get_meeting_for_update(meeting_id):
    """Завантажити зустріч і lazy-completed; None якщо немає."""
    try:
        meeting = Meeting.objects.select_related('creator', 'conversation').get(pk=meeting_id)
    except Meeting.DoesNotExist:
        return None
    meeting.ensure_completed_if_due()
    return meeting


def get_active_meeting(user):
    """ACTIVE зустріч користувача (після lazy COMPLETED) або None."""
    meeting = (
        Meeting.objects
        .filter(creator=user, status=MeetingStatus.ACTIVE)
        .select_related('conversation')
        .first()
    )
    if meeting is None:
        return None
    meeting.ensure_completed_if_due()
    if meeting.status != MeetingStatus.ACTIVE:
        return None
    return meeting


def is_meeting_participant(user, meeting):
    return MeetingParticipant.objects.filter(meeting=meeting, user=user).exists()


def user_can_access_meeting_chat(user, meeting):
    meeting.ensure_completed_if_due()
    if not meeting.is_chat_open:
        return False
    return is_meeting_participant(user, meeting)


def serialize_meeting(meeting, viewer):
    """JSON для popup і sidebar."""
    meeting.ensure_completed_if_due()
    is_creator = meeting.creator_id == viewer.id
    is_participant = is_meeting_participant(viewer, meeting)
    conversation_id = None
    try:
        conversation_id = meeting.conversation.id
    except ObjectDoesNotExist:
        conversation_id = None
    can_join = (
        meeting.status == MeetingStatus.ACTIVE
        and not meeting.is_past
        and not is_participant
    )
    can_open_chat = is_participant and meeting.is_chat_open
    local_start = timezone.localtime(meeting.starts_at)
    return {
        'id': meeting.id,
        'title': meeting.title,
        'location': meeting.location,
        'description': meeting.description,
        'starts_at': meeting.starts_at.isoformat(),
        'date': local_start.strftime('%Y-%m-%d'),
        'time': local_start.strftime('%H:%M'),
        'status': meeting.status,
        'creator_id': meeting.creator_id,
        'is_creator': is_creator,
        'is_participant': is_participant,
        'conversation_id': conversation_id,
        'can_join': can_join,
        'can_open_chat': can_open_chat,
        'chat_closes_at': meeting.chat_closes_at.isoformat(),
        'is_chat_open': meeting.is_chat_open,
        'participant_count': meeting.participants.count(),
    }


@transaction.atomic
def create_meeting(user, *, title, location, description, starts_at):
    starts_at = _parse_starts_at(starts_at)
    title, location, description, starts_at = _validate_meeting_fields(
        title, location, description, starts_at,
    )
    if get_active_meeting(user) is not None:
        raise MeetingError('У вас уже є активна зустріч.', status=400)

    try:
        meeting = Meeting.objects.create(
            creator=user,
            title=title,
            location=location,
            description=description,
            starts_at=starts_at,
            status=MeetingStatus.ACTIVE,
        )
    except IntegrityError as exc:
        raise MeetingError('У вас уже є активна зустріч.', status=400) from exc

    MeetingParticipant.objects.create(meeting=meeting, user=user)
    Conversation.objects.create(meeting=meeting, match=None)
    return meeting


@transaction.atomic
def update_meeting(user, meeting, *, title, location, description, starts_at):
    meeting.ensure_completed_if_due()
    if meeting.creator_id != user.id:
        raise MeetingError('Редагувати зустріч може лише автор.', status=403)
    if meeting.status != MeetingStatus.ACTIVE:
        raise MeetingError('Можна редагувати лише активну зустріч.', status=400)

    starts_at = _parse_starts_at(starts_at)
    title, location, description, starts_at = _validate_meeting_fields(
        title, location, description, starts_at,
    )
    meeting.title = title
    meeting.location = location
    meeting.description = description
    meeting.starts_at = starts_at
    meeting.save(update_fields=['title', 'location', 'description', 'starts_at', 'updated_at'])
    return meeting


@transaction.atomic
def cancel_meeting(user, meeting):
    meeting.ensure_completed_if_due()
    if meeting.creator_id != user.id:
        raise MeetingError('Скасувати зустріч може лише автор.', status=403)
    if meeting.status == MeetingStatus.CANCELLED:
        raise MeetingError('Зустріч уже скасована.', status=400)
    meeting.status = MeetingStatus.CANCELLED
    meeting.save(update_fields=['status', 'updated_at'])
    return meeting


@transaction.atomic
def join_meeting(user, meeting):
    meeting.ensure_completed_if_due()
    if meeting.status != MeetingStatus.ACTIVE:
        raise MeetingError('До цієї зустрічі вже не можна приєднатися.', status=400)
    if meeting.is_past:
        raise MeetingError('Час зустрічі вже минув.', status=400)
    if is_meeting_participant(user, meeting):
        raise MeetingError('Ви вже є учасником цієї зустрічі.', status=400)

    try:
        MeetingParticipant.objects.create(meeting=meeting, user=user)
    except IntegrityError as exc:
        raise MeetingError('Ви вже є учасником цієї зустрічі.', status=400) from exc
    return meeting


@transaction.atomic
def leave_meeting(user, meeting):
    meeting.ensure_completed_if_due()
    if meeting.creator_id == user.id:
        raise MeetingError(
            'Автор не може вийти із зустрічі. Скасуйте зустріч.',
            status=400,
        )
    deleted, _ = MeetingParticipant.objects.filter(meeting=meeting, user=user).delete()
    if not deleted:
        raise MeetingError('Ви не є учасником цієї зустрічі.', status=400)
    return meeting


def active_meeting_id_for_user(user):
    """id ACTIVE зустрічі для discover-картки або None."""
    meeting = get_active_meeting(user)
    return meeting.id if meeting else None


def assert_conversation_writable(conversation):
    """Для meeting-чату перевірити, що чат ще відкритий."""
    if not conversation.is_meeting_chat:
        return
    meeting = conversation.meeting
    meeting.ensure_completed_if_due()
    if not meeting.is_chat_open:
        raise ValueError('Чат зустрічі вже закрито.')
