from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Tree(models.Model):
    PUBLICATION_STATUS = [
        ("published", "Published"),
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trees')
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=100, blank=True)  # Make species optional
    caption = models.TextField(blank=True)
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
    publication_status = models.CharField(
        max_length=12, choices=PUBLICATION_STATUS, default="published", db_index=True
    )
    scheduled_publish_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_dead = models.BooleanField(default=False)
    death_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.species})"


class TreeMedia(models.Model):
    MEDIA_TYPES = [("image", "Image"), ("video", "Video")]
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="tree_media/%Y/%m/")
    media_type = models.CharField(max_length=8, choices=MEDIA_TYPES)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "pk"]


class TreeHashtag(models.Model):
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE, related_name="hashtags")
    tag = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["tree", "tag"], name="unique_tree_hashtag"),
        ]
        indexes = [models.Index(fields=["tag"], name="tree_hashtag_tag_idx")]


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
    NOTIFICATION_TYPES = [
        ('reaction', 'Reaction'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('mention', 'Mention'),
        ('system', 'System'),
        ('streak', 'Streak reminder'),
        ('challenge', 'Challenge'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='sent_tree_notifications',
        null=True,
        blank=True,
    )
    tree = models.ForeignKey(
        Tree, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True
    )
    message = models.CharField(max_length=255)
    notification_type = models.CharField(
        max_length=20, choices=NOTIFICATION_TYPES, default='reaction'
    )
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
    ACCOUNT_TYPES = [("personal", "Personal"), ("business", "Business / Farm")]
    GARDEN_INTERESTS = [
        ("trees", "Trees"),
        ("vegetables", "Vegetables"),
        ("flowers", "Flowers"),
        ("herbs", "Herbs"),
        ("indoor", "Indoor plants"),
        ("bonsai", "Bonsai"),
        ("succulents", "Succulents"),
        ("fruit", "Fruit trees"),
        ("organic", "Organic farming"),
        ("other", "Other"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='personal')
    cover_image = models.ImageField(upload_to='profile_covers/', blank=True)
    bio = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(max_length=200, blank=True)
    social_links = models.JSONField(default=list, blank=True)
    interests = models.JSONField(default=list, blank=True)
    language = models.CharField(
        max_length=2, choices=[("en", "English"), ("bn", "বাংলা")], default="en"
    )
    is_verified = models.BooleanField(default=False)
    username_changed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class UserFollow(models.Model):
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following_relationships'
    )
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='follower_relationships'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['follower', 'following'], name='unique_user_follow'
            ),
            models.CheckConstraint(
                check=~models.Q(follower=models.F('following')), name='prevent_self_follow'
            ),
        ]
        ordering = ['-created_at']


class Achievement(models.Model):
    TIERS = [
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
    ]

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=240)
    icon = models.CharField(max_length=40, default="sprout")
    tier = models.CharField(max_length=12, choices=TIERS, default="bronze")
    criteria = models.JSONField(default=dict)
    points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["points", "name"]

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="achievements")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="unlocks")
    progress = models.PositiveIntegerField(default=0)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "achievement"], name="unique_user_achievement"),
        ]
        ordering = ["-unlocked_at", "achievement__points"]


class UserStreak(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="streak")
    current_login = models.PositiveIntegerField(default=0)
    longest_login = models.PositiveIntegerField(default=0)
    current_post = models.PositiveIntegerField(default=0)
    longest_post = models.PositiveIntegerField(default=0)
    current_reaction = models.PositiveIntegerField(default=0)
    longest_reaction = models.PositiveIntegerField(default=0)
    freeze_available = models.PositiveSmallIntegerField(default=1)
    freeze_month = models.DateField(null=True, blank=True)
    last_login_date = models.DateField(null=True, blank=True)
    last_post_date = models.DateField(null=True, blank=True)
    last_reaction_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Streaks for {self.user.username}"


class DailyChallenge(models.Model):
    CHALLENGE_TYPES = [("daily", "Daily"), ("weekly", "Weekly")]

    date = models.DateField()
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300)
    category = models.CharField(max_length=40, default="garden")
    challenge_type = models.CharField(
        max_length=8, choices=CHALLENGE_TYPES, default="daily"
    )
    generated_by = models.CharField(max_length=40, default="curated")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "challenge_type"], name="unique_challenge_period"
            ),
        ]


class ChallengeParticipation(models.Model):
    challenge = models.ForeignKey(
        DailyChallenge, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="challenge_participations"
    )
    completed_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=240, blank=True)
    post = models.ForeignKey(
        Tree, on_delete=models.SET_NULL, null=True, blank=True, related_name="challenge_entries"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["challenge", "user"], name="unique_user_daily_challenge"
            ),
        ]


# Automatically create or update Profile when User is saved
@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
