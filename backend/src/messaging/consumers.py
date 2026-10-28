"""WebSocket-споживачі чату: відкритий діалог і особистий inbox."""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from messaging.models import Conversation
from messaging.services import (
    can_access_conversation,
    create_message,
    is_participant,
    mark_conversation_read,
    message_preview,
    participant_user_ids,
    serialize_message,
    serialize_reaction_groups,
    set_message_reaction,
)


class ChatConsumer(AsyncWebsocketConsumer):
    """Чат одного діалогу: приймає/розсилає повідомлення, стежить за доступом."""

    async def connect(self):
        user = self.scope.get('user')
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']

        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        conversation = await self._get_conversation()
        if conversation is None or not await self._user_can_access(user, conversation):
            await self.close(code=4003)
            return

        self.user = user
        self.conversation_group = f'conversation_{self.conversation_id}'

        await self.channel_layer.group_add(self.conversation_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        conversation_group = getattr(self, 'conversation_group', None)
        if conversation_group:
            await self.channel_layer.group_discard(conversation_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or '{}')
        except json.JSONDecodeError:
            await self._send_error('Невірний формат повідомлення.')
            return

        action = payload.get('type', 'message')

        if action == 'message':
            await self._handle_send_message(payload.get('text', ''))
        elif action == 'read':
            await self._handle_mark_read()
        elif action == 'react':
            await self._handle_react(payload.get('message_id'), payload.get('emoji', ''))
        else:
            await self._send_error(f'Невідомий тип події: {action}')

    async def _handle_send_message(self, text):
        try:
            message_data, recipient_ids, conversation_meta = await self._create_message(text)
        except ValueError as exc:
            await self._send_error(str(exc))
            return

        await self.channel_layer.group_send(
            self.conversation_group,
            {
                'type': 'chat.message',
                'message': message_data,
                'mode': conversation_meta['mode'],
            },
        )

        dialog_event = {
            'type': 'dialog.update',
            'conversation_id': int(self.conversation_id),
            'preview': message_preview(message_data['text'], message_data.get('image_url')),
            'time_label': message_data['time_label'],
            'sender_id': message_data['sender_id'],
            'mode': conversation_meta['mode'],
        }
        for user_id in recipient_ids:
            await self.channel_layer.group_send(f'user_{user_id}', dialog_event)

    async def _handle_mark_read(self):
        updated = await self._mark_read()
        if updated:
            await self.channel_layer.group_send(
                self.conversation_group,
                {
                    'type': 'chat.read',
                    'conversation_id': int(self.conversation_id),
                    'reader_id': self.user.id,
                },
            )

    async def _handle_react(self, message_id, emoji):
        try:
            groups, msg_id = await self._set_reaction(message_id, emoji)
        except ValueError as exc:
            await self._send_error(str(exc))
            return
        await self.channel_layer.group_send(
            self.conversation_group,
            {
                'type': 'chat.reactions_updated',
                'message_id': msg_id,
                'conversation_id': int(self.conversation_id),
                'reactions': groups,
            },
        )

    async def _send_error(self, message):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    def _message_for_socket(self, message):
        """is_mine і mine-реакції — з погляду цього з'єднання, не автора події."""
        payload = dict(message)
        payload['is_mine'] = payload.get('sender_id') == self.user.id
        reactions = []
        for item in payload.get('reactions') or []:
            user_ids = item.get('user_ids') or []
            reactions.append({
                'emoji': item['emoji'],
                'count': item['count'],
                'mine': self.user.id in user_ids if user_ids else bool(item.get('mine')),
            })
        payload['reactions'] = reactions
        return payload

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': self._message_for_socket(event['message']),
            'mode': event.get('mode'),
        }))
        if event['message'].get('sender_id') == self.user.id:
            return
        updated = await self._mark_read()
        if updated:
            await self.channel_layer.group_send(
                self.conversation_group,
                {
                    'type': 'chat.read',
                    'conversation_id': int(self.conversation_id),
                    'reader_id': self.user.id,
                },
            )

    async def chat_read(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read',
            'conversation_id': event['conversation_id'],
            'reader_id': event['reader_id'],
        }))

    async def chat_message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message': self._message_for_socket(event['message']),
            'mode': event.get('mode'),
        }))

    async def chat_message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id'],
            'conversation_id': event['conversation_id'],
        }))

    async def chat_reactions_updated(self, event):
        viewer_id = self.user.id
        reactions = [
            {
                'emoji': group['emoji'],
                'count': group['count'],
                'mine': viewer_id in group.get('user_ids', []),
            }
            for group in event.get('reactions') or []
        ]
        await self.send(text_data=json.dumps({
            'type': 'reactions_updated',
            'message_id': event['message_id'],
            'conversation_id': event['conversation_id'],
            'reactions': reactions,
        }))

    @database_sync_to_async
    def _get_conversation(self):
        return (
            Conversation.objects
            .select_related(
                'match', 'match__user_a', 'match__user_b',
                'meeting',
            )
            .filter(pk=self.conversation_id)
            .first()
        )

    @database_sync_to_async
    def _user_can_access(self, user, conversation):
        return can_access_conversation(user, conversation)

    @database_sync_to_async
    def _create_message(self, text):
        conversation = (
            Conversation.objects
            .select_related(
                'match', 'match__user_a', 'match__user_b',
                'meeting',
            )
            .get(pk=self.conversation_id)
        )
        if not is_participant(self.user, conversation):
            raise ValueError('Немає доступу до чату.')
        message = create_message(conversation, self.user, text)
        return (
            serialize_message(message, self.user),
            participant_user_ids(conversation),
            {'mode': conversation.mode},
        )

    @database_sync_to_async
    def _mark_read(self):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        return mark_conversation_read(conversation, self.user)

    @database_sync_to_async
    def _set_reaction(self, message_id, emoji):
        conversation = (
            Conversation.objects
            .select_related(
                'match', 'match__user_a', 'match__user_b',
                'meeting',
            )
            .get(pk=self.conversation_id)
        )
        if not is_participant(self.user, conversation):
            raise ValueError('Немає доступу до чату.')
        message = set_message_reaction(conversation, self.user, message_id, emoji)
        return serialize_reaction_groups(message), message.id


class InboxConsumer(AsyncWebsocketConsumer):
    """Особистий канал користувача для оновлення списку діалогів."""

    async def connect(self):
        user = self.scope.get('user')
        if user is None or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        self.personal_group = f'user_{user.id}'

        await self.channel_layer.group_add(self.personal_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        personal_group = getattr(self, 'personal_group', None)
        if personal_group:
            await self.channel_layer.group_discard(personal_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        pass

    async def dialog_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'dialog_update',
            'conversation_id': event['conversation_id'],
            'preview': event['preview'],
            'time_label': event['time_label'],
            'sender_id': event['sender_id'],
            'mode': event['mode'],
        }))

    async def match_removed(self, event):
        """Друга сторона анметчнула — прибрати метч і діалог у цьому клієнті."""
        await self.send(text_data=json.dumps({
            'type': 'match_removed',
            'conversation_id': event.get('conversation_id'),
            'mode': event.get('mode'),
        }))
