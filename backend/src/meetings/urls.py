"""Маршрути зустрічей."""

from django.urls import path

from meetings.views import (
    meeting_cancel_view,
    meeting_chat_view,
    meeting_create_view,
    meeting_detail_view,
    meeting_edit_view,
    meeting_join_view,
    meeting_leave_view,
    meeting_mine_view,
)

urlpatterns = [
    path('meetings/mine/', meeting_mine_view, name='meeting_mine'),
    path('meetings/create/', meeting_create_view, name='meeting_create'),
    path('meetings/<int:meeting_id>/', meeting_detail_view, name='meeting_detail'),
    path('meetings/<int:meeting_id>/edit/', meeting_edit_view, name='meeting_edit'),
    path('meetings/<int:meeting_id>/cancel/', meeting_cancel_view, name='meeting_cancel'),
    path('meetings/<int:meeting_id>/join/', meeting_join_view, name='meeting_join'),
    path('meetings/<int:meeting_id>/leave/', meeting_leave_view, name='meeting_leave'),
    path('meetings/<int:meeting_id>/chat/', meeting_chat_view, name='meeting_chat'),
]
