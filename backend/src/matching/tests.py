"""Тести критичної логіки матчінгу: свайпи, матчі, ізоляція режимів."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from matching.models import Like, Match
from matching.services import (
    count_strict_candidates,
    discover_candidates_queryset,
    has_similar_candidates,
    matches_for_user,
    next_candidate,
    record_swipe,
)
from messaging.models import Conversation
from profiles.models import (
    AgePreference,
    BffLookingFor,
    HobbyLevel,
    LanguageLevel,
    LookingFor,
    Orientation,
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

    def test_no_limit_ignores_min_max_age(self):
        """«Без обмежень» показує кандидатів поза збереженим min/max."""
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            age_preference=AgePreference.NO_LIMIT,
            min_age=20,
            max_age=40,
        )
        candidate = self._make_candidate(
            'no.limit@example.com', 'Олег', tags=(self.book, self.hiking),
        )
        candidate.profile.birth_date = date(1960, 1, 1)
        candidate.profile.save()
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertEqual(profile.user_id, candidate.id)

    def test_peers_keeps_near_viewer_age(self):
        """«Однолітки» лишає кандидатів ±3 роки від віку переглядача."""
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            age_preference=AgePreference.PEERS,
            min_age=18,
            max_age=99,
        )
        # viewer birth_date = 1998-05-12 → ~28 у 2026; ±3 → ~25–31
        peer = self._make_candidate(
            'peer.ok@example.com', 'Катя', tags=(self.book, self.hiking),
        )
        peer.profile.birth_date = date(1999, 6, 1)
        peer.profile.save()
        too_young = self._make_candidate(
            'peer.young@example.com', 'Ліза', tags=(self.book, self.hiking),
        )
        too_young.profile.birth_date = date(2010, 1, 1)
        too_young.profile.save()

        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertEqual(profile.user_id, peer.id)

    def test_excludes_less_than_two_shared_interests(self):
        self._make_candidate(
            'one.tag@example.com', 'Тарас', tags=(self.book, self.chess),
        )
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(profile)

    def test_looking_for_male_excludes_women(self):
        """«Шукаю хлопця» не показує жінок навіть за містом, віком і інтересами."""
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            looking_for=LookingFor.MALE,
        )
        woman = self._make_candidate(
            'same.gender@example.com', 'Іра', tags=(self.book, self.hiking),
        )
        man = self._make_candidate(
            'wanted.gender@example.com', 'Ігор', tags=(self.book, self.hiking),
        )
        man.profile.gender = 'male'
        man.profile.save()
        profile, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertEqual(profile.user_id, man.id)
        self.assertNotEqual(profile.user_id, woman.id)


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


class RelaxedDiscoverTests(TestCase):
    """Коли строгих збігів менше 3 — схожі анкети за статтю та орієнтацією."""

    def setUp(self):
        self.book = Tag.objects.create(name='Релакс-книги', category=TagCategory.INTEREST)
        self.hiking = Tag.objects.create(name='Релакс-походи', category=TagCategory.INTEREST)
        self.chess = Tag.objects.create(name='Релакс-шахи', category=TagCategory.INTEREST)
        self.english = Tag.objects.create(name='Релакс-англійська', category=TagCategory.LANGUAGE)
        self.hobby = Tag.objects.create(name='Релакс-хобі', category=TagCategory.HOBBY)

        self.viewer = make_user_with_profile('viewer.relax@example.com', 'Оля')
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            looking_for=LookingFor.FEMALE,
            min_age=18,
            max_age=99,
        )
        ProfileTag.objects.create(profile=self.viewer.profile, tag=self.book, mode=SearchMode.DATING)
        ProfileTag.objects.create(profile=self.viewer.profile, tag=self.hiking, mode=SearchMode.DATING)

        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.BFF).update(
            looking_for=BffLookingFor.LANGUAGE,
        )
        ProfileTag.objects.create(
            profile=self.viewer.profile, tag=self.english, mode=SearchMode.BFF, level=LanguageLevel.B1,
        )
        ProfileTag.objects.create(
            profile=self.viewer.profile, tag=self.hobby, mode=SearchMode.BFF, level=HobbyLevel.NOVICE,
        )

    def _dating_candidate(self, email, name, gender, tags=()):
        user = make_user_with_profile(email, name)
        user.profile.gender = gender
        user.profile.save()
        for tag in tags:
            ProfileTag.objects.create(profile=user.profile, tag=tag, mode=SearchMode.DATING)
        return user

    def _bff_candidate(self, email, name, looking_for, language_level, hobby_level):
        user = make_user_with_profile(email, name)
        ProfileMode.objects.filter(profile=user.profile, mode=SearchMode.BFF).update(looking_for=looking_for)
        ProfileTag.objects.create(
            profile=user.profile, tag=self.english, mode=SearchMode.BFF, level=language_level,
        )
        ProfileTag.objects.create(
            profile=user.profile, tag=self.hobby, mode=SearchMode.BFF, level=hobby_level,
        )
        return user

    def test_strict_dating_empty_relaxed_only_wanted_gender(self):
        woman = self._dating_candidate(
            'woman.relax@example.com', 'Катя', 'female', tags=(self.chess,),
        )
        self._dating_candidate(
            'man.relax@example.com', 'Ігор', 'male', tags=(self.chess,),
        )
        strict, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(strict)
        relaxed, shared = next_candidate(self.viewer, SearchMode.DATING, relaxed=True)
        self.assertEqual(relaxed.user_id, woman.id)
        self.assertEqual(shared, {})

    def test_relaxed_dating_everyone_includes_any_gender(self):
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            looking_for=LookingFor.EVERYONE,
        )
        man = self._dating_candidate('any.man@example.com', 'Богдан', 'male', tags=(self.chess,))
        strict, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(strict)
        relaxed, _ = next_candidate(self.viewer, SearchMode.DATING, relaxed=True)
        self.assertEqual(relaxed.user_id, man.id)

    def test_relaxed_does_not_repeat_already_swiped(self):
        woman = self._dating_candidate('swiped.woman@example.com', 'Леся', 'female', tags=(self.chess,))
        record_swipe(self.viewer, woman.id, SearchMode.DATING, False)
        relaxed, _ = next_candidate(self.viewer, SearchMode.DATING, relaxed=True)
        self.assertIsNone(relaxed)

    def test_strict_match_is_preferred_over_relaxed(self):
        match = self._dating_candidate(
            'real.match@example.com', 'Іра', 'female', tags=(self.book, self.hiking),
        )
        self._dating_candidate(
            'weak.match@example.com', 'Софія', 'female', tags=(self.chess,),
        )
        profile, shared = next_candidate(self.viewer, SearchMode.DATING)
        self.assertEqual(profile.user_id, match.id)
        self.assertIn(self.book.id, shared['interests'])

    def test_bff_relaxed_shows_profiles_without_hobby_match(self):
        friend = self._bff_candidate(
            'friend.relax@example.com', 'Марта',
            looking_for=BffLookingFor.TRAVEL,
            language_level=LanguageLevel.C1,
            hobby_level=HobbyLevel.PRO,
        )
        strict, _ = next_candidate(self.viewer, SearchMode.BFF)
        self.assertIsNone(strict)
        relaxed, _ = next_candidate(self.viewer, SearchMode.BFF, relaxed=True)
        self.assertEqual(relaxed.user_id, friend.id)

    def test_discover_api_offers_browse_then_returns_relaxed_candidate(self):
        woman = self._dating_candidate(
            'api.woman@example.com', 'Ніна', 'female', tags=(self.chess,),
        )
        self.client.force_login(self.viewer)
        empty = self.client.get(reverse('discover_next'), {'mode': 'dating'})
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json()['candidate'])
        self.assertTrue(empty.json()['can_browse'])
        browsed = self.client.get(reverse('discover_next'), {'mode': 'dating', 'relaxed': '1'})
        self.assertEqual(browsed.status_code, 200)
        self.assertEqual(browsed.json()['candidate']['user_id'], woman.id)

    def test_relaxed_includes_other_city_when_gender_and_orientation_match(self):
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            looking_for=LookingFor.MALE,
        )
        man = self._dating_candidate('city.man@example.com', 'Тарас', 'male', tags=(self.chess,))
        man.profile.orientation = Orientation.STRAIGHT
        man.profile.city = 'Львів'
        man.profile.save()
        strict, _ = next_candidate(self.viewer, SearchMode.DATING)
        self.assertIsNone(strict)
        relaxed, _ = next_candidate(self.viewer, SearchMode.DATING, relaxed=True)
        self.assertEqual(relaxed.user_id, man.id)

    def test_relaxed_skips_incompatible_orientation(self):
        ProfileMode.objects.filter(profile=self.viewer.profile, mode=SearchMode.DATING).update(
            looking_for=LookingFor.MALE,
        )
        gay_man = self._dating_candidate('gay.man@example.com', 'Максим', 'male', tags=(self.chess,))
        gay_man.profile.orientation = Orientation.GAY
        gay_man.profile.city = 'Львів'
        gay_man.profile.save()
        relaxed, _ = next_candidate(self.viewer, SearchMode.DATING, relaxed=True)
        self.assertIsNone(relaxed)

    def test_few_strict_matches_offer_similar_without_duplicates(self):
        match = self._dating_candidate(
            'few.strict@example.com', 'Іра', 'female', tags=(self.book, self.hiking),
        )
        extra = self._dating_candidate(
            'few.extra@example.com', 'Софія', 'female', tags=(self.chess,),
        )
        extra.profile.city = 'Одеса'
        extra.profile.save()

        self.assertEqual(count_strict_candidates(self.viewer, SearchMode.DATING), 1)
        self.assertTrue(has_similar_candidates(self.viewer, SearchMode.DATING))

        self.client.force_login(self.viewer)
        first = self.client.get(reverse('discover_next'), {'mode': 'dating'})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['candidate']['user_id'], match.id)
        self.assertTrue(first.json()['can_browse'])

        record_swipe(self.viewer, match.id, SearchMode.DATING, False)
        empty = self.client.get(reverse('discover_next'), {'mode': 'dating'})
        self.assertIsNone(empty.json()['candidate'])
        self.assertTrue(empty.json()['can_browse'])

        similar = self.client.get(reverse('discover_next'), {'mode': 'dating', 'relaxed': '1'})
        self.assertEqual(similar.json()['candidate']['user_id'], extra.id)

        record_swipe(self.viewer, extra.id, SearchMode.DATING, False)
        again = self.client.get(reverse('discover_next'), {'mode': 'dating', 'relaxed': '1'})
        self.assertIsNone(again.json()['candidate'])

    def test_three_strict_matches_do_not_offer_similar_yet(self):
        for idx in range(3):
            self._dating_candidate(
                f'strict.pool.{idx}@example.com', f'Анна{idx}', 'female',
                tags=(self.book, self.hiking),
            )
        extra = self._dating_candidate(
            'pool.extra@example.com', 'Оксана', 'female', tags=(self.chess,),
        )
        extra.profile.city = 'Харків'
        extra.profile.save()
        self.client.force_login(self.viewer)
        first = self.client.get(reverse('discover_next'), {'mode': 'dating'})
        self.assertIsNotNone(first.json()['candidate'])
        self.assertFalse(first.json()['can_browse'])
        self.assertEqual(count_strict_candidates(self.viewer, SearchMode.DATING), 3)
