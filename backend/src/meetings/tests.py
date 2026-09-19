"""Тести функціоналу зустрічей (BFF)."""

import json
from datetime import timedelta

from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from matching.tests import make_user_with_profile
from meetings.models import MeetingParticipant, MeetingStatus
from meetings.services import (
    MeetingError,
    cancel_meeting,
    create_meeting,
    join_meeting,
    leave_meeting,
    update_meeting,
)
from messaging.models import Conversation
from messaging.services import create_message, is_participant


def _future_starts_at(hours=24):
    return timezone.now() + timedelta(hours=hours)


def _create_meeting(user, **overrides):
    data = {
        'title': 'Кава',
        'location': 'Київ, центр',
        'description': 'Зустрінемось на каву',
        'starts_at': _future_starts_at(),
    }
    data.update(overrides)
    return create_meeting(user, **data)


class MeetingCreateTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-m@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-m@example.com', 'Боб')

    def test_create_meeting_makes_creator_participant_and_conversation(self):
        meeting = _create_meeting(self.alice)
        self.assertEqual(meeting.status, MeetingStatus.ACTIVE)
        self.assertTrue(
            MeetingParticipant.objects.filter(meeting=meeting, user=self.alice).exists(),
        )
        self.assertTrue(Conversation.objects.filter(meeting=meeting).exists())
        conversation = meeting.conversation
        self.assertIsNone(conversation.match_id)
        self.assertTrue(is_participant(self.alice, conversation))

    def test_second_active_meeting_forbidden(self):
        _create_meeting(self.alice)
        with self.assertRaises(MeetingError):
            _create_meeting(self.alice, title='Кіно')

    def test_create_after_cancel(self):
        meeting = _create_meeting(self.alice)
        cancel_meeting(self.alice, meeting)
        new_meeting = _create_meeting(self.alice, title='Виставка')
        self.assertEqual(new_meeting.status, MeetingStatus.ACTIVE)

    def test_create_after_completed(self):
        meeting = _create_meeting(self.alice)
        meeting.starts_at = timezone.now() - timedelta(hours=1)
        meeting.save(update_fields=['starts_at'])
        meeting.ensure_completed_if_due()
        self.assertEqual(meeting.status, MeetingStatus.COMPLETED)
        new_meeting = _create_meeting(self.alice, title='Прогулянка')
        self.assertEqual(new_meeting.status, MeetingStatus.ACTIVE)

    def test_past_starts_at_rejected(self):
        with self.assertRaises(MeetingError):
            _create_meeting(self.alice, starts_at=timezone.now() - timedelta(hours=1))


class MeetingJoinLeaveTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-j@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-j@example.com', 'Боб')
        self.carol = make_user_with_profile('carol-j@example.com', 'Кароліна')
        self.meeting = _create_meeting(self.alice)

    def test_join_without_like_or_match(self):
        join_meeting(self.bob, self.meeting)
        self.assertTrue(
            MeetingParticipant.objects.filter(meeting=self.meeting, user=self.bob).exists(),
        )
        self.assertTrue(is_participant(self.bob, self.meeting.conversation))

    def test_repeat_join_forbidden(self):
        join_meeting(self.bob, self.meeting)
        with self.assertRaises(MeetingError):
            join_meeting(self.bob, self.meeting)

    def test_leave_removes_access(self):
        join_meeting(self.bob, self.meeting)
        leave_meeting(self.bob, self.meeting)
        self.assertFalse(
            MeetingParticipant.objects.filter(meeting=self.meeting, user=self.bob).exists(),
        )
        self.assertFalse(is_participant(self.bob, self.meeting.conversation))

    def test_creator_cannot_leave(self):
        with self.assertRaises(MeetingError):
            leave_meeting(self.alice, self.meeting)


class MeetingEditCancelTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-e@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-e@example.com', 'Боб')
        self.meeting = _create_meeting(self.alice)

    def test_creator_can_edit(self):
        new_start = _future_starts_at(48)
        updated = update_meeting(
            self.alice,
            self.meeting,
            title='Кіно',
            location='Планета кіно',
            description='Новий фільм',
            starts_at=new_start,
        )
        self.assertEqual(updated.title, 'Кіно')
        self.assertEqual(updated.location, 'Планета кіно')

    def test_non_creator_cannot_edit(self):
        with self.assertRaises(MeetingError) as ctx:
            update_meeting(
                self.bob,
                self.meeting,
                title='Хак',
                location='X',
                description='Y',
                starts_at=_future_starts_at(),
            )
        self.assertEqual(ctx.exception.status, 403)

    def test_creator_can_cancel(self):
        cancel_meeting(self.alice, self.meeting)
        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, MeetingStatus.CANCELLED)
        self.assertFalse(self.meeting.is_chat_open)

    def test_non_creator_cannot_cancel(self):
        with self.assertRaises(MeetingError) as ctx:
            cancel_meeting(self.bob, self.meeting)
        self.assertEqual(ctx.exception.status, 403)


class MeetingChatAccessTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-c@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-c@example.com', 'Боб')
        self.carol = make_user_with_profile('carol-c@example.com', 'Кароліна')
        self.meeting = _create_meeting(self.alice)
        join_meeting(self.bob, self.meeting)
        self.conversation = self.meeting.conversation

    def test_participant_can_send_message(self):
        message = create_message(self.conversation, self.bob, 'Привіт усім')
        self.assertEqual(message.text, 'Привіт усім')

    def test_non_participant_is_not_participant(self):
        self.assertFalse(is_participant(self.carol, self.conversation))

    def test_join_after_completed_forbidden(self):
        self.meeting.starts_at = timezone.now() - timedelta(minutes=1)
        self.meeting.save(update_fields=['starts_at'])
        with self.assertRaises(MeetingError):
            join_meeting(self.carol, self.meeting)

    def test_message_forbidden_after_chat_closed(self):
        self.meeting.starts_at = timezone.now() - timedelta(days=3)
        self.meeting.status = MeetingStatus.COMPLETED
        self.meeting.save(update_fields=['starts_at', 'status'])
        with self.assertRaises(ValueError):
            create_message(self.conversation, self.bob, 'Пізно')

    def test_chat_closes_at_is_day_after_meeting(self):
        local = timezone.localtime(self.meeting.starts_at)
        expected_date = (local.date() + timedelta(days=1))
        self.assertEqual(timezone.localtime(self.meeting.chat_closes_at).date(), expected_date)


class MeetingApiTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-api@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-api@example.com', 'Боб')
        self.client = Client()
        self.client.force_login(self.alice)

    def test_create_and_mine_endpoints(self):
        starts = (_future_starts_at()).astimezone(timezone.get_current_timezone())
        response = self.client.post(
            reverse('meeting_create'),
            data=json.dumps({
                'title': 'Концерт',
                'location': 'Палац спорту',
                'description': 'Йдемо разом',
                'date': starts.strftime('%Y-%m-%d'),
                'time': starts.strftime('%H:%M'),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        meeting_id = response.json()['meeting']['id']

        mine = self.client.get(reverse('meeting_mine'))
        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json()['meeting']['id'], meeting_id)

    def test_join_chat_endpoint(self):
        meeting = _create_meeting(self.alice)
        bob_client = Client()
        bob_client.force_login(self.bob)
        join_resp = bob_client.post(reverse('meeting_join', args=[meeting.id]))
        self.assertEqual(join_resp.status_code, 200)
        chat_resp = bob_client.get(reverse('meeting_chat', args=[meeting.id]))
        self.assertEqual(chat_resp.status_code, 200)
        self.assertEqual(chat_resp.json()['conversation_id'], meeting.conversation.id)


@override_settings(
    CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}},
)
class MeetingChatConsumerTests(TransactionTestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice-ws@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob-ws@example.com', 'Боб')
        self.meeting = _create_meeting(self.alice)
        join_meeting(self.bob, self.meeting)
        self.conversation = self.meeting.conversation

    def test_participant_can_connect_and_send(self):
        import asyncio

        from channels.testing import WebsocketCommunicator

        from messaging.consumers import ChatConsumer

        async def scenario():
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f'/ws/chat/{self.conversation.id}/',
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': self.conversation.id},
            }
            communicator.scope['user'] = self.bob
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.send_json_to({'type': 'message', 'text': 'Всім привіт'})
            event = await communicator.receive_json_from()
            self.assertEqual(event['type'], 'message')
            self.assertEqual(event['message']['text'], 'Всім привіт')
            await communicator.disconnect()

        asyncio.run(scenario())

    def test_non_participant_rejected(self):
        import asyncio

        from channels.testing import WebsocketCommunicator

        from messaging.consumers import ChatConsumer

        carol = make_user_with_profile('carol-ws@example.com', 'Кароліна')

        async def scenario():
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f'/ws/chat/{self.conversation.id}/',
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': self.conversation.id},
            }
            communicator.scope['user'] = carol
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4003)
            await communicator.disconnect()

        asyncio.run(scenario())

    def test_closed_chat_rejects_connect(self):
        import asyncio

        from channels.testing import WebsocketCommunicator

        from messaging.consumers import ChatConsumer

        self.meeting.starts_at = timezone.now() - timedelta(days=3)
        self.meeting.status = MeetingStatus.COMPLETED
        self.meeting.save(update_fields=['starts_at', 'status'])

        async def scenario():
            communicator = WebsocketCommunicator(
                ChatConsumer.as_asgi(),
                f'/ws/chat/{self.conversation.id}/',
            )
            communicator.scope['url_route'] = {
                'kwargs': {'conversation_id': self.conversation.id},
            }
            communicator.scope['user'] = self.bob
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4003)
            await communicator.disconnect()

        asyncio.run(scenario())
