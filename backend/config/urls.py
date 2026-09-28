"""Кореневі URL: адмінка, Google OAuth, профіль, акаунт."""

from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from core.media import serve_user_media

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
    # Перед include('app/'): nginx на проді часто 403 на /media/, тож файли
    # віддаємо через Django за шляхом, який уже проксується на бекенд.
    path('app/media/<path:path>', serve_user_media, name='user_media'),
    path('app/', include('matching.urls')),
    path('app/', include('messaging.urls')),
    path('app/', include('meetings.urls')),
    path('', include('accounts.urls')),
    re_path(r'^media/(?P<path>.*)$', serve_user_media),
]
