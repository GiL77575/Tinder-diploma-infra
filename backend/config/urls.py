"""Кореневі URL: адмінка, Google OAuth, профіль, акаунт."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve as media_serve

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
    path('app/', include('matching.urls')),
    path('app/', include('messaging.urls')),
    path('app/', include('meetings.urls')),
    path('', include('accounts.urls')),
]

# Локальні фото (профіль/зустріч), коли CLOUDINARY_URL порожній.
# django.conf.urls.static.static() у DEBUG=False нічого не додає — тому явно.
# У проді краще віддавати nginx'ом (deploy/nginx-crushme.conf).
urlpatterns += [
    re_path(
        r'^media/(?P<path>.*)$',
        media_serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
