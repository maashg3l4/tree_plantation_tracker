import hashlib
import json
import tempfile
from datetime import date, timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .ai_services import AIServiceError, identify_species
from .daily_jobs import publish_scheduled_posts
from .gamification import record_activity, update_achievement_progress
from .impact import refresh_user_impact_score
from .models import (
    Achievement,
    ChallengeParticipation,
    DailyChallenge,
    HelpOffer,
    Notification,
    NewsletterSubscription,
    Pledge,
    Profile,
    Reaction,
    Tree,
    TreeHashtag,
    TreeMedia,
    TreeHealthAnalysis,
    UserAchievement,
    UserFollow,
    UserImpactScore,
    UserStreak,
)


class ImpactReactionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='tree-owner', password='test-password')
        self.actor = User.objects.create_user(username='community-member', password='test-password')
        self.tree = Tree.objects.create(
            user=self.owner,
            name='Mango tree',
            species='Mango',
            date_planted=date(2025, 1, 1),
        )
        self.client.force_login(self.actor)
        self.url = reverse('react_or_comment')

    def react(self, **values):
        payload = {
            'form_type': 'react',
            'tree_id': self.tree.pk,
            **values,
        }
        return self.client.post(self.url, payload)

    def test_planting_reaction_creates_pledge_notification_and_weighted_score(self):
        response = self.react(reaction_type='planted', intensity='3', note='Planting this season')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['counts']['planted'], 1)
        reaction = Reaction.objects.get(user=self.actor, tree=self.tree)
        self.assertEqual(reaction.intensity, 3)
        self.assertEqual(reaction.note, 'Planting this season')
        self.assertEqual(Pledge.objects.get(user=self.actor).species, 'Mango')
        notification = Notification.objects.get(user=self.owner)
        self.assertEqual(notification.actor, self.actor)
        self.assertEqual(notification.tree, self.tree)
        self.assertEqual(UserImpactScore.objects.get(user=self.actor).total_score, 30)

        self.react(reaction_type='planted', intensity='2')
        self.assertEqual(Pledge.objects.filter(user=self.actor).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), 1)
        self.assertEqual(UserImpactScore.objects.get(user=self.actor).total_score, 20)

    def test_help_reaction_requires_valid_type_and_records_offer(self):
        invalid = self.react(reaction_type='help', help_type='teleport')
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(Reaction.objects.exists())

        response = self.react(
            reaction_type='help',
            intensity='2',
            help_type='water',
            help_message='I can water it this weekend.',
        )
        self.assertEqual(response.status_code, 200)
        offer = HelpOffer.objects.get(user=self.actor, post=self.tree)
        self.assertEqual(offer.help_type, 'water')
        self.assertEqual(offer.message, 'I can water it this weekend.')
        self.assertEqual(UserImpactScore.objects.get(user=self.actor).total_score, 16)
        self.assertEqual(UserImpactScore.objects.get(user=self.actor).help_offered, 1)

    def test_unknown_reaction_and_invalid_intensity_are_rejected(self):
        self.assertEqual(self.react(reaction_type='like').status_code, 400)
        self.assertEqual(
            self.react(reaction_type='care', intensity='4').status_code,
            400,
        )
        self.assertFalse(Reaction.objects.exists())

    def test_comment_uses_htmx_partial_response(self):
        response = self.client.post(
            self.url,
            {'form_type': 'comment', 'tree_id': self.tree.pk, 'comment_text': 'A healthy start.'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A healthy start.')
        self.assertContains(response, 'community-member')

    def test_reaction_endpoint_enforces_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.actor)

        response = csrf_client.post(
            self.url,
            {'form_type': 'react', 'tree_id': self.tree.pk, 'reaction_type': 'care'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Reaction.objects.exists())

    def test_feed_renders_impact_reactions_and_tree_context(self):
        response = self.client.get(reverse('tree_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'I Planted Too')
        self.assertContains(response, 'Sending Care')
        self.assertContains(response, 'data-tree-status="unknown"')
        self.assertNotContains(response, '👍 Like')

    def test_inspiring_reactions_boost_posts_in_feed_order(self):
        another_tree = Tree.objects.create(
            user=self.owner,
            name='Oak tree',
            species='Oak',
            date_planted=date(2025, 2, 1),
        )
        Reaction.objects.create(
            tree=self.tree,
            user=self.actor,
            reaction='inspiring',
            intensity=2,
        )

        response = self.client.get(reverse('tree_list'))

        self.assertEqual(
            [tree.pk for tree in response.context['trees']],
            [self.tree.pk, another_tree.pk],
        )

    def test_pledge_status_updates_user_impact_score(self):
        Pledge.objects.create(user=self.actor, source_post=self.tree, species='Mango')
        response = self.client.post(
            reverse('update_pledge_status', args=[Pledge.objects.get(user=self.actor).pk]),
            {'status': 'planted'},
        )

        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(UserImpactScore.objects.get(user=self.actor).trees_planted, 1)
        self.assertContains(self.client.get(reverse('profile')), 'Pledge queue')

    def test_deleting_tree_recalculates_reactors_impact_scores(self):
        reaction = Reaction.objects.create(user=self.actor, tree=self.tree, reaction='help')
        HelpOffer.objects.create(
            user=self.actor,
            post=self.tree,
            reaction=reaction,
            help_type='water',
        )
        refresh_user_impact_score(self.actor)
        self.client.force_login(self.owner)

        response = self.client.post(reverse('delete_tree', args=[self.tree.pk]))

        self.assertEqual(response.status_code, 200)
        score = UserImpactScore.objects.get(user=self.actor)
        self.assertEqual(score.total_score, 0)
        self.assertEqual(score.help_offered, 0)


class AIAnalysisTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        self.media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.owner = User.objects.create_user(username='ai-tree-owner', password='test-password')
        self.other_user = User.objects.create_user(username='other-member', password='test-password')
        self.tree = Tree.objects.create(
            user=self.owner,
            name='Test tree',
            date_planted=date(2025, 1, 1),
            image=self.png_upload(),
        )
        self.addCleanup(self.tree.image.close)

    @staticmethod
    def png_upload():
        content = BytesIO()
        Image.new('RGB', (2, 2), 'green').save(content, format='PNG')
        return SimpleUploadedFile('tree.png', content.getvalue(), content_type='image/png')

    def test_species_api_falls_back_from_plantnet_to_inaturalist(self):
        with override_settings(PLANTNET_API_KEY='plantnet-test-key'), patch(
            'trees.ai_services._post_image',
            side_effect=[
                AIServiceError('PlantNet unavailable'),
                {'results': [{
                    'score': 0.87,
                    'taxon': {'name': 'Quercus robur', 'preferred_common_name': 'English oak'},
                }]},
            ],
        ) as post_image:
            result = identify_species(self.png_upload())

        self.assertEqual(result['provider'], 'inaturalist')
        self.assertEqual(result['predictions'][0]['name'], 'English oak')
        self.assertEqual(result['predictions'][0]['confidence'], 0.87)
        self.assertEqual(post_image.call_count, 2)
        self.assertTrue(post_image.call_args_list[1].kwargs['file_field'] == 'image')

    def test_species_identification_tracks_user_correction_on_tree(self):
        image_bytes = self.png_upload().read()
        prediction = {
            'provider': 'plantnet',
            'predictions': [
                {'name': 'Quercus robur', 'confidence': 0.45},
                {'name': 'Quercus petraea', 'confidence': 0.31},
            ],
            'image_hash': hashlib.sha256(image_bytes).hexdigest(),
        }
        self.client.force_login(self.owner)
        with patch('trees.views.identify_species', return_value=prediction):
            identify_response = self.client.post(
                reverse('identify_tree_species'),
                {'image': self.png_upload()},
            )
        self.assertEqual(identify_response.status_code, 200)
        self.assertEqual(identify_response.json()['predictions'][1]['name'], 'Quercus petraea')

        create_response = self.client.post(reverse('add_tree'), {
            'name': 'Oak sapling',
            'species': 'Quercus petraea',
            'date_planted': '2026-10-11',
            'image': self.png_upload(),
        })

        self.assertEqual(create_response.status_code, 302)
        tree = Tree.objects.get(name='Oak sapling')
        self.assertEqual(tree.ai_species_guess, 'Quercus robur')
        self.assertEqual(tree.ai_confidence, 0.45)
        self.assertTrue(tree.ai_species_corrected)

    def test_health_analysis_is_cached_for_the_same_tree_image(self):
        self.client.force_login(self.owner)
        analysis = {
            'score': 92,
            'issues': ['A few dry leaves'],
            'recommendations': ['Water during dry weather'],
            'confidence': 0.84,
            'model_used': 'gemini-2.5-flash',
            'image_hash': hashlib.sha256(self.tree.image.read()).hexdigest(),
        }
        self.tree.image.seek(0)
        endpoint = reverse('analyze_tree', args=[self.tree.pk])
        with patch('trees.views.analyze_tree_health', return_value=analysis) as analyze:
            first = self.client.post(endpoint)
            second = self.client.post(endpoint)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['analysis']['score'], 92)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(TreeHealthAnalysis.objects.filter(post=self.tree).count(), 1)

    def test_only_tree_owner_can_run_health_analysis(self):
        self.client.force_login(self.other_user)

        response = self.client.post(reverse('analyze_tree', args=[self.tree.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(TreeHealthAnalysis.objects.exists())

    def test_feed_health_chip_renders_existing_json_analysis_data(self):
        TreeHealthAnalysis.objects.create(
            post=self.tree,
            score=92,
            issues=['Dry leaves', 'Low contrast'],
            recommendations=['Water regularly'],
            confidence=0.84,
            model_used='gemini-2.5-flash',
            image_hash='0' * 64,
        )

        response = self.client.get(reverse('tree_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Health 92/100')
        self.assertContains(response, 'data-issues="[&quot;Dry leaves&quot;, &quot;Low contrast&quot;]"')


class FooterFeatureTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_footer_renders_navigation_newsletter_language_and_status(self):
        response = self.client.get(reverse("tree_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "canopy-footer")
        self.assertContains(response, reverse("newsletter_subscribe"))
        self.assertContains(response, reverse("system_status"))
        self.assertContains(response, reverse("set_language"))

    def test_newsletter_subscription_is_validated_and_idempotent(self):
        invalid = self.client.post(
            reverse("newsletter_subscribe"), {"email": "not-an-email"}
        )
        self.assertEqual(invalid.status_code, 400)

        first = self.client.post(
            reverse("newsletter_subscribe"), {"email": "Garden@example.com"}
        )
        second = self.client.post(
            reverse("newsletter_subscribe"), {"email": "garden@example.com"}
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(NewsletterSubscription.objects.count(), 1)
        self.assertEqual(
            NewsletterSubscription.objects.get().email, "garden@example.com"
        )
        self.assertIn("newsletter/unsubscribe/", first.json()["unsubscribe_url"])

    def test_newsletter_unsubscribe_requires_confirmation_and_can_be_reversed(self):
        subscription = NewsletterSubscription.objects.create(email="garden@example.com")
        unsubscribe_url = reverse(
            "newsletter_unsubscribe", args=[subscription.unsubscribe_token]
        )

        self.assertEqual(self.client.get(unsubscribe_url).status_code, 200)
        response = self.client.post(unsubscribe_url)
        self.assertEqual(response.status_code, 200)
        subscription.refresh_from_db()
        self.assertFalse(subscription.is_active)
        self.assertIsNotNone(subscription.unsubscribed_at)

        resubscribed = self.client.post(
            reverse("newsletter_subscribe"), {"email": subscription.email}
        )
        self.assertEqual(resubscribed.status_code, 200)
        subscription.refresh_from_db()
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.unsubscribed_at)

    def test_status_endpoint_reports_database_health(self):
        response = self.client.get(reverse("system_status"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "operational")
class CommunityCoreTests(TestCase):
    def make_user(self, username, email=None):
        return User.objects.create_user(
            username=username,
            email=email or f"{username}@example.com",
            password="A-strong-garden-password-42!",
        )

    def test_signup_creates_account_and_starts_onboarding(self):
        response = self.client.post(
            reverse("signup_step2"),
            {
                "email": "newgardener@example.com",
                "password1": "A-strong-garden-password-42!",
                "password2": "A-strong-garden-password-42!",
                "accept_terms": "on",
            },
        )

        self.assertRedirects(response, reverse("onboarding"))
        user = User.objects.get(email="newgardener@example.com")
        self.assertTrue(user.check_password("A-strong-garden-password-42!"))
        self.assertTrue(Profile.objects.filter(user=user).exists())
        self.assertTrue(self.client.session["onboarding_incomplete"])

    def test_legacy_register_route_redirects_to_new_signup_experience(self):
        response = self.client.get(reverse("register"))

        self.assertRedirects(response, reverse("signup_step1"))

    def test_onboarding_accepts_underscores_and_sets_profile(self):
        user = self.make_user("temporary-account")
        self.client.force_login(user)

        response = self.client.post(
            reverse("onboarding"),
            {
                "first_name": "Garden",
                "last_name": "Friend",
                "username": "green_friend",
                "bio": "Growing native trees.",
                "location": "Dhaka",
                "interests": ["trees", "flowers"],
            },
        )

        self.assertRedirects(response, reverse("user_profile", args=["green_friend"]))
        user.refresh_from_db()
        user.profile.refresh_from_db()
        self.assertEqual(user.username, "green_friend")
        self.assertEqual(user.profile.interests, ["trees", "flowers"])
        self.assertEqual(user.profile.bio, "Growing native trees.")

    def test_username_availability_is_case_insensitive_and_allows_current_user(self):
        user = self.make_user("GreenFriend")
        self.make_user("OtherGardener")
        self.client.force_login(user)

        same_user = self.client.get(
            reverse("username_available"), {"username": user.username}
        )
        another_user = self.client.get(
            reverse("username_available"), {"username": "OTHERGARDENER"}
        )
        invalid_handle = self.client.get(
            reverse("username_available"), {"username": "two words"}
        )

        self.assertTrue(same_user.json()["available"])
        self.assertFalse(another_user.json()["available"])
        self.assertFalse(invalid_handle.json()["available"])

    def test_follow_creates_notification_and_can_be_removed(self):
        follower = self.make_user("first-gardener")
        target = self.make_user("second-gardener")
        self.client.force_login(follower)
        url = reverse("toggle_follow", args=[target.username])

        created = self.client.post(url)
        removed = self.client.post(url)

        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["following"])
        self.assertEqual(created.json()["follower_count"], 1)
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.json()["following"])
        self.assertFalse(UserFollow.objects.exists())
        self.assertEqual(
            Notification.objects.filter(user=target, notification_type="follow").count(), 1
        )

    def test_follow_rejects_self_follow(self):
        user = self.make_user("solo-gardener")
        self.client.force_login(user)

        response = self.client.post(reverse("toggle_follow", args=[user.username]))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(UserFollow.objects.exists())

    def test_follow_button_has_csrf_token_for_ajax_request(self):
        follower = self.make_user("csrf-follower")
        target = self.make_user("csrf-target")
        client = Client(enforce_csrf_checks=True)
        client.force_login(follower)
        client.get(reverse("user_profile", args=[target.username]))
        csrf_token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("toggle_follow", args=[target.username]),
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["following"])

    def test_password_reset_flow_has_named_routes(self):
        self.make_user("password-gardener")

        response = self.client.post(
            reverse("password_reset"), {"email": "password-gardener@example.com"}
        )

        self.assertRedirects(response, reverse("password_reset_done"))

    def test_email_login_is_case_insensitive_and_rejects_external_next_url(self):
        user = self.make_user("email-login-gardener", "gardener@example.com")

        response = self.client.post(
            reverse("login"),
            {
                "email": "GARDENER@example.com",
                "password": "A-strong-garden-password-42!",
                "remember_me": "on",
                "next": "https://attacker.example/",
            },
        )

        self.assertRedirects(response, reverse("tree_list"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.pk, user.pk)

    def test_service_worker_is_served_from_root_scope(self):
        response = self.client.get(reverse("service_worker"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertTrue(response["Cache-Control"].startswith("max-age=0"))
        self.assertContains(response, 'const CACHE_NAME = "tree-garden-v4"')
        self.assertContains(response, '"/static/trees/footer.css"')

    def test_offline_page_cache_opt_in_is_limited_to_anonymous_requests(self):
        anonymous = self.client.get(reverse("tree_list"))
        user = self.make_user("signed-in-gardener")
        self.client.force_login(user)
        authenticated = self.client.get(reverse("tree_list"))

        self.assertEqual(anonymous["X-Public-Offline-Cacheable"], "true")
        self.assertNotIn("X-Public-Offline-Cacheable", authenticated)


class EngagementEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="engagement-user", password="test-password"
        )

    def make_achievement(self, slug, metric):
        return Achievement.objects.create(
            slug=slug,
            name=slug.replace("-", " ").title(),
            description="Test achievement",
            criteria={"metric": metric, "threshold": 1},
            points=1,
        )

    def test_streak_advances_and_uses_one_monthly_freeze(self):
        first_day = date(2025, 1, 31)
        second_day = date(2025, 2, 2)

        record_activity(self.user, "post", day=first_day)
        streak = record_activity(self.user, "post", day=second_day)

        self.assertEqual(streak.current_post, 2)
        self.assertEqual(streak.longest_post, 2)
        self.assertEqual(streak.freeze_available, 0)
        self.assertEqual(streak.freeze_month, date(2025, 2, 1))

        repeated = record_activity(self.user, "post", day=second_day)
        self.assertEqual(repeated.current_post, 2)

    def test_login_signal_records_daily_login_streak(self):
        self.assertTrue(self.client.login(username="engagement-user", password="test-password"))

        streak = UserStreak.objects.get(user=self.user)
        self.assertEqual(streak.current_login, 1)
        self.assertEqual(streak.last_login_date, timezone.localdate())

    def test_owner_achievements_update_after_comments_reactions_and_planted_pledges(self):
        owner = self.user
        actor = User.objects.create_user(
            username="engagement-actor", password="test-password"
        )
        tree = Tree.objects.create(
            user=owner,
            name="Oak",
            species="Oak",
            date_planted=date(2025, 1, 1),
        )
        comment_badge = self.make_achievement("test-comments", "post_comments")
        reaction_badge = self.make_achievement(
            "test-reactions", "max_post_reactions"
        )
        pledge_badge = self.make_achievement("test-pledges", "post_pledges")
        self.client.force_login(actor)

        self.client.post(
            reverse("react_or_comment"),
            {
                "form_type": "comment",
                "tree_id": tree.pk,
                "comment_text": "Growing well!",
            },
        )
        self.assertIsNotNone(
            UserAchievement.objects.get(
                user=owner, achievement=comment_badge
            ).unlocked_at
        )

        self.client.post(
            reverse("react_or_comment"),
            {
                "form_type": "react",
                "tree_id": tree.pk,
                "reaction_type": "care",
                "intensity": "1",
            },
        )
        self.assertIsNotNone(
            UserAchievement.objects.get(
                user=owner, achievement=reaction_badge
            ).unlocked_at
        )

        pledge = Pledge.objects.create(
            user=actor, source_post=tree, species="Oak"
        )
        self.client.post(
            reverse("update_pledge_status", args=[pledge.pk]),
            {"status": "planted"},
        )
        self.assertIsNotNone(
            UserAchievement.objects.get(
                user=owner, achievement=pledge_badge
            ).unlocked_at
        )

    def test_weekly_challenge_does_not_count_toward_daily_challenge_badge(self):
        badge = self.make_achievement("test-daily-challenges", "challenges")
        weekly = DailyChallenge.objects.create(
            date=date(2025, 1, 6),
            title="Weekly",
            description="A weekly challenge",
            challenge_type="weekly",
        )
        ChallengeParticipation.objects.create(challenge=weekly, user=self.user)

        update_achievement_progress(self.user)
        record = UserAchievement.objects.get(user=self.user, achievement=badge)
        self.assertEqual(record.progress, 0)
        self.assertIsNone(record.unlocked_at)

    def test_scheduled_posts_publish_and_start_post_streak(self):
        publish_at = timezone.now() - timedelta(minutes=1)
        tree = Tree.objects.create(
            user=self.user,
            name="Scheduled tree",
            date_planted=date(2025, 1, 1),
            publication_status="scheduled",
            scheduled_publish_at=publish_at,
        )

        self.assertEqual(publish_scheduled_posts(), 1)

        tree.refresh_from_db()
        self.assertEqual(tree.publication_status, "published")
        self.assertIsNotNone(tree.published_at)
        self.assertEqual(UserStreak.objects.get(user=self.user).current_post, 1)

    def test_draft_is_visible_only_on_its_owner_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("add_tree"),
            {
                "name": "Private sapling",
                "species": "Oak",
                "date_planted": "2025-01-01",
                "caption": "Still growing",
                "save_as_draft": "on",
            },
        )
        tree = Tree.objects.get(name="Private sapling")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(tree.publication_status, "draft")
        owner_profile = self.client.get(
            reverse("user_profile", args=[self.user.username])
        )
        self.assertIn(tree, owner_profile.context["posts"])
        self.assertContains(owner_profile, "Draft")
        self.assertEqual(self.client.get(reverse("tree_detail", args=[tree.pk])).status_code, 200)

        self.client.logout()
        public_profile = self.client.get(
            reverse("user_profile", args=[self.user.username])
        )
        self.assertNotIn(tree, public_profile.context["posts"])
        other_user = User.objects.create_user(
            username="other-profile-viewer", password="test-password"
        )
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse("tree_detail", args=[tree.pk])).status_code, 404
        )

    def test_post_media_and_hashtags_are_saved_and_searchable(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        with override_settings(MEDIA_ROOT=media_directory.name):
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("add_tree"),
                {
                    "name": "Community oak",
                    "species": "Oak",
                    "date_planted": "2025-01-01",
                    "caption": "Growing together #NativeTrees",
                    "extra_images": [
                        SimpleUploadedFile(
                            "leaf.jpg", b"image-data", content_type="image/jpeg"
                        )
                    ],
                },
            )
            tree = Tree.objects.get(name="Community oak")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                TreeMedia.objects.filter(tree=tree, media_type="image").count(), 1
            )
            self.assertTrue(
                TreeHashtag.objects.filter(tree=tree, tag="nativetrees").exists()
            )

        self.client.logout()
        search_response = self.client.get(reverse("search"), {"q": "#NativeTrees"})
        self.assertEqual(search_response.status_code, 200)
        self.assertContains(search_response, "Oak")

    @override_settings(CRON_SECRET="cron-test-secret")
    def test_daily_engagement_cron_requires_bearer_secret(self):
        url = reverse("daily_engagement_cron")
        unauthorized = self.client.get(url)
        self.assertEqual(unauthorized.status_code, 401)

        with patch(
            "trees.daily_jobs.run_daily_engagement",
            return_value={"published_posts": 0, "challenge_id": 1, "reminders": 0},
        ) as run_job:
            authorized = self.client.get(
                url, HTTP_AUTHORIZATION="Bearer cron-test-secret"
            )

        self.assertEqual(authorized.status_code, 200)
        self.assertTrue(authorized.json()["success"])
        run_job.assert_called_once_with()
