"""Маршрути профілю: перегляд, редагування, перша анкета."""

from django.urls import path

from profiles.views import edit_view, me_view, setup_view

urlpatterns = [
    path('', me_view, name='profile_me'),
    path('edit/', edit_view, name='profile_edit'),
    path('setup/', setup_view, name='profile_setup'),
]
