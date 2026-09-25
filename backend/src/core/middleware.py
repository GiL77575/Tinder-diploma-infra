"""Middleware for reverse-proxy / public host fixes."""

from django.conf import settings


class PublicHostMiddleware:
    """Force the public hostname so OAuth callbacks never use a private IP.

    When nginx (or another proxy) forwards X-Forwarded-Host / Host as the
    backend address (e.g. 10.239.88.223), Google rejects the redirect_uri.
    Set PUBLIC_HOST=crush.pp.ua to pin the external domain.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.public_host = getattr(settings, 'PUBLIC_HOST', '').strip()

    def __call__(self, request):
        if self.public_host:
            request.META['HTTP_HOST'] = self.public_host
            request.META['HTTP_X_FORWARDED_HOST'] = self.public_host
        return self.get_response(request)
