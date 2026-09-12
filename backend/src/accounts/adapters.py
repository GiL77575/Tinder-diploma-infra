"""Адаптери allauth: Google OAuth, редіректи, прив'язка до існуючих акаунтів."""

import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.account.utils import user_email, user_username
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.urls import reverse

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        user = request.user
        if user.is_authenticated and not user.is_profile_complete:
            return reverse('profile_setup')
        return reverse('app_dashboard')


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        user = sociallogin.user
        if not user or not user.pk:
            return

        verified_emails = [
            address.email
            for address in sociallogin.email_addresses
            if address.verified
        ]
        if user.email:
            verified_emails.append(user.email)

        for email in verified_emails:
            EmailAddress.objects.update_or_create(
                user=user,
                email=email.lower(),
                defaults={'verified': True, 'primary': True},
            )

    def save_user(self, request, sociallogin, form=None):
        user = sociallogin.user
        if user and not user_username(user) and user_email(user):
            local_part = user_email(user).split('@', 1)[0]
            user_username(user, local_part[:150])
        return super().save_user(request, sociallogin, form=form)

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
