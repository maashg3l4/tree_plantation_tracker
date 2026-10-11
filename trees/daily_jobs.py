import json
import logging
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .gamification import record_activity, update_achievement_progress
from .models import DailyChallenge, Notification, Tree, UserStreak


logger = logging.getLogger(__name__)

CURATED_CHALLENGES = [
    (
        "Meet a native plant",
        "Find out which tree or plant is native to your area. Share one thing you learned with #NativePlants.",
        "learning",
    ),
    (
        "Give a plant some care",
        "Water, mulch, or check on a tree that needs attention. Share your small act of care with #GardenCare.",
        "care",
    ),
    (
        "Notice new growth",
        "Spend a few minutes observing a plant and share a photo or detail you had not noticed before with #GardenObservation.",
        "observation",
    ),
    (
        "Share a growing tip",
        "Share one practical tip that helped a plant thrive with #GrowTogether.",
        "community",
    ),
]


def _curated_challenge(day):
    title, description, category = CURATED_CHALLENGES[day.toordinal() % len(CURATED_CHALLENGES)]
    return {"title": title, "description": description, "category": category}


def _curated_weekly_challenge(day):
    prompts = [
        ("A week of tiny observations", "Choose one plant and check in on it three times this week. Share one change you noticed.", "observation"),
        ("A week of thoughtful care", "Give one tree a small act of care this week, then share what you did and why.", "care"),
        ("Learn and share", "Learn one new fact about a local plant this week and share it with the community.", "learning"),
    ]
    title, description, category = prompts[day.isocalendar().week % len(prompts)]
    return {"title": title, "description": description, "category": category}


def _generate_challenge(day, challenge_type="daily"):
    if not settings.GEMINI_API_KEY:
        return (
            _curated_weekly_challenge(day) if challenge_type == "weekly"
            else _curated_challenge(day),
            "curated",
        )
    payload = {
        "contents": [{
            "parts": [{
                "text": (
                    f"Create one safe, inclusive, practical {challenge_type} gardening community challenge. "
                    "A daily challenge must take no more than 15 minutes; a weekly challenge should be "
                    "achievable in small steps over a week. Neither may require buying items, land, or "
                    "special equipment. Invite the user to share a post. Return JSON with title "
                    "(under 80 characters), description (under 240 characters), and category "
                    "(observation, care, learning, or community)."
                )
            }]
        }],
        "generationConfig": {
            "temperature": 0.6,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "category": {"type": "STRING"},
                },
                "required": ["title", "description", "category"],
            },
        },
    }
    request = Request(
        f"{settings.GEMINI_API_URL}/models/{settings.GEMINI_VISION_MODEL}:generateContent"
        f"?{urlencode({'key': settings.GEMINI_API_KEY})}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = json.loads(response.read().decode("utf-8"))
        content = "".join(
            part.get("text", "")
            for part in raw["candidates"][0]["content"]["parts"]
        )
        result = json.loads(content)
        allowed_categories = {"observation", "care", "learning", "community"}
        if (
            not isinstance(result.get("title"), str)
            or not 1 <= len(result["title"]) <= 80
            or not isinstance(result.get("description"), str)
            or not 1 <= len(result["description"]) <= 240
            or result.get("category") not in allowed_categories
        ):
            raise ValueError("Gemini returned invalid challenge fields.")
        return result, "gemini"
    except (HTTPError, URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        logger.exception("Daily challenge generation failed; using the curated challenge.")
        return (
            _curated_weekly_challenge(day) if challenge_type == "weekly"
            else _curated_challenge(day),
            "curated",
        )


def ensure_daily_challenge(day=None, challenge_type="daily", generate_with_ai=True):
    day = day or timezone.localdate()
    challenge = DailyChallenge.objects.filter(
        date=day, challenge_type=challenge_type
    ).first()
    if challenge:
        return challenge
    challenge_data, provider = (
        _generate_challenge(day, challenge_type)
        if generate_with_ai
        else (
            _curated_weekly_challenge(day) if challenge_type == "weekly"
            else _curated_challenge(day),
            "curated",
        )
    )
    challenge, _ = DailyChallenge.objects.get_or_create(
        date=day,
        challenge_type=challenge_type,
        defaults={**challenge_data, "generated_by": provider},
    )
    return challenge


@transaction.atomic
def publish_scheduled_posts(now=None):
    now = now or timezone.now()
    scheduled = list(
        Tree.objects.select_for_update().filter(
            publication_status="scheduled", scheduled_publish_at__lte=now
        )
    )
    for tree in scheduled:
        tree.publication_status = "published"
        tree.published_at = now
        tree.save(update_fields=["publication_status", "published_at", "updated_at"])
        record_activity(tree.user, "post", day=timezone.localdate(now))
        update_achievement_progress(tree.user)
    return len(scheduled)


def create_streak_reminders(day=None):
    day = day or timezone.localdate()
    users = UserStreak.objects.select_related("user").filter(
        last_login_date__lte=day - timedelta(days=1)
    )
    created = 0
    for streak in users.iterator():
        already_sent = Notification.objects.filter(
            user=streak.user, notification_type="streak", created_at__date=day
        ).exists()
        if not already_sent:
            inactive_days = (day - streak.last_login_date).days
            if inactive_days >= 7:
                message = "It has been a while since you visited the garden. Come back and see what’s growing."
            elif streak.current_login >= 2:
                message = (
                    f"Keep your {streak.current_login}-day garden login streak growing. "
                    "Stop by today."
                )
            else:
                continue
            Notification.objects.create(
                user=streak.user,
                actor=None,
                notification_type="streak",
                message=message,
            )
            created += 1
    return created


def run_daily_engagement(day=None):
    day = day or timezone.localdate()
    published = publish_scheduled_posts()
    next_day = day + timedelta(days=1)
    challenge = ensure_daily_challenge(next_day, generate_with_ai=True)
    if next_day.weekday() == 0:
        ensure_daily_challenge(next_day, "weekly", generate_with_ai=True)
    reminders = create_streak_reminders(day)
    return {"published_posts": published, "challenge_id": challenge.pk, "reminders": reminders}
