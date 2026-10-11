from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.db.models import Count
from django.dispatch import receiver
from django.utils import timezone

from .models import (
    Achievement,
    ChallengeParticipation,
    Comment,
    HelpOffer,
    Pledge,
    Reaction,
    Tree,
    TreeHealthAnalysis,
    UserAchievement,
    UserFollow,
    UserStreak,
)


ACHIEVEMENT_CATALOG = [
    ("first-sprout", "First Sprout", "Share your first tree.", "sprout", "bronze", "tree_count", 1, 10),
    ("green-thumb", "Green Thumb", "Share 10 trees.", "leaf", "silver", "tree_count", 10, 25),
    ("forest-builder", "Forest Builder", "Share 50 trees.", "trees", "gold", "tree_count", 50, 50),
    ("grove-keeper", "Grove Keeper", "Share 100 trees.", "tree-pine", "platinum", "tree_count", 100, 100),
    ("legacy-planter", "Legacy Planter", "Share 500 trees.", "trees", "platinum", "tree_count", 500, 250),
    ("canopy-creator", "Canopy Creator", "Share 1,000 trees.", "forest", "platinum", "tree_count", 1000, 500),
    ("first-follower", "First Follower", "Welcome your first follower.", "user-plus", "bronze", "followers", 1, 10),
    ("community-voice", "Community Voice", "Reach 100 followers.", "users", "silver", "followers", 100, 50),
    ("local-legend", "Local Legend", "Reach 500 followers.", "award", "gold", "followers", 500, 150),
    ("trendsetter", "Trendsetter", "One of your posts receives 1,000 reactions.", "trending-up", "platinum", "max_post_reactions", 1000, 250),
    ("conversation-starter", "Conversation Starter", "Receive 100 comments on your tree posts.", "message-circle", "gold", "post_comments", 100, 100),
    ("mentor", "Mentor", "Inspire 10 planting pledges on your posts.", "graduation-cap", "gold", "post_pledges", 10, 100),
    ("week-warrior", "Week Warrior", "Keep a 7-day posting streak.", "flame", "bronze", "post_streak", 7, 20),
    ("month-master", "Month Master", "Keep a 30-day posting streak.", "flame", "silver", "post_streak", 30, 75),
    ("season-keeper", "Season Keeper", "Keep a 90-day posting streak.", "flame", "gold", "post_streak", 90, 200),
    ("year-of-growth", "Year of Growth", "Keep a 365-day posting streak.", "flame", "platinum", "post_streak", 365, 500),
    ("species-explorer", "Species Explorer", "Share 10 different species.", "scan-search", "bronze", "species_count", 10, 20),
    ("botanist", "Botanist", "Share 25 different species.", "book-open", "silver", "species_count", 25, 60),
    ("encyclopedia", "Encyclopedia", "Share 50 different species.", "library", "gold", "species_count", 50, 150),
    ("pest-detective", "Pest Detective", "Identify 10 tree health issues with AI.", "bug", "silver", "health_issues", 10, 50),
    ("data-contributor", "Data Contributor", "Share 25 data insights.", "database", "silver", "insights", 25, 50),
    ("helper", "Helper", "Offer help 10 times.", "heart-handshake", "bronze", "help_offers", 10, 30),
    ("guardian", "Guardian", "Offer help for 50 struggling trees.", "shield-check", "gold", "struggling_help", 50, 150),
    ("reaction-master", "Reaction Master", "Give 500 impact reactions.", "sparkles", "gold", "reactions", 500, 150),
    ("supporter", "Supporter", "Send care 100 times.", "heart", "silver", "care_reactions", 100, 50),
    ("challenge-regular", "Challenge Regular", "Complete 7 daily garden challenges.", "calendar-check", "silver", "challenges", 7, 50),
]


def current_month_start(day):
    return day.replace(day=1)


@transaction.atomic
def record_activity(user, activity, day=None):
    if activity not in {"login", "post", "reaction"}:
        raise ValueError(f"Unknown streak activity: {activity}")
    day = day or timezone.localdate()
    streak, _ = UserStreak.objects.select_for_update().get_or_create(user=user)
    month = current_month_start(day)
    reset_freeze = streak.freeze_month != month
    if reset_freeze:
        streak.freeze_month = month
        streak.freeze_available = 1

    last_field = f"last_{activity}_date"
    current_field = f"current_{activity}"
    longest_field = f"longest_{activity}"
    last_day = getattr(streak, last_field)
    current = getattr(streak, current_field)
    if last_day == day:
        if reset_freeze:
            streak.save(update_fields=["freeze_month", "freeze_available"])
        return streak
    if last_day is None:
        current = 1
    else:
        gap = (day - last_day).days
        if gap == 1:
            current += 1
        elif gap == 2 and streak.freeze_available:
            current += 1
            streak.freeze_available -= 1
        else:
            current = 1

    setattr(streak, current_field, current)
    setattr(streak, longest_field, max(getattr(streak, longest_field), current))
    setattr(streak, last_field, day)
    streak.save()
    return streak


def achievement_metrics(user):
    trees = Tree.objects.filter(user=user, publication_status="published")
    tree_ids = trees.values("pk")
    issue_count = sum(
        len(issues)
        for issues in TreeHealthAnalysis.objects.filter(post__user=user).values_list(
            "issues", flat=True
        )
    )
    return {
        "tree_count": trees.count(),
        "followers": UserFollow.objects.filter(following=user).count(),
        "max_post_reactions": max(
            (row["reaction_count"] for row in trees.annotate(
                reaction_count=Count("reactions")
            ).values("reaction_count")),
            default=0,
        ),
        "post_comments": Comment.objects.filter(tree__in=tree_ids).count(),
        "post_pledges": Pledge.objects.filter(
            source_post__in=tree_ids, status="planted"
        ).count(),
        "post_streak": getattr(getattr(user, "streak", None), "current_post", 0),
        "species_count": trees.exclude(species="").values("species").distinct().count(),
        "health_issues": issue_count,
        "insights": Reaction.objects.filter(user=user, reaction="insight").count(),
        "help_offers": HelpOffer.objects.filter(user=user).count(),
        "struggling_help": HelpOffer.objects.filter(
            user=user, post__is_dead=True
        ).values("post_id").distinct().count(),
        "reactions": Reaction.objects.filter(user=user).count(),
        "care_reactions": Reaction.objects.filter(user=user, reaction="care").count(),
        "challenges": ChallengeParticipation.objects.filter(
            user=user, challenge__challenge_type="daily"
        ).count(),
    }


@transaction.atomic
def update_achievement_progress(user):
    definitions = Achievement.objects.filter(is_active=True)
    if not definitions.exists():
        return
    metrics = achievement_metrics(user)
    for achievement in definitions:
        metric = achievement.criteria.get("metric")
        threshold = achievement.criteria.get("threshold", 1)
        progress = min(int(metrics.get(metric, 0)), threshold)
        record, _ = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={"progress": progress},
        )
        record.progress = progress
        if progress >= threshold and record.unlocked_at is None:
            record.unlocked_at = timezone.now()
        record.save(update_fields=["progress", "unlocked_at"])


@receiver(user_logged_in)
def record_login_streak(sender, request, user, **kwargs):
    record_activity(user, "login")
    update_achievement_progress(user)
