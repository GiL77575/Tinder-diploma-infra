"""CSS/JS через Django: nginx на проді часто alias /static/ на застарілу папку.

Той самий прийом, що й /app/media/: шлях /app/static/ уже проксується на бекенд,
тож після git pull картки беруть той самий chat.css/chat.js, що й локально.
"""

from django.contrib.staticfiles.views import serve as serve_static
from django.views.decorators.http import require_GET


@require_GET
def serve_frontend_static(request, path):
    """Віддає файл зі STATICFILES_DIRS навіть коли DEBUG=False."""
    response = serve_static(request, path, insecure=True)
    response['Cache-Control'] = 'public, max-age=120, must-revalidate'
    return response
