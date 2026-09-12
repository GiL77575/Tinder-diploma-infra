"""Маршрути головного екрану: дашборд, свайпи, метчі."""

from django.urls import path

from matching.views import (
    dashboard_view,
    discover_next_view,
    like_view,
    matches_list_view,
    unmatch_view,
)

urlpatterns = [
    path('', dashboard_view, name='app_dashboard'),
    path('discover/', discover_next_view, name='discover_next'),
    path('like/', like_view, name='like_action'),
    path('matches/', matches_list_view, name='matches_list'),
    path('matches/<int:match_id>/unmatch/', unmatch_view, name='unmatch'),
    path('unmatch/<int:match_id>/', unmatch_view, name='unmatch_alt'),
]
