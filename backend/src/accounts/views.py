"""Вхід, реєстрація та лендинг. Профіль — у додатку profiles."""

import re

from allauth.socialaccount.models import SocialApp
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect, render

User = get_user_model()


def _google_oauth_enabled():
    """Чи налаштований Google OAuth у базі (кнопка Gmail)."""
    return SocialApp.objects.filter(provider='google').exists()


def _render_auth(request, template, **extra):
    """Рендер login/register; extra — збережені поля форми після помилки."""
    return render(
        request,
        template,
        {'google_oauth_enabled': _google_oauth_enabled(), **extra},
    )


def redirect_after_auth(user):
    """Після входу: анкета, якщо профіль порожній, інакше головний екран."""
    if not user.is_profile_complete:
        return redirect('profile_setup')
    return redirect('app_dashboard')


def home_view(request):
    """Лендинг crush; незаповнений профіль одразу на анкету."""
    if request.user.is_authenticated and not request.user.is_profile_complete:
        return redirect('profile_setup')
    return render(request, 'home.html')


INFO_PAGES = {
    'about': 'about.html',
    'safety': 'safety.html',
    'support': 'support.html',
}


def info_page_view(request, slug):
    """Інфосторінки: Про нас, Безпека, Підтримка."""
    template = INFO_PAGES.get(slug)
    if template is None:
        raise Http404('Сторінку не знайдено')
    return render(request, template)


def login_view(request):
    """Показує форму входу. Завершений профіль з /login/ іде в застосунок."""
    if request.method == 'GET' and request.user.is_authenticated:
        if request.user.is_profile_complete:
            return redirect('app_dashboard')
        logout(request)

    posted_username = ''
    if request.method == 'POST':
        if request.user.is_authenticated:
            logout(request)
        posted_username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=posted_username, password=password)
        if user is not None:
            login(request, user)
            return redirect_after_auth(user)
        messages.error(request, 'Невірний логін або пароль')

    return _render_auth(request, 'login.html', username=posted_username)


def logout_view(request):
    """Вихід із сесії."""
    logout(request)
    return redirect('home')


def _registration_error(username, email, password, password_confirm):
    """Текст помилки реєстрації або None, якщо дані валідні."""
    if not username:
        return 'Поле "Логін" не може бути порожнім.'
    if not email:
        return 'Поле "Email" не може бути порожнім.'
    if User.objects.filter(username__iexact=username).exists():
        return 'Помилка у полі "Логін": Користувач з таким логіном вже існує.'
    if User.objects.filter(email__iexact=email).exists():
        return 'Помилка у полі "Email": Вказана адреса вже використовується.'
    if password != password_confirm:
        return 'Помилка у полі "Підтвердження пароля": Паролі не збігаються.'
    if len(password) < 8:
        return 'Помилка у полі "Пароль": Довжина має бути не менше 8 символів.'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return (
            'Помилка у полі "Пароль": Пароль повинен містити '
            'хоча б один спеціальний символ (!@#$%^&* тощо).'
        )
    return None


def register_view(request):
    """Реєстрація email/пароль, далі — анкета профілю."""
    if request.user.is_authenticated:
        return redirect_after_auth(request.user)

    username = ''
    email = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        error = _registration_error(username, email, password, password_confirm)
        if error:
            messages.error(request, error)
            return _render_auth(
                request,
                'register.html',
                username=username,
                email=email,
            )

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
            EmailAddress.objects.update_or_create(
                user=user,
                email=email.lower(),
                defaults={'verified': True, 'primary': True},
            )
        except IntegrityError:
            messages.error(request, 'Користувач з таким логіном або email вже існує.')
            return _render_auth(
                request,
                'register.html',
                username=username,
                email=email,
            )

        login(request, user, backend='accounts.backends.EmailOrUsernameModelBackend')
        return redirect_after_auth(user)

    return _render_auth(request, 'register.html', username=username, email=email)
