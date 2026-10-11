from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Tree(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trees')
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=100, blank=True)  # Make species optional
    country = models.CharField(max_length=100, blank=True)
    division = models.CharField(max_length=100, blank=True)  # state/province/region
    district = models.CharField(max_length=100, blank=True)
    other_location = models.CharField(max_length=255, blank=True)  # for uncommon or specific
    location = models.CharField(max_length=255, blank=True)  # full location string for backward compatibility
    latitude = models.FloatField(blank=True, null=True)  # Added for map
    longitude = models.FloatField(blank=True, null=True) # Added for map
    date_planted = models.DateField()
    image = models.ImageField(upload_to='tree_images/', blank=True, null=True)
    ai_species_guess = models.CharField(max_length=120, blank=True)
    ai_confidence = models.FloatField(null=True, blank=True)
    ai_species_corrected = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    is_dead = models.BooleanField(default=False)
    death_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.species})"


class HealthLog(models.Model):
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='health_logs')
    date = models.DateField()
    health_status = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    is_dead = models.BooleanField(default=False)
    death_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Health on {self.date} - {self.tree.name}"


class Task(models.Model):
    TASK_TYPES = [
        ('Watering', 'Watering'),
        ('Fertilizing', 'Fertilizing'),
        ('Pest Control', 'Pest Control'),
        ('Other', 'Other'),
    ]

    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='tasks')
    task_type = models.CharField(max_length=50, choices=TASK_TYPES)
    scheduled_date = models.DateField()
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.task_type} for {self.tree.name} on {self.scheduled_date}"


class Comment(models.Model):
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Reaction(models.Model):
    REACTION_TYPES = [
        ('planted', 'I Planted Too'),
        ('inspiring', 'Inspiring'),
        ('care', 'Sending Care'),
        ('help', "I'll Help Here"),
        ('insight', 'Data Insight'),
    ]
    INTENSITY_LEVELS = [(1, 'Registered'), (2, 'Committed'), (3, 'Deep')]

    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='impact_reactions')
    reaction = models.CharField(max_length=20, choices=REACTION_TYPES)
    intensity = models.PositiveSmallIntegerField(default=1, choices=INTENSITY_LEVELS)
    note = models.CharField(max_length=140, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'tree', 'reaction'],
                name='unique_user_tree_impact_reaction',
            ),
        ]
        indexes = [
            models.Index(fields=['tree', 'reaction'], name='reaction_tree_type_idx'),
            models.Index(fields=['user', 'created_at'], name='reaction_user_created_idx'),
        ]


class Pledge(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('planted', 'Planted'),
        ('abandoned', 'Abandoned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pledges')
    source_post = models.ForeignKey(
        Tree,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pledges',
    )
    species = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class HelpOffer(models.Model):
    HELP_TYPES = [
        ('water', 'Watering'),
        ('visit', 'Visit'),
        ('donate', 'Donate'),
        ('share', 'Share Location'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='help_offers')
    post = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='help_offers')
    reaction = models.OneToOneField(
        Reaction,
        on_delete=models.CASCADE,
        related_name='help_offer',
    )
    help_type = models.CharField(max_length=40, choices=HELP_TYPES)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)


class UserImpactScore(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='impact_score')
    total_score = models.IntegerField(default=0)
    trees_planted = models.IntegerField(default=0)
    pledges_made = models.IntegerField(default=0)
    help_offered = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_tree_notifications',
    )
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)


class TreeHealthAnalysis(models.Model):
    post = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name='health_analyses')
    score = models.PositiveSmallIntegerField()
    issues = models.JSONField(default=list)
    recommendations = models.JSONField(default=list)
    confidence = models.FloatField()
    model_used = models.CharField(max_length=40)
    image_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['post', 'image_hash', '-created_at'], name='tree_health_cache_idx'),
        ]


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


# Automatically create or update Profile when User is saved
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
