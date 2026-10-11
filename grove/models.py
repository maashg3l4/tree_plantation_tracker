import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


def new_batch_code():
    return uuid.uuid4().hex


class Organization(models.Model):
    ORG_TYPES = [
        ("farm", "Farm"),
        ("nursery", "Nursery"),
        ("timber", "Timber Company"),
        ("plantation", "Plantation Company"),
        ("coop", "Cooperative"),
        ("ngo", "NGO"),
        ("govt", "Government"),
        ("corporate", "Corporate CSR"),
    ]

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=200)
    org_type = models.CharField(max_length=20, choices=ORG_TYPES, default="farm")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_organizations",
    )
    logo = models.ImageField(upload_to="orgs/logos/", blank=True)
    cover_image = models.ImageField(upload_to="orgs/covers/", blank=True)
    description = models.TextField(blank=True)
    country = models.CharField(max_length=60, default="Bangladesh")
    region = models.CharField(max_length=120, blank=True)
    total_area_hectares = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    is_public = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "grove"
            candidate = base_slug
            suffix = 2
            while Organization.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    ROLES = [
        ("owner", "Owner"),
        ("manager", "Manager"),
        ("worker", "Worker"),
        ("viewer", "Viewer"),
    ]

    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "user"], name="unique_grove_org_member")
        ]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} — {self.org} ({self.role})"


class Plot(models.Model):
    org = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="plots")
    name = models.CharField(max_length=120)
    boundary = models.JSONField(default=dict)
    area_hectares = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    soil_type = models.CharField(max_length=60, blank=True)
    irrigation = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["org", "name"], name="unique_grove_plot_name")
        ]

    def __str__(self):
        return f"{self.name} — {self.org.name}"


class TreeBatch(models.Model):
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="batches")
    species = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    planted_date = models.DateField()
    spacing_m = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    source_nursery = models.CharField(max_length=200, blank=True)
    qr_batch_code = models.CharField(max_length=40, unique=True, default=new_batch_code)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tree_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-planted_date", "-created_at"]

    def __str__(self):
        return f"{self.quantity} {self.species} — {self.plot.name}"


class Task(models.Model):
    PRIORITIES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]
    TASK_TYPES = [
        ("water", "Water"),
        ("fertilize", "Fertilize"),
        ("prune", "Prune"),
        ("pest", "Pest Control"),
        ("harvest", "Harvest"),
        ("inspect", "Inspect"),
        ("other", "Other"),
    ]

    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="tasks")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grove_tasks",
    )
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    title = models.CharField(max_length=200)
    notes = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITIES, default="normal")
    due_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True)
    proof_image = models.ImageField(upload_to="tasks/proofs/", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_grove_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["completed_at", "due_date", "-priority"]

    def __str__(self):
        return f"{self.title} — {self.plot.name}"


class PlotHealthSnapshot(models.Model):
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="health_snapshots")
    ndvi = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("-1")), MaxValueValidator(Decimal("1"))],
    )
    source = models.CharField(max_length=80, default="manual")
    notes = models.CharField(max_length=240, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.plot.name}: NDVI {self.ndvi}"


class PlotHealthAnalysis(models.Model):
    plot = models.ForeignKey(Plot, on_delete=models.CASCADE, related_name="ai_health_analyses")
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    issues = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    confidence = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    model_used = models.CharField(max_length=40)
    image_hash = models.CharField(max_length=64)
    analyzed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["plot", "image_hash"], name="unique_plot_health_image")
        ]

    def __str__(self):
        return f"{self.plot.name}: health {self.score}/100"
