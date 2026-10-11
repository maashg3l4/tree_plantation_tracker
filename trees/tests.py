import hashlib
import json
import tempfile
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .ai_services import AIServiceError, identify_species
from .impact import refresh_user_impact_score
from .models import (
    HelpOffer,
    Notification,
    Pledge,
    Reaction,
    Tree,
    TreeHealthAnalysis,
    UserImpactScore,
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
# Create your tests here.
