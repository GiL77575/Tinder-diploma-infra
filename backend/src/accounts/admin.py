"""Адмінка користувачів (потрібна також для autocomplete_fields в matching/messaging)."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User


@admin.register(User)
class CrushUserAdmin(UserAdmin):
    list_display = ('id', 'email', 'username', 'is_profile_complete', 'is_staff', 'date_joined')
    search_fields = ('email', 'username')
    ordering = ('-date_joined',)
