import re
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from accounts.models import User

User = get_user_model()


def home_view(request):
    """Головна сторінка-лендинг crush."""
    return render(request, 'home.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        
        # Аутентифікація (перевірка логіна та пароля)
        user = authenticate(request, username=username_or_email, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Невірний логін або пароль')
            
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not username:
            messages.error(request, 'Поле "Логін" не може бути порожнім.')
            return render(request, 'register.html')

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, 'Помилка у полі "Логін": Користувач з таким логіном вже існує.')
            return render(request, 'register.html')

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Помилка у полі "Email": Вказана адреса вже використовується.')
            return render(request, 'register.html')

        if password != password_confirm:
            messages.error(request, 'Помилка у полі "Підтвердження пароля": Паролі не збігаються.')
            return render(request, 'register.html')

        if len(password) < 8:
            messages.error(request, 'Помилка у полі "Пароль": Довжина має бути не менше 8 символів.')
            return render(request, 'register.html')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, 'Помилка у полі "Пароль": Пароль повинен містити хоча б один спеціальний символ (!@#$%^&* тощо).')
            return render(request, 'register.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        login(request, user, backend='accounts.backends.EmailOrUsernameModelBackend')
        return redirect('home')

    return render(request, 'register.html')