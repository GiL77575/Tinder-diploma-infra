"""Middleware для reverse-proxy: фіксує публічний Host."""

from django.conf import settings


class PublicHostMiddleware:
    """Підставляє PUBLIC_HOST замість приватного IP у Host / X-Forwarded-*.

    Інакше Google OAuth відхиляє redirect_uri з адреси на кшталт 10.x
    («device_id and device_name are required for private IP»).
    PUBLIC_HOST має збігатися з Google Console і django Site.domain.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.public_host = getattr(settings, 'PUBLIC_HOST', '').strip()

    def __call__(self, request):
        if self.public_host:
            request.META['HTTP_HOST'] = self.public_host
            request.META['HTTP_X_FORWARDED_HOST'] = self.public_host
            # OAuth callback має бути https://..., не http://
            request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
            request.META['wsgi.url_scheme'] = 'https'
        return self.get_response(request)
