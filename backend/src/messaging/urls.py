"""Маршрути чату: список діалогів, історія повідомлень, статуси."""

from django.urls import path

from messaging.views import (
    conversation_delete_message_view,
    conversation_edit_message_view,
    conversation_mark_read_view,
    conversation_messages_view,
    conversation_send_message_view,
    conversation_send_photo_view,
    conversations_list_view,
    open_conversation_view,
)

urlpatterns = [
    path('conversations/', conversations_list_view, name='conversations_list'),
    path('conversations/open/', open_conversation_view, name='conversation_open'),
    path(
        'conversations/<int:conversation_id>/messages/',
        conversation_messages_view,
        name='conversation_messages',
    ),
    path(
        'conversations/<int:conversation_id>/send/',
        conversation_send_message_view,
        name='conversation_send',
    ),
    path(
        'conversations/<int:conversation_id>/photo/',
        conversation_send_photo_view,
        name='conversation_send_photo',
    ),
    path(
        'conversations/<int:conversation_id>/read/',
        conversation_mark_read_view,
        name='conversation_read',
    ),
    path(
        'conversations/<int:conversation_id>/messages/<int:message_id>/edit/',
        conversation_edit_message_view,
        name='conversation_edit_message',
    ),
    path(
        'conversations/<int:conversation_id>/messages/<int:message_id>/delete/',
        conversation_delete_message_view,
        name='conversation_delete_message',
    ),
]
