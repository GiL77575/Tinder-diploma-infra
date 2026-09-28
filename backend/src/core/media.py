"""Локальні завантаження: nginx на проді часто перехоплює /media/ і віддає 403.

Файли лежать у MEDIA_ROOT, а публічний URL іде через Django (/app/media/...),
який проксі вже пропускає на бекенд."""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404

APP_MEDIA_PREFIX = '/app/media/'


def public_media_url(url):
    """Cloudinary лишаємо як є; локальний /media/... → /app/media/..."""
    if not url:
        return ''
    url = str(url).strip()
    if url.startswith(('http://', 'https://', APP_MEDIA_PREFIX)):
        return url
    media_url = settings.MEDIA_URL or '/media/'
    if url.startswith(media_url):
        rel = url[len(media_url):].lstrip('/')
        return f'{APP_MEDIA_PREFIX}{rel}'
    if url.startswith('/media/'):
        return f'{APP_MEDIA_PREFIX}{url[len("/media/"):]}'
    return url


def serve_user_media(request, path):
    """Віддає файл з MEDIA_ROOT без directory traversal."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    full = (media_root / path).resolve()
    try:
        full.relative_to(media_root)
    except ValueError as exc:
        raise Http404() from exc
    if not full.is_file():
        raise Http404()
    content_type, _ = mimetypes.guess_type(str(full))
    return FileResponse(full.open('rb'), content_type=content_type or 'application/octet-stream')
