"""Адаптер allauth socialaccount: логування помилок Google OAuth."""

import logging

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

logger = logging.getLogger(__name__)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def on_authentication_error(
        self,
        request,
        provider,
        error=None,
        exception=None,
        extra_context=None,
    ):
        logger.error(
            "Social auth failed: provider=%s error=%s exception=%s extra=%s",
            getattr(provider, "id", provider),
            error,
            exception,
            extra_context,
        )
        return super().on_authentication_error(
            request,
            provider,
            error=error,
            exception=exception,
            extra_context=extra_context,
        )
