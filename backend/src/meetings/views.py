"""JSON API для зустрічей (BFF)."""

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from meetings.services import (
    MeetingError,
    cancel_meeting,
    create_meeting,
    get_active_meeting,
    get_meeting_for_update,
    join_meeting,
    leave_meeting,
    serialize_meeting,
    update_meeting,
    user_can_access_meeting_chat,
)


def _json_body(request):
    try:
        return json.loads(request.body or '{}')
    except json.JSONDecodeError as exc:
        raise MeetingError('Невірний формат запиту.') from exc


def _error_response(exc):
    status = getattr(exc, 'status', 400)
    return JsonResponse({'error': str(exc)}, status=status)


def _starts_at_from_payload(payload):
    """Приймає starts_at ISO або date + time окремо."""
    if payload.get('starts_at'):
        return payload['starts_at']
    date_part = (payload.get('date') or '').strip()
    time_part = (payload.get('time') or '').strip()
    if date_part and time_part:
        if len(time_part) == 5:
            time_part = f'{time_part}:00'
        return f'{date_part}T{time_part}'
    raise MeetingError('Вкажіть дату і час зустрічі.')


@login_required
@require_GET
def meeting_mine_view(request):
    """Активна зустріч поточного користувача або null."""
    meeting = get_active_meeting(request.user)
    return JsonResponse({
        'meeting': serialize_meeting(meeting, request.user) if meeting else None,
    })


@login_required
@require_POST
def meeting_create_view(request):
    try:
        payload = _json_body(request)
        meeting = create_meeting(
            request.user,
            title=payload.get('title'),
            location=payload.get('location'),
            description=payload.get('description'),
            starts_at=_starts_at_from_payload(payload),
        )
    except MeetingError as exc:
        return _error_response(exc)
    return JsonResponse({'meeting': serialize_meeting(meeting, request.user)}, status=201)


@login_required
@require_GET
def meeting_detail_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    return JsonResponse({'meeting': serialize_meeting(meeting, request.user)})


@login_required
@require_http_methods(['POST'])
def meeting_edit_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    try:
        payload = _json_body(request)
        meeting = update_meeting(
            request.user,
            meeting,
            title=payload.get('title'),
            location=payload.get('location'),
            description=payload.get('description'),
            starts_at=_starts_at_from_payload(payload),
        )
    except MeetingError as exc:
        return _error_response(exc)
    return JsonResponse({'meeting': serialize_meeting(meeting, request.user)})


@login_required
@require_POST
def meeting_cancel_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    try:
        meeting = cancel_meeting(request.user, meeting)
    except MeetingError as exc:
        return _error_response(exc)
    return JsonResponse({'meeting': serialize_meeting(meeting, request.user)})


@login_required
@require_POST
def meeting_join_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    try:
        meeting = join_meeting(request.user, meeting)
    except MeetingError as exc:
        return _error_response(exc)
    return JsonResponse({'meeting': serialize_meeting(meeting, request.user)})


@login_required
@require_POST
def meeting_leave_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    try:
        leave_meeting(request.user, meeting)
    except MeetingError as exc:
        return _error_response(exc)
    return JsonResponse({'ok': True})


@login_required
@require_GET
def meeting_chat_view(request, meeting_id):
    meeting = get_meeting_for_update(meeting_id)
    if meeting is None:
        return JsonResponse({'error': 'Зустріч не знайдено.'}, status=404)
    if not user_can_access_meeting_chat(request.user, meeting):
        return JsonResponse({'error': 'Немає доступу до чату зустрічі.'}, status=403)
    try:
        conversation = meeting.conversation
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Чат зустрічі не знайдено.'}, status=404)
    return JsonResponse({
        'conversation_id': conversation.id,
        'meeting_id': meeting.id,
        'mode': 'bff',
    })
