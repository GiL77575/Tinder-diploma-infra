"""Кореневі URL: адмінка, Google OAuth, профіль, акаунт."""

from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.media import serve_user_media
from core.static_serve import serve_frontend_static

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/signup/',
        RedirectView.as_view(pattern_name='register', permanent=False),
    ),
    path(
        'accounts/login/',
        RedirectView.as_view(pattern_name='login', permanent=False),
    ),
    path('accounts/', include('allauth.urls')),
    path('profile/', include('profiles.urls')),
    # Перед include('app/'): nginx alias /static/ і /media/ на хост — старі CSS
    # і 403 на фото. Віддаємо через Django за шляхом, який уже йде в проксі.
    path('app/static/<path:path>', serve_frontend_static, name='frontend_static'),
    path('app/media/<path:path>', serve_user_media, name='user_media'),
    path('app/', include('matching.urls')),
    path('app/', include('messaging.urls')),
    path('app/', include('meetings.urls')),
    path('', include('accounts.urls')),
    re_path(r'^static/(?P<path>.*)$', serve_frontend_static),
    re_path(r'^media/(?P<path>.*)$', serve_user_media),
]
