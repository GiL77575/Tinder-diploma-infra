"""JSON API для панелі діалогів і чату (споживається chat.js)."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from messaging.models import Conversation
from messaging.services import (
    broadcast_message_deleted,
    broadcast_message_edited,
    broadcast_new_message,
    conversations_for_user,
    create_message,
    delete_own_message,
    edit_own_message,
    is_participant,
    mark_conversation_read,
    messages_for_conversation,
    open_conversation_for_match,
    save_chat_image,
)
from profiles.models import SearchMode


def _valid_mode(mode):
    return mode in dict(SearchMode.choices)


@login_required
@require_GET
def conversations_list_view(request):
    """Список діалогів поточного користувача в обраному режимі."""
    mode = request.GET.get('mode', SearchMode.DATING)
    if not _valid_mode(mode):
        return JsonResponse({'error': 'Невірний режим.'}, status=400)
    return JsonResponse({'conversations': conversations_for_user(request.user, mode)})


@login_required
@require_POST
def open_conversation_view(request):
    """Відкриває (або підстраховано створює) чат за id матчу свого користувача."""
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невірний формат запиту.'}, status=400)

    match_id = payload.get('match_id')
    if not match_id:
        return JsonResponse({'error': 'Не вказано match_id.'}, status=400)

    conversation = open_conversation_for_match(request.user, match_id)
    if conversation is None:
        return JsonResponse({'error': 'Матч не знайдено або немає доступу.'}, status=404)

    return JsonResponse({
        'conversation_id': conversation.id,
        'match_id': conversation.match_id,
        'mode': conversation.mode,
    })


def _get_owned_conversation(request, conversation_id):
    """Чат за id, лише якщо запитувач — його учасник; інакше None."""
    try:
        conversation = Conversation.objects.select_related(
            'match', 'match__user_a', 'match__user_b',
        ).get(pk=conversation_id)
    except Conversation.DoesNotExist:
        return None
    if not is_participant(request.user, conversation):
        return None
    return conversation


@login_required
@require_GET
def conversation_messages_view(request, conversation_id):
    """Історія повідомлень чату (тільки для його учасників)."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)

    other = conversation.match.other_user(request.user)
    profile = getattr(other, 'profile', None)
    return JsonResponse({
        'conversation_id': conversation.id,
        'mode': conversation.mode,
        'other_user': {
            'id': other.id,
            'display_name': profile.display_name if profile else other.username,
            'age': profile.age if profile else None,
            'avatar_url': profile.photos.first().url if profile and profile.photos.first() else None,
        },
        'messages': messages_for_conversation(conversation, request.user),
    })


@login_required
@require_POST
def conversation_send_message_view(request, conversation_id):
    """HTTP fallback для відправлення повідомлення (основний шлях — WebSocket)."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невірний формат запиту.'}, status=400)

    try:
        message = create_message(conversation, request.user, payload.get('text', ''))
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({
        'message': broadcast_new_message(conversation, message, request.user),
    })


@login_required
@require_POST
def conversation_send_photo_view(request, conversation_id):
    """Завантажує фото в чат (multipart) і розсилає повідомлення через канал."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)

    uploaded = request.FILES.get('image')
    if not uploaded:
        return JsonResponse({'error': 'Додайте фото.'}, status=400)

    try:
        public_id, url = save_chat_image(conversation.id, request.user.id, uploaded)
        message = create_message(
            conversation,
            request.user,
            request.POST.get('text', ''),
            image_url=url,
            image_public_id=public_id,
        )
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({
        'message': broadcast_new_message(conversation, message, request.user),
    })


@login_required
@require_POST
def conversation_mark_read_view(request, conversation_id):
    """Позначає повідомлення співрозмовника прочитаними."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)
    updated = mark_conversation_read(conversation, request.user)
    return JsonResponse({'updated': updated})


@login_required
@require_POST
def conversation_edit_message_view(request, conversation_id, message_id):
    """Редагує своє текстове повідомлення; зміни бачать обидва учасники."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невірний формат запиту.'}, status=400)

    try:
        message = edit_own_message(
            conversation, request.user, message_id, payload.get('text', ''),
        )
    except ValueError as exc:
        status = 404 if str(exc) == 'Повідомлення не знайдено.' else 400
        return JsonResponse({'error': str(exc)}, status=status)

    return JsonResponse({
        'message': broadcast_message_edited(conversation, message, request.user),
    })


@login_required
@require_POST
def conversation_delete_message_view(request, conversation_id, message_id):
    """Видаляє своє повідомлення з чату в обох учасників."""
    conversation = _get_owned_conversation(request, conversation_id)
    if conversation is None:
        return JsonResponse({'error': 'Чат не знайдено або немає доступу.'}, status=404)

    try:
        deleted_id = delete_own_message(conversation, request.user, message_id)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=404)

    return JsonResponse(broadcast_message_deleted(conversation, deleted_id, request.user))
