"""Головна сторінка застосунку (метчі + діалоги + чат/картка) і JSON API свайпів."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from matching.services import (
    matches_for_user,
    next_candidate,
    record_swipe,
    serialize_candidate,
    serialize_match,
)
from profiles.models import SearchMode


def _valid_mode(mode):
    return mode in dict(SearchMode.choices)


@login_required
def dashboard_view(request):
    """Головний екран: хедер з перемикачем режимів, метчі, діалоги, картка/чат."""
    if not request.user.is_profile_complete:
        return redirect('profile_setup')

    profile = getattr(request.user, 'profile', None)
    initial_mode = profile.active_mode if profile else SearchMode.DATING
    avatar = profile.photos.first() if profile else None
    return render(request, 'chat/dashboard.html', {
        'initial_mode': initial_mode,
        'modes': SearchMode.choices,
        'my_display_name': profile.display_name if profile else request.user.username,
        'my_age': profile.age if profile else None,
        'my_avatar_url': avatar.url if avatar else None,
    })


@login_required
@require_GET
def discover_next_view(request):
    """Наступний кандидат для свайпу, що проходить фільтри обраного режиму."""
    mode = request.GET.get('mode', SearchMode.DATING)
    if not _valid_mode(mode):
        return JsonResponse({'error': 'Невірний режим.'}, status=400)

    profile, shared_tags = next_candidate(request.user, mode)
    if profile is None:
        return JsonResponse({'candidate': None})
    return JsonResponse({'candidate': serialize_candidate(profile, mode, shared_tags)})


@login_required
@require_POST
def like_view(request):
    """Лайк/дизлайк кандидата; за взаємності — створює матч і чат."""
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Невірний формат запиту.'}, status=400)

    mode = payload.get('mode', SearchMode.DATING)
    to_user_id = payload.get('to_user_id')
    is_positive = bool(payload.get('is_positive'))

    if not _valid_mode(mode):
        return JsonResponse({'error': 'Невірний режим.'}, status=400)
    if not to_user_id:
        return JsonResponse({'error': 'Не вказано to_user_id.'}, status=400)

    try:
        _, match = record_swipe(request.user, to_user_id, mode, is_positive)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({'match': serialize_match(match) if match else None})


@login_required
@require_GET
def matches_list_view(request):
    """Список метчів користувача для панелі «Метчі»."""
    mode = request.GET.get('mode', SearchMode.DATING)
    if not _valid_mode(mode):
        return JsonResponse({'error': 'Невірний режим.'}, status=400)
    return JsonResponse({'matches': matches_for_user(request.user, mode)})
