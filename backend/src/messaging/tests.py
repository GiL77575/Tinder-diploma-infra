"""Тести чату: доступ до діалогів, повідомлення, unread, WebSocket."""

import asyncio

from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from matching.services import record_swipe
from matching.tests import make_user_with_profile
from messaging.models import Conversation, Message
from messaging.services import conversations_for_user, mark_conversation_read
from profiles.models import SearchMode


def make_match(user_a, user_b, mode=SearchMode.DATING):
    record_swipe(user_a, user_b.id, mode, True)
    _, match = record_swipe(user_b, user_a.id, mode, True)
    return match


class ConversationAccessTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice3@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob3@example.com', 'Боб')
        self.stranger = make_user_with_profile('stranger@example.com', 'Чужий')
        self.match = make_match(self.alice, self.bob)
        self.conversation = Conversation.objects.get(match=self.match)

    def test_participant_can_read_messages(self):
        self.client.force_login(self.alice)
        response = self.client.get(
            reverse('conversation_messages', args=[self.conversation.id]),
        )
        self.assertEqual(response.status_code, 200)

    def test_stranger_cannot_read_messages(self):
        self.client.force_login(self.stranger)
        response = self.client.get(
            reverse('conversation_messages', args=[self.conversation.id]),
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_cannot_read_messages(self):
        response = self.client.get(
            reverse('conversation_messages', args=[self.conversation.id]),
        )
        self.assertEqual(response.status_code, 302)

    def test_send_message_sets_sender_to_authenticated_user(self):
        self.client.force_login(self.bob)
        response = self.client.post(
            reverse('conversation_send', args=[self.conversation.id]),
            data={'text': 'Привіт!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        message = Message.objects.get(conversation=self.conversation)
        self.assertEqual(message.sender_id, self.bob.id)
        self.assertEqual(message.text, 'Привіт!')

    def test_stranger_cannot_send_message(self):
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse('conversation_send', args=[self.conversation.id]),
            data={'text': 'Хочу втрутитись'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Message.objects.filter(conversation=self.conversation).exists())


class DialogListOrderingTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice4@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob4@example.com', 'Боб')
        self.carl = make_user_with_profile('carl4@example.com', 'Карл')
        self.match_bob = make_match(self.alice, self.bob)
        self.match_carl = make_match(self.alice, self.carl)
        self.conv_bob = Conversation.objects.get(match=self.match_bob)
        self.conv_carl = Conversation.objects.get(match=self.match_carl)

    def test_unread_dialog_is_sorted_first(self):
        Message.objects.create(conversation=self.conv_bob, sender=self.alice, text='mine, no unread for me')
        Message.objects.create(conversation=self.conv_carl, sender=self.carl, text='unread from carl')

        items = conversations_for_user(self.alice, SearchMode.DATING)
        self.assertEqual(items[0]['other_user_id'], self.carl.id)
        self.assertEqual(items[0]['unread_count'], 1)

    def test_mark_read_clears_unread_count(self):
        Message.objects.create(conversation=self.conv_bob, sender=self.bob, text='hi')
        mark_conversation_read(self.conv_bob, self.alice)
        items = conversations_for_user(self.alice, SearchMode.DATING)
        bob_item = next(i for i in items if i['other_user_id'] == self.bob.id)
        self.assertEqual(bob_item['unread_count'], 0)

    def test_modes_are_isolated_in_dialog_list(self):
        friend_match = make_match(self.alice, self.bob, mode=SearchMode.BFF)
        Conversation.objects.get(match=friend_match)
        dating_items = conversations_for_user(self.alice, SearchMode.DATING)
        bff_items = conversations_for_user(self.alice, SearchMode.BFF)
        self.assertEqual(len(bff_items), 1)
        self.assertEqual(len(dating_items), 2)


class ChatConsumerTests(TransactionTestCase):
    """WebSocket: доступ, надсилання/отримання повідомлень у реальному часі.

    TransactionTestCase (а не TestCase) — консюмер працює в окремому потоці
    через database_sync_to_async і не бачить дані з незакомічених транзакцій.
    """

    def setUp(self):
        self.alice = make_user_with_profile('alice5@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob5@example.com', 'Боб')
        self.stranger = make_user_with_profile('stranger5@example.com', 'Чужий')
        self.match = make_match(self.alice, self.bob)
        self.conversation = Conversation.objects.get(match=self.match)

    def test_stranger_is_rejected(self):
        from channels.testing import WebsocketCommunicator

        from messaging.consumers import ChatConsumer

        async def scenario():
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(), f'/ws/chat/{self.conversation.id}/',
            )
            communicator.scope['url_route'] = {'kwargs': {'conversation_id': self.conversation.id}}
            communicator.scope['user'] = self.stranger
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        asyncio.run(scenario())

    def test_participant_can_send_and_receive_message(self):
        from channels.testing import WebsocketCommunicator

        from messaging.consumers import ChatConsumer

        async def scenario():
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(), f'/ws/chat/{self.conversation.id}/',
            )
            communicator.scope['url_route'] = {'kwargs': {'conversation_id': self.conversation.id}}
            communicator.scope['user'] = self.alice
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({'type': 'message', 'text': 'Привіт, Боб!'})
            response = await communicator.receive_json_from()
            self.assertEqual(response['type'], 'message')
            self.assertEqual(response['message']['text'], 'Привіт, Боб!')
            self.assertEqual(response['message']['sender_id'], self.alice.id)

            await communicator.disconnect()

        asyncio.run(scenario())

        self.assertTrue(Message.objects.filter(conversation=self.conversation, text='Привіт, Боб!').exists())
