"""Тести критичної логіки матчінгу: свайпи, матчі, ізоляція режимів."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matching.models import Like, Match
from matching.services import discover_candidates_queryset, matches_for_user, next_candidate, record_swipe
from messaging.models import Conversation
from profiles.models import (
    BffLookingFor,
    HobbyLevel,
    LanguageLevel,
    Profile,
    ProfileMode,
    ProfileTag,
    SearchMode,
    Tag,
    TagCategory,
)

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


class UnmatchTests(TestCase):
    """Анметч прибирає метч і діалог у обох сторін, окремо для кожного режиму."""

    def setUp(self):
        self.alice = make_user_with_profile('alice.unmatch@example.com', 'Аліса')
        self.bob = make_user_with_profile('bob.unmatch@example.com', 'Боб')
        self.stranger = make_user_with_profile('stranger.unmatch@example.com', 'Чужий')

    def _make_match(self, mode):
        record_swipe(self.alice, self.bob.id, mode, True)
        _, match = record_swipe(self.bob, self.alice.id, mode, True)
        return match

    def test_unmatch_removes_match_and_conversation_for_both(self):
        match = self._make_match(SearchMode.DATING)
        conversation = Conversation.objects.get(match=match)
        self.client.force_login(self.alice)
        response = self.client.post(reverse('unmatch', args=[match.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Match.objects.filter(pk=match.id).exists())
        self.assertFalse(Conversation.objects.filter(pk=conversation.id).exists())
        self.assertEqual(len(matches_for_user(self.alice, SearchMode.DATING)), 0)
        self.assertEqual(len(matches_for_user(self.bob, SearchMode.DATING)), 0)

    def test_unmatch_works_in_bff_mode(self):
        match = self._make_match(SearchMode.BFF)
        self.client.force_login(self.bob)
        response = self.client.post(reverse('unmatch', args=[match.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(matches_for_user(self.alice, SearchMode.BFF)), 0)
        self.assertEqual(len(matches_for_user(self.bob, SearchMode.BFF)), 0)

    def test_stranger_cannot_unmatch(self):
        match = self._make_match(SearchMode.DATING)
        self.client.force_login(self.stranger)
        response = self.client.post(reverse('unmatch', args=[match.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Match.objects.filter(pk=match.id).exists())

    def test_unmatch_does_not_touch_other_mode(self):
        dating = self._make_match(SearchMode.DATING)
        bff = self._make_match(SearchMode.BFF)
        self.client.force_login(self.alice)
        self.client.post(reverse('unmatch', args=[dating.id]))
        self.assertFalse(Match.objects.filter(pk=dating.id).exists())
        self.assertTrue(Match.objects.filter(pk=bff.id).exists())


class DatingFilterTests(TestCase):
    """Dating: те саме місто, вік у діапазоні, 2+ спільні інтереси."""

    def setUp(self):
        self.book = Tag.objects.create(name='Тест-книги', category=TagCategory.INTEREST)
        self.hiking = Tag.objects.create(name='Тест-походи', category=TagCategory.INTEREST)
        self.chess = Tag.objects.create(name='Тест-шахи', category=TagCategory.INTEREST)

        self.viewer = make_user_with_profile('viewer.dating@example.com', 'Оля')
        self.viewer.profile.city = 'Київ'
        self.viewer.profile.save()
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            min_age=20, max_age=40,
        )
        for tag in (self.book, self.hiking):
            ProfileTag.objects.create(profile=self.viewer.profile, tag=tag, mode=SearchMode.DATING)

    def _make_candidate(self, email, name, city='Київ', tags=()):
        user = make_user_with_profile(email, name)
        user.profile.city = city
        user.profile.save()
        for tag in tags:
            ProfileTag.objects.create(profile=user.profile, tag=tag, mode=SearchMode.DATING)
        return user

    def test_matches_same_city_age_and_two_shared_interests(self):
        candidate = self._make_candidate(
            'match.dating@example.com', 'Ігор', tags=(self.book, self.hiking),
        )
        profile, shared = next_candidate(self.viewer, SearchMode.DATING)
        self.assertEqual(profile.user_id, candidate.id)
        self.assertCountEqual(shared['interests'], [self.book.id, self.hiking.id])

    def test_excludes_different_city(self):
        self._make_candidate(
            'other.city@example.com', 'Марко', city='Львів', tags=(self.book, self.hiking),
        )
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(profile)

    def test_excludes_age_outside_range(self):
        candidate = self._make_candidate(
            'too.old@example.com', 'Петро', tags=(self.book, self.hiking),
        )
        candidate.profile.birth_date = date(1960, 1, 1)
        candidate.profile.save()
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(profile)

    def test_excludes_less_than_two_shared_interests(self):
        self._make_candidate(
            'one.tag@example.com', 'Тарас', tags=(self.book, self.chess),
        )
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(profile)


class BffFilterTests(TestCase):
    """BFF: та сама тема пошуку, спільне хобі й мова з тим самим рівнем."""

    def setUp(self):
        self.english = Tag.objects.create(name='Тест-англійська', category=TagCategory.LANGUAGE)
        self.chess_hobby = Tag.objects.create(name='Тест-шахи-хобі', category=TagCategory.HOBBY)

        self.viewer = make_user_with_profile('viewer.bff@example.com', 'Настя')
        self.viewer.profile.city = 'Київ'
        self.viewer.profile.save()
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.BFF).update(
            looking_for=BffLookingFor.LANGUAGE,
        )
        ProfileTag.objects.create(
            profile=self.viewer.profile, tag=self.english, mode=SearchMode.BFF, level=LanguageLevel.B1,
        )
        ProfileTag.objects.create(
            profile=self.viewer.profile, tag=self.chess_hobby, mode=SearchMode.BFF, level=HobbyLevel.NOVICE,
        )

    def _make_candidate(self, email, name, city, looking_for, language_level, hobby_level):
        user = make_user_with_profile(email, name)
        user.profile.city = city
        user.profile.save()
        ProfileMode.objects.filter(profile=user.profile, mode=SearchMode.BFF).update(looking_for=looking_for)
        ProfileTag.objects.create(
            profile=user.profile, tag=self.english, mode=SearchMode.BFF, level=language_level,
        )
        ProfileTag.objects.create(
            profile=user.profile, tag=self.chess_hobby, mode=SearchMode.BFF, level=hobby_level,
        )
        return user

    def test_matches_regardless_of_city_when_topic_language_and_level_match(self):
        candidate = self._make_candidate(
            'match.bff@example.com', 'Олег', city='Одеса',
            looking_for=BffLookingFor.LANGUAGE,
            language_level=LanguageLevel.B1, hobby_level=HobbyLevel.NOVICE,
        )
        profile, shared = next_candidate(self.viewer, SearchMode.BFF)
        self.assertEqual(profile.user_id, candidate.id)
        self.assertIn(self.english.id, shared['languages'])
        self.assertIn(self.chess_hobby.id, shared['hobbies'])

    def test_excludes_different_topic(self):
        self._make_candidate(
            'diff.topic@example.com', 'Іван', city='Київ',
            looking_for=BffLookingFor.TRAVEL,
            language_level=LanguageLevel.B1, hobby_level=HobbyLevel.NOVICE,
        )
        profile, _ = next_candidate(self.viewer, SearchMode.BFF)
        self.assertIsNone(profile)

    def test_excludes_different_language_level(self):
        self._make_candidate(
            'diff.level@example.com', 'Ліна', city='Київ',
            looking_for=BffLookingFor.LANGUAGE,
            language_level=LanguageLevel.C1, hobby_level=HobbyLevel.NOVICE,
        )
        profile, _ = next_candidate(self.viewer, SearchMode.BFF)
        self.assertIsNone(profile)

    def test_excludes_different_hobby_level(self):
        self._make_candidate(
            'diff.hobby.level@example.com', 'Марта', city='Київ',
            looking_for=BffLookingFor.LANGUAGE,
            language_level=LanguageLevel.B1, hobby_level=HobbyLevel.PRO,
        )
        profile, _ = next_candidate(self.viewer, SearchMode.BFF)
        self.assertIsNone(profile)
