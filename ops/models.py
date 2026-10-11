from django.db import models

# Create your models here.
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ModerationStatus(models.TextChoices):
    VISIBLE = "visible", "Visible"
    HIDDEN = "hidden", "Hidden"
    REMOVED = "removed", "Removed"


class Report(models.Model):
    REASONS = [
        ("spam", "Spam"),
        ("harassment", "Harassment"),
        ("misinformation", "Misinformation"),
        ("nsfw", "Inappropriate content"),
        ("fake_tree", "Fake or misleading tree post"),
        ("other", "Other"),
    ]
    STATUSES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("action_taken", "Action taken"),
        ("dismissed", "Dismissed"),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ops_reports_submitted",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    reason = models.CharField(max_length=20, choices=REASONS)
    details = models.CharField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default="pending", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_reports_reviewed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["reporter", "content_type", "object_id"],
                condition=models.Q(status="pending"),
                name="ops_unique_pending_user_report",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="ops_report_status_created_idx"),
            models.Index(fields=["content_type", "object_id"], name="ops_report_target_idx"),
        ]

    def __str__(self):
        return f"Report #{self.pk} ({self.get_reason_display()})"


class AIFlag(models.Model):
    ACTIONS = [
        ("keep", "Keep"),
        ("warn", "Warn user"),
        ("hide", "Hide content"),
        ("remove", "Remove content"),
    ]
    STATUSES = [
        ("pending", "Pending"),
        ("reviewed", "Reviewed"),
        ("action_taken", "Action taken"),
        ("dismissed", "Dismissed"),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    score = models.PositiveSmallIntegerField()
    reasoning = models.CharField(max_length=1000)
    suggested_action = models.CharField(max_length=12, choices=ACTIONS, default="keep")
    source = models.CharField(max_length=40, default="manual")
    status = models.CharField(max_length=20, choices=STATUSES, default="pending", db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_ai_flags_reviewed",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["status", "-score", "-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(score__gte=0) & models.Q(score__lte=100),
                name="ops_ai_flag_score_0_100",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-score", "-created_at"], name="ops_flag_queue_idx"),
            models.Index(fields=["content_type", "object_id"], name="ops_flag_target_idx"),
        ]

    def __str__(self):
        return f"AI flag #{self.pk} ({self.score}/100)"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ops_actions",
    )
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40, db_index=True)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    target_label = models.CharField(max_length=255)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_actions_received",
    )
    reason = models.CharField(max_length=1000)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor_label}: {self.action} · {self.target_label}"
