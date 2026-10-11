from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from grove.models import (
    Organization,
    OrganizationMember,
    Plot,
    PlotHealthAnalysis,
    Task,
    TreeBatch,
)
from grove_finance.models import Transaction
from grove_carbon.models import CarbonCalculation
from grove_compliance.models import CertificationDocument
from grove_market.models import MarketplaceListing


def small_jpeg(name="field.jpg"):
    buffer = BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


class GroveWorkspaceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="farm-owner", password="test-password")
        self.worker = User.objects.create_user(username="field-worker", password="test-password")
        self.viewer = User.objects.create_user(username="farm-viewer", password="test-password")
        self.org = Organization.objects.create(name="Green Valley Farm", owner=self.owner)
        self.owner_membership = OrganizationMember.objects.create(
            org=self.org, user=self.owner, role="owner"
        )
        self.worker_membership = OrganizationMember.objects.create(
            org=self.org, user=self.worker, role="worker"
        )
        self.viewer_membership = OrganizationMember.objects.create(
            org=self.org, user=self.viewer, role="viewer"
        )
        self.plot = Plot.objects.create(
            org=self.org,
            name="North plot",
            boundary={"type": "Polygon", "coordinates": [[[90, 23], [91, 23], [91, 24], [90, 23]]]},
            area_hectares=Decimal("2.50"),
        )

    def test_create_organization_sets_business_account_and_owner_membership(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("grove:create_organization"),
            {
                "name": "New Nursery",
                "org_type": "nursery",
                "description": "Local native seedlings",
                "country": "Bangladesh",
                "region": "Sylhet",
                "total_area_hectares": "1.25",
                "is_public": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        org = Organization.objects.get(name="New Nursery")
        self.assertTrue(OrganizationMember.objects.filter(org=org, user=self.owner, role="owner").exists())
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.account_type, "business")

    def test_public_farm_profile_displays_only_public_organizations(self):
        self.client.force_login(self.owner)
        public_response = self.client.get(reverse("grove:public_farm", args=[self.org.slug]))
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "Green Valley Farm")
        self.org.is_public = False
        self.org.save(update_fields=["is_public"])
        private_response = self.client.get(reverse("grove:public_farm", args=[self.org.slug]))
        self.assertEqual(private_response.status_code, 404)

    def test_viewer_cannot_create_plot(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("grove:create_plot", args=[self.org.slug]))
        self.assertEqual(response.status_code, 403)

    def test_plot_requires_valid_closed_geojson_boundary(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("grove:create_plot", args=[self.org.slug]),
            {
                "name": "Open boundary",
                "area_hectares": "1",
                "boundary": '{"type":"Polygon","coordinates":[[[90,23],[91,23],[91,24],[90,24]]]}',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Plot.objects.filter(name="Open boundary").exists())

    def test_csv_import_creates_batches_and_invalid_file_is_atomic(self):
        self.client.force_login(self.owner)
        valid = SimpleUploadedFile(
            "trees.csv",
            b"species,quantity,planted_date,spacing_m,source_nursery\nMango,25,2025-06-01,3.5,Local nursery\n",
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("grove:import_batches", args=[self.org.slug, self.plot.pk]),
            {"csv_file": valid},
        )
        self.assertEqual(response.status_code, 302)
        batch = TreeBatch.objects.get(plot=self.plot)
        self.assertEqual(batch.quantity, 25)
        self.assertEqual(batch.species, "Mango")
        self.assertTrue(batch.qr_batch_code)

        invalid = SimpleUploadedFile(
            "invalid.csv",
            b"species,quantity,planted_date\nMahogany,10,2025-01-01\nTeak,nope,2025-02-01\n",
            content_type="text/csv",
        )
        self.client.post(
            reverse("grove:import_batches", args=[self.org.slug, self.plot.pk]),
            {"csv_file": invalid},
        )
        self.assertEqual(TreeBatch.objects.count(), 1)

    def test_public_batch_page_and_authenticated_qr_image(self):
        batch = TreeBatch.objects.create(
            plot=self.plot,
            species="Teak",
            quantity=12,
            planted_date=date(2025, 7, 1),
            created_by=self.owner,
        )
        public_response = self.client.get(
            reverse("grove:public_batch", args=[batch.qr_batch_code])
        )
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, "Teak")

        self.client.force_login(self.owner)
        qr_response = self.client.get(
            reverse("grove:batch_qr", args=[self.org.slug, batch.qr_batch_code])
        )
        self.assertEqual(qr_response.status_code, 200)
        self.assertEqual(qr_response["Content-Type"], "image/png")
        self.assertTrue(qr_response.content.startswith(b"\x89PNG"))

    def test_worker_can_complete_assigned_task_but_not_another_users_task(self):
        task = Task.objects.create(
            plot=self.plot,
            assigned_to=self.worker,
            task_type="water",
            title="Water seedlings",
            due_date=date(2026, 10, 20),
            created_by=self.owner,
        )
        self.client.force_login(self.worker)
        response = self.client.post(reverse("grove:complete_task", args=[self.org.slug, task.pk]))
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertIsNotNone(task.completed_at)

        unassigned_task = Task.objects.create(
            plot=self.plot,
            assigned_to=self.owner,
            task_type="inspect",
            title="Inspect orchard",
            due_date=date(2026, 10, 21),
            created_by=self.owner,
        )
        forbidden = self.client.post(
            reverse("grove:complete_task", args=[self.org.slug, unassigned_task.pk])
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_owner_can_add_an_existing_account_to_workspace(self):
        new_member = User.objects.create_user(username="new-field-worker", password="test-password")
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("grove:add_member", args=[self.org.slug]),
            {"user": new_member.pk, "role": "worker"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrganizationMember.objects.filter(
                org=self.org, user=new_member, role="worker"
            ).exists()
        )

    def test_manager_cannot_grant_manager_role(self):
        manager = User.objects.create_user(username="farm-manager", password="test-password")
        OrganizationMember.objects.create(org=self.org, user=manager, role="manager")
        new_member = User.objects.create_user(username="another-worker", password="test-password")
        self.client.force_login(manager)
        response = self.client.post(
            reverse("grove:add_member", args=[self.org.slug]),
            {"user": new_member.pk, "role": "manager"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(OrganizationMember.objects.filter(org=self.org, user=new_member).exists())

    def test_ndvi_values_are_bounded_and_owner_can_save_observation(self):
        self.client.force_login(self.owner)
        invalid = self.client.post(
            reverse("grove:add_health_snapshot", args=[self.org.slug, self.plot.pk]),
            {"ndvi": "1.5"},
        )
        self.assertEqual(invalid.status_code, 400)
        valid = self.client.post(
            reverse("grove:add_health_snapshot", args=[self.org.slug, self.plot.pk]),
            {"ndvi": "0.7231", "notes": "Sentinel-2 field check"},
        )
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(self.plot.health_snapshots.get().ndvi, Decimal("0.7231"))

    def test_plot_ai_health_uses_cached_image_and_manager_permissions(self):
        from trees.ai_services import AIServiceError, image_digest

        self.client.force_login(self.worker)
        denied = self.client.post(
            reverse("grove:analyze_plot_health", args=[self.org.slug, self.plot.pk]),
            {"image": small_jpeg()},
        )
        self.assertEqual(denied.status_code, 403)

        result = {
            "score": 84,
            "issues": ["Minor leaf discoloration"],
            "recommendations": ["Check irrigation"],
            "confidence": 0.86,
            "model_used": "test-model",
            "image_hash": image_digest(small_jpeg()),
        }
        self.client.force_login(self.owner)
        with patch("grove.views.analyze_tree_health", return_value=result) as analyze:
            first = self.client.post(
                reverse("grove:analyze_plot_health", args=[self.org.slug, self.plot.pk]),
                {"image": small_jpeg()},
            )
            second = self.client.post(
                reverse("grove:analyze_plot_health", args=[self.org.slug, self.plot.pk]),
                {"image": small_jpeg()},
            )
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(PlotHealthAnalysis.objects.get(plot=self.plot).score, 84)

    def test_missing_ai_provider_returns_user_visible_error(self):
        from trees.ai_services import AIServiceError

        self.client.force_login(self.owner)
        with patch(
            "grove.views.analyze_tree_health",
            side_effect=AIServiceError("AI provider is not configured."),
        ):
            response = self.client.post(
                reverse("grove:analyze_plot_health", args=[self.org.slug, self.plot.pk]),
                {"image": small_jpeg()},
                follow=True,
            )
        self.assertContains(response, "AI provider is not configured.")

    def test_finance_report_is_member_scoped_and_pdf(self):
        Transaction.objects.create(
            org=self.org,
            plot=self.plot,
            trans_type="expense",
            category="seedlings",
            amount=Decimal("1250.00"),
            description="Mango seedlings",
            date=date(2026, 10, 1),
            created_by=self.owner,
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse("grove_finance:pdf_report", args=[self.org.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

        outsider = User.objects.create_user(username="outsider", password="test-password")
        self.client.force_login(outsider)
        denied = self.client.get(reverse("grove_finance:overview", args=[self.org.slug]))
        self.assertEqual(denied.status_code, 404)

    def test_carbon_estimate_is_screening_only_and_stores_no_eligible_credits(self):
        TreeBatch.objects.create(
            plot=self.plot,
            species="Mango",
            quantity=100,
            planted_date=date(2026, 1, 1),
            created_by=self.owner,
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("grove_carbon:overview", args=[self.org.slug]),
            {"plot": self.plot.pk, "horizon_years": 2},
            follow=True,
        )
        self.assertContains(response, "not a verified carbon inventory")
        calculation = CarbonCalculation.objects.get(plot=self.plot)
        self.assertEqual(calculation.co2_tonnes, Decimal("4.40"))
        self.assertIsNone(calculation.eligible_credits)

    def test_compliance_document_download_requires_organization_membership(self):
        file = SimpleUploadedFile("certificate.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        document = CertificationDocument.objects.create(
            org=self.org,
            title="Forest certificate",
            certification_type="Local permit",
            document=file,
            uploaded_by=self.owner,
        )
        outsider = User.objects.create_user(username="no-access", password="test-password")
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("grove_compliance:download_document", args=[self.org.slug, document.pk])
        )
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("grove_compliance:download_document", args=[self.org.slug, document.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith('attachment; filename="certificate'))
        self.assertTrue(response["Content-Disposition"].endswith('.pdf"'))

    def test_market_listing_creation_requires_a_manager_and_is_public(self):
        self.client.force_login(self.worker)
        denied = self.client.get(reverse("grove_market:create_listing"))
        self.assertRedirects(denied, reverse("grove_market:listings"))

        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("grove_market:create_listing"),
            {
                "org": self.org.slug,
                "listing_type": "sell",
                "title": "Native mango seedlings",
                "category": "Seedlings",
                "description": "Locally grown seedlings available for the next planting season.",
                "price_amount": "75.00",
                "currency": "BDT",
                "region": "Sylhet",
                "contact_email": "farm@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        listing = MarketplaceListing.objects.get()
        self.assertEqual(listing.org, self.org)
        self.assertEqual(listing.status, "active")

    def test_homepage_exposes_both_audiences_and_community_feed_remains_available(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Explore the community")
        self.assertContains(response, "Open Grove for farms")
        self.assertEqual(self.client.get(reverse("tree_list")).status_code, 200)
