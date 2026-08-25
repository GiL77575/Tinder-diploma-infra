"""Тести критичної логіки матчінгу: свайпи, матчі, ізоляція режимів."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matching.models import Like, Match
from matching.services import discover_candidates_queryset, matches_for_user, record_swipe
from messaging.models import Conversation
from profiles.models import Profile, ProfileMode, SearchMode

User = get_user_model()


def make_user_with_profile(email, display_name, is_discoverable=True):
    user = User.objects.create_user(
        username=email.split('@')[0],
        email=email,
        password='StrongPass!1',
        is_profile_complete=True,
    )
    profile = Profile.objects.create(
        user=user,
        display_name=display_name,
        birth_date=date(1998, 5, 12),
        gender='female',
        orientation='straight',
        city='Київ',
        is_discoverable=is_discoverable,
    )
    ProfileMode.objects.create(profile=profile, mode=SearchMode.DATING, bio='Привіт, я тут заради знайомств')
    ProfileMode.objects.create(profile=profile, mode=SearchMode.BFF, bio='Шукаю друзів')
    return user


class RecordSwipeTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob@example.com', 'Боб')

    def test_one_sided_like_does_not_create_match(self):
        _, match = record_swipe(self.alice, self.bob.id, SearchMode.DATING, True)
        self.assertIsNone(match)
        self.assertEqual(Match.objects.count(), 0)

    def test_mutual_like_creates_match_and_conversation(self):
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, True)
        _, match = record_swipe(self.bob, self.alice.id, SearchMode.DATING, True)

        self.assertIsNotNone(match)
        self.assertEqual(Match.objects.count(), 1)
        self.assertTrue(Conversation.objects.filter(match=match).exists())
        # canonical order: менший id завжди user_a
        self.assertLess(match.user_a_id, match.user_b_id)

    def test_dislike_never_creates_match(self):
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, False)
        _, match = record_swipe(self.bob, self.alice.id, SearchMode.DATING, True)
        self.assertIsNone(match)

    def test_cannot_swipe_self(self):
        with self.assertRaises(ValueError):
            record_swipe(self.alice, self.alice.id, SearchMode.DATING, True)

    def test_match_is_isolated_per_mode(self):
        """Взаємний лайк у dating не створює матч у bff і навпаки."""
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, True)
        record_swipe(self.bob, self.alice.id, SearchMode.DATING, True)

        self.assertEqual(matches_for_user(self.alice, SearchMode.DATING).__len__(), 1)
        self.assertEqual(len(matches_for_user(self.alice, SearchMode.BFF)), 0)

    def test_swipe_updates_existing_like_instead_of_duplicating(self):
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, False)
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, True)
        self.assertEqual(Like.objects.filter(from_user=self.alice, to_user=self.bob).count(), 1)
        like = Like.objects.get(from_user=self.alice, to_user=self.bob)
        self.assertTrue(like.is_positive)


class DiscoverCandidatesTests(TestCase):
    def setUp(self):
        self.viewer = make_user_with_profile('viewer@example.com', 'Оля')
        self.candidate = make_user_with_profile('candidate@example.com', 'Ігор')
        self.hidden = make_user_with_profile('hidden@example.com', 'Прихований', is_discoverable=False)

    def test_excludes_self(self):
        ids = list(discover_candidates_queryset(self.viewer, SearchMode.DATING).values_list('user_id', flat=True))
        self.assertNotIn(self.viewer.id, ids)

    def test_excludes_non_discoverable(self):
        ids = list(discover_candidates_queryset(self.viewer, SearchMode.DATING).values_list('user_id', flat=True))
        self.assertNotIn(self.hidden.id, ids)

    def test_excludes_already_swiped(self):
        record_swipe(self.viewer, self.candidate.id, SearchMode.DATING, False)
        ids = list(discover_candidates_queryset(self.viewer, SearchMode.DATING).values_list('user_id', flat=True))
        self.assertNotIn(self.candidate.id, ids)


class LikeViewTests(TestCase):
    def setUp(self):
        self.alice = make_user_with_profile('alice2@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob2@example.com', 'Боб')
        self.client.force_login(self.alice)

    def test_like_requires_login(self):
        self.client.logout()
        response = self.client.post(
            reverse('like_action'),
            data={'to_user_id': self.bob.id, 'mode': 'dating', 'is_positive': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_like_endpoint_creates_match_json(self):
        record_swipe(self.bob, self.alice.id, SearchMode.DATING, True)
        response = self.client.post(
            reverse('like_action'),
            data={'to_user_id': self.bob.id, 'mode': 'dating', 'is_positive': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()['match'])

    def test_matches_list_only_current_user(self):
        record_swipe(self.alice, self.bob.id, SearchMode.DATING, True)
        record_swipe(self.bob, self.alice.id, SearchMode.DATING, True)
        response = self.client.get(reverse('matches_list'), {'mode': 'dating'})
        self.assertEqual(response.status_code, 200)
        matches = response.json()['matches']
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['other_user_id'], self.bob.id)
