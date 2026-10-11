from datetime import date

from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from trees.models import Comment, Notification, Tree

from .models import AIFlag, AuditLog, Report


class OpsConsoleTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            username="reporting-member", password="password-123"
        )
        self.owner = User.objects.create_user(
            username="reported-member", password="password-123"
        )
        self.moderator = User.objects.create_user(
            username="garden-moderator", password="password-123"
        )
        self.support = User.objects.create_user(
            username="garden-support", password="password-123"
        )
        moderator_group, _ = Group.objects.get_or_create(name="Moderator")
        support_group, _ = Group.objects.get_or_create(name="Support")
        self.moderator.groups.add(moderator_group)
        self.support.groups.add(support_group)
        self.tree = Tree.objects.create(
            user=self.owner,
            name="Reported oak",
            species="Oak",
            date_planted=date(2025, 1, 1),
            caption="A reportable post",
        )
        self.tree_content_type = ContentType.objects.get_for_model(Tree)
        self.report = Report.objects.create(
            reporter=self.reporter,
            content_type=self.tree_content_type,
            object_id=self.tree.pk,
            reason="spam",
            details="This post appears to be spam.",
        )

    def test_ops_console_denies_members_and_allows_moderator_read(self):
        dashboard = reverse("ops:dashboard")
        self.client.force_login(self.reporter)
        self.assertEqual(self.client.get(dashboard).status_code, 403)

        self.client.force_login(self.support)
        response = self.client.get(dashboard)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Community overview")
        self.assertEqual(response.context["pending_reports"], 1)

    def test_anonymous_users_are_sent_to_login(self):
        response = self.client.get(reverse("ops:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/?next=", response["Location"])

    def test_support_can_read_queue_but_cannot_take_action(self):
        self.client.force_login(self.support)
        detail = self.client.get(reverse("ops:report_detail", args=[self.report.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.context["can_moderate"])
        response = self.client.post(
            reverse("ops:report_action", args=[self.report.pk]),
            {"action": "hide", "reason": "Confirmed spam"},
        )
        self.assertEqual(response.status_code, 403)
        self.tree.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.tree.moderation_status, "visible")
        self.assertEqual(self.report.status, "pending")
        self.assertFalse(AuditLog.objects.exists())

    def test_report_submission_and_duplicate_are_idempotent(self):
        self.report.delete()
        self.client.force_login(self.reporter)
        url = reverse("report:submit", args=["tree", self.tree.pk])
        first = self.client.post(url, {"reason": "harassment", "details": "Please review."})
        second = self.client.post(url, {"reason": "spam", "details": "Second report."})

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Report.objects.filter(reporter=self.reporter).count(), 1)
        self.assertEqual(
            Report.objects.get(reporter=self.reporter).reason, "harassment"
        )

    def test_invalid_report_reason_is_not_saved(self):
        self.report.delete()
        self.client.force_login(self.reporter)
        response = self.client.post(
            reverse("report:submit", args=["tree", self.tree.pk]),
            {"reason": "invalid-reason", "details": "Not a supported reason"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Report.objects.filter(reporter=self.reporter).count(), 0)

    def test_profile_report_redirects_correctly_and_self_report_is_rejected(self):
        self.client.force_login(self.reporter)
        target_url = reverse("report:submit", args=["user", self.owner.pk])
        response = self.client.post(
            target_url, {"reason": "harassment", "details": "Please review this profile."}
        )
        self.assertRedirects(
            response, reverse("user_profile", args=[self.owner.username])
        )
        profile_report = Report.objects.get(
            reporter=self.reporter, content_type=ContentType.objects.get_for_model(User),
            object_id=self.owner.pk,
        )
        self.assertEqual(profile_report.content_object, self.owner)

        self.client.force_login(self.owner)
        self_report = self.client.post(
            reverse("report:submit", args=["user", self.owner.pk]),
            {"reason": "other", "details": "Cannot report yourself."},
        )
        self.assertRedirects(
            self_report, reverse("user_profile", args=[self.owner.username])
        )
        self.assertEqual(Report.objects.count(), 2)

    def test_moderator_can_hide_post_with_reason_and_immutable_audit(self):
        self.client.force_login(self.moderator)
        response = self.client.post(
            reverse("ops:report_action", args=[self.report.pk]),
            {"action": "hide", "reason": "Confirmed policy violation."},
        )

        self.assertRedirects(response, reverse("ops:reports"))
        self.tree.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.tree.moderation_status, "hidden")
        self.assertEqual(self.report.status, "action_taken")
        audit = AuditLog.objects.get()
        self.assertEqual(audit.actor, self.moderator)
        self.assertEqual(audit.reason, "Confirmed policy violation.")
        self.assertEqual(audit.before["moderation_status"], "visible")
        self.assertEqual(audit.after["moderation_status"], "hidden")

        self.client.logout()
        feed = self.client.get(reverse("tree_list"))
        self.assertNotContains(feed, "Reported oak")
        self.assertNotIn(self.tree, feed.context["trees"])
        self.assertNotIn(self.tree, self.client.get(reverse("discover")).context["trees"])
        self.assertNotIn(
            self.tree,
            self.client.get(
                reverse("user_profile", args=[self.owner.username])
            ).context["posts"],
        )
        search = self.client.get(reverse("search"), {"q": "Reported oak"})
        self.assertNotIn(self.tree, search.context["trees"])
        self.client.force_login(self.reporter)
        self.assertEqual(
            self.client.get(reverse("tree_detail", args=[self.tree.pk])).status_code,
            404,
        )

    def test_moderator_warning_creates_notification_and_audit_entry(self):
        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ops:report_action", args=[self.report.pk]),
            {"action": "warn", "reason": "Please follow community guidelines."},
        )

        notification = Notification.objects.get(user=self.owner)
        self.assertEqual(notification.actor, self.moderator)
        self.assertIn("community guidelines", notification.message)
        self.assertEqual(AuditLog.objects.get().action, "report_warn")

    def test_deleted_report_target_can_be_dismissed_and_audited(self):
        self.tree.delete()
        self.client.force_login(self.moderator)

        detail = self.client.get(reverse("ops:report_detail", args=[self.report.pk]))
        self.assertEqual(detail.status_code, 200)
        response = self.client.post(
            reverse("ops:report_action", args=[self.report.pk]),
            {"action": "dismiss", "reason": "The reported post was deleted."},
        )

        self.assertRedirects(response, reverse("ops:reports"))
        self.assertEqual(AuditLog.objects.get().action, "report_dismiss")

    def test_ai_flag_actions_are_moderator_only_and_audited(self):
        flag = AIFlag.objects.create(
            content_type=self.tree_content_type,
            object_id=self.tree.pk,
            score=91,
            reasoning="Repeated promotional content.",
            suggested_action="hide",
            source="review-test",
        )
        self.client.force_login(self.moderator)
        response = self.client.post(
            reverse("ops:ai_flag_action", args=[flag.pk]),
            {"action": "remove", "reason": "Confirmed spam after manual review."},
        )

        self.assertRedirects(response, reverse("ops:ai_flags"))
        self.tree.refresh_from_db()
        flag.refresh_from_db()
        self.assertEqual(self.tree.moderation_status, "removed")
        self.assertEqual(flag.status, "action_taken")
        self.assertEqual(AuditLog.objects.get().action, "ai_flag_remove")

        self.client.force_login(self.support)
        self.assertEqual(
            self.client.post(
                reverse("ops:ai_flag_action", args=[flag.pk]),
                {"action": "keep", "reason": "Keep."},
            ).status_code,
            403,
        )

    def test_moderator_can_hide_comment_from_public_pages(self):
        comment = Comment.objects.create(
            tree=self.tree, user=self.owner, text="Reported comment."
        )
        comment_type = ContentType.objects.get_for_model(Comment)
        report = Report.objects.create(
            reporter=self.reporter,
            content_type=comment_type,
            object_id=comment.pk,
            reason="harassment",
        )
        self.client.force_login(self.moderator)
        self.client.post(
            reverse("ops:report_action", args=[report.pk]),
            {"action": "hide", "reason": "Harassment confirmed."},
        )

        self.client.force_login(self.reporter)
        response = self.client.get(reverse("tree_detail", args=[self.tree.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Reported comment.")
