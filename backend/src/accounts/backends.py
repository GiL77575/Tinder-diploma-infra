from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Дозволяє користувачу входити в систему, використовуючи email або username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        try:
            # Шукаємо користувача за username або за email (без урахування регістру)
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # Якщо з таким email є кілька акаунтів, беремо першого
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None