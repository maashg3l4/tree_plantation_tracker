import json
import hashlib
import hmac
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import UserCreationForm
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db import connection
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Case, Count, F, IntegerField, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.db.models.functions import Lower, TruncMonth
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import (
    Comment,
    Achievement,
    ChallengeParticipation,
    DailyChallenge,
    HealthLog,
    HelpOffer,
    Notification,
    Pledge,
    Profile,
    Reaction,
    Tree,
    TreeHashtag,
    TreeHealthAnalysis,
    TreeMedia,
    UserImpactScore,
    UserFollow,
    UserAchievement,
    UserStreak,
)
from .forms import TreeForm, HealthLogForm, TaskForm
from .forms_auth import EmailLoginForm, OnboardingForm, SignupForm
from .forms_profile import ProfileForm, UserForm, PasswordChangeForm
from .impact import refresh_user_impact_score
from .ai_services import AIServiceError, analyze_tree_health, identify_species, image_digest
from .gamification import record_activity, update_achievement_progress


def landing(request):
    from grove.models import Organization, TreeBatch

    tree_totals = TreeBatch.objects.filter(plot__org__is_public=True).aggregate(total=Sum("quantity"))
    return render(
        request,
        "trees/landing.html",
        {
            "community_tree_count": Tree.objects.count(),
            "grove_tree_count": tree_totals["total"] or 0,
            "public_farm_count": Organization.objects.filter(is_public=True).count(),
        },
    )


def signup_step1(request):
    if request.user.is_authenticated:
        return redirect("tree_list")
    return render(request, "registration/signup_step1.html")


def signup_step2(request):
    if request.user.is_authenticated:
        return redirect("tree_list")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = get_user_model().objects.create_user(
            username=f"gardener-{uuid.uuid4().hex[:12]}",
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
        )
        login(request, user)
        request.session["onboarding_incomplete"] = True
        return redirect("onboarding")
    return render(request, "registration/signup_step2.html", {"form": form})


@login_required
def onboarding(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = OnboardingForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
        initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "username": request.user.username if not request.user.username.startswith("gardener-") else "",
            "bio": profile.bio,
            "location": profile.location,
            "interests": profile.interests,
        },
    )
    if request.method == "POST" and form.is_valid():
        request.user.first_name = form.cleaned_data["first_name"].strip()
        request.user.last_name = form.cleaned_data["last_name"].strip()
        request.user.username = form.cleaned_data["username"]
        request.user.save(update_fields=["first_name", "last_name", "username"])
        profile.bio = form.cleaned_data["bio"].strip()
        profile.location = form.cleaned_data["location"].strip()
        profile.interests = form.cleaned_data["interests"]
        if form.cleaned_data["profile_picture"]:
            profile.profile_picture = form.cleaned_data["profile_picture"]
        profile.save()
        request.session.pop("onboarding_incomplete", None)
        return redirect("user_profile", username=request.user.username)
    return render(request, "registration/onboarding.html", {"form": form})


def username_available(request):
    username = request.GET.get("username", "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_-]{3,30}", username):
        return JsonResponse(
            {"available": False, "error": "Use 3–30 letters, numbers, hyphens, or underscores."}
        )
    users = get_user_model().objects.annotate(lower_username=Lower("username")).filter(
        lower_username=username.lower()
    )
    if request.user.is_authenticated:
        users = users.exclude(pk=request.user.pk)
    available = not users.exists()
    return JsonResponse({"available": available})


def password_reset_done(request):
    return render(request, "registration/password_reset_done.html")


def password_reset_complete(request):
    return render(request, "registration/password_reset_complete.html")


def offline_page(request):
    return render(request, "trees/offline.html")


def register(request):
    return redirect("signup_step1")

# Login view
def user_login(request):
    client_key = hashlib.sha256(request.META.get("REMOTE_ADDR", "").encode()).hexdigest()[:24]
    throttle_key = f"login_attempts:{client_key}"
    locked_out = cache.get(throttle_key, 0) >= 10
    form = EmailLoginForm(request, request.POST or None)
    if request.method == "POST" and not locked_out and form.is_valid():
        user = form.get_user()
        login(request, user)
        if form.cleaned_data["remember_me"]:
            request.session.set_expiry(60 * 60 * 24 * 14)
        else:
            request.session.set_expiry(0)
        cache.delete(throttle_key)
        next_url = request.POST.get("next", "")
        if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("tree_list")
    if request.method == "POST" and not locked_out and form.errors:
        cache.set(throttle_key, cache.get(throttle_key, 0) + 1, timeout=15 * 60)
        locked_out = cache.get(throttle_key, 0) >= 10
    return render(
        request,
        "registration/login.html",
        {"form": form, "locked_out": locked_out, "next": request.GET.get("next", "")},
    )

# Logout view
def user_logout(request):
    logout(request)
    return redirect('home')


@login_required
@require_POST
def change_password(request):
    form = DjangoPasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return JsonResponse({"success": True, "message": "Password updated."})
    return JsonResponse({"success": False, "errors": form.errors}, status=400)


def user_profile(request, username):
    profile_user = get_object_or_404(get_user_model(), username__iexact=username)
    profile, _ = Profile.objects.get_or_create(user=profile_user)
    posts = Tree.objects.filter(user=profile_user)
    if not request.user.is_authenticated or request.user.pk != profile_user.pk:
        posts = posts.filter(publication_status="published")
    posts = posts.select_related("user").prefetch_related("media").order_by(
        "-published_at", "-updated_at"
    )
    tab = request.GET.get("tab", "posts")
    is_following = request.user.is_authenticated and UserFollow.objects.filter(
        follower=request.user, following=profile_user
    ).exists()
    context = {
        "profile_user": profile_user,
        "profile": profile,
        "posts": posts,
        "tab": tab if tab in {"posts", "garden", "about"} else "posts",
        "is_following": is_following,
        "post_count": posts.count(),
        "follower_count": profile_user.follower_relationships.count(),
        "following_count": profile_user.following_relationships.count(),
        "tree_count": posts.count(),
        "species_count": posts.exclude(species="").values("species").distinct().count(),
        "streak": UserStreak.objects.filter(user=profile_user).first(),
        "badges": UserAchievement.objects.filter(
            user=profile_user, unlocked_at__isnull=False
        ).select_related("achievement")[:6],
    }
    response = render(request, "profile/public.html", context)
    if not request.user.is_authenticated:
        response["X-Public-Offline-Cacheable"] = "true"
    return response


@login_required
@require_POST
def toggle_follow(request, username):
    target = get_object_or_404(get_user_model(), username__iexact=username)
    if target.pk == request.user.pk:
        return JsonResponse({"success": False, "error": "You cannot follow yourself."}, status=400)
    follow, created = UserFollow.objects.get_or_create(follower=request.user, following=target)
    if created:
        Notification.objects.create(
            user=target,
            actor=request.user,
            tree=None,
            notification_type="follow",
            message=f"{request.user.username} started following you.",
        )
        update_achievement_progress(target)
    else:
        follow.delete()
    return JsonResponse(
        {
            "success": True,
            "following": created,
            "follower_count": target.follower_relationships.count(),
        }
    )


def follow_list(request, username, relation):
    profile_user = get_object_or_404(get_user_model(), username__iexact=username)
    if relation == "followers":
        people = get_user_model().objects.filter(following_relationships__following=profile_user)
    else:
        people = get_user_model().objects.filter(following_relationships__follower=profile_user)
    return render(
        request,
        "profile/follow_list.html",
        {"profile_user": profile_user, "people": people.distinct(), "relation": relation},
    )


@login_required
def notification_center(request):
    notifications = request.user.notifications.select_related("actor", "tree").order_by("-created_at")
    unread_count = notifications.filter(is_read=False).count()
    return render(
        request,
        "notifications/center.html",
        {"notifications": notifications[:100], "unread_count": unread_count},
    )


@login_required
@require_POST
def mark_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("notifications")


def discover(request):
    people = get_user_model().objects.all()
    if request.user.is_authenticated:
        people = people.exclude(pk=request.user.pk)
        already_following = UserFollow.objects.filter(follower=request.user).values("following_id")
        people = people.exclude(pk__in=already_following)
    people = people.select_related("profile").order_by("-date_joined")[:12]
    trees = Tree.objects.filter(publication_status="published").select_related("user").prefetch_related("media")
    species = request.GET.get("species", "").strip()
    location = request.GET.get("location", "").strip()
    if species:
        trees = trees.filter(species__iexact=species)
    if location:
        trees = trees.filter(
            Q(country__icontains=location)
            | Q(division__icontains=location)
            | Q(district__icontains=location)
            | Q(location__icontains=location)
        )
    if request.GET.get("sort") == "species":
        trees = trees.order_by("species", "-published_at")
    else:
        trees = trees.order_by("-published_at", "-updated_at")
    trees = trees[:30]
    species_options = (
        Tree.objects.filter(publication_status="published")
        .exclude(species="")
        .values_list("species", flat=True)
        .distinct()
        .order_by("species")
    )
    location_options = (
        Tree.objects.filter(publication_status="published")
        .exclude(district="")
        .values_list("district", flat=True)
        .distinct()
        .order_by("district")
    )
    return render(
        request,
        "trees/discover.html",
        {
            "people": people,
            "trees": trees,
            "species_options": species_options,
            "location_options": location_options,
            "selected_species": species,
            "selected_location": location,
        },
    )


def search(request):
    query = request.GET.get("q", "").strip()[:100]
    users = get_user_model().objects.none()
    trees = Tree.objects.none()
    if query:
        users = get_user_model().objects.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        ).select_related("profile")[:20]
        posts = Tree.objects.filter(publication_status="published").select_related(
            "user"
        ).prefetch_related("hashtags", "media")
        if query.startswith("#"):
            tag = query[1:].casefold()
            posts = posts.filter(hashtags__tag__iexact=tag)
        elif connection.vendor == "postgresql":
            vector = (
                SearchVector("name", weight="A")
                + SearchVector("species", weight="A")
                + SearchVector("caption", weight="B")
                + SearchVector("location", weight="C")
                + SearchVector("district", weight="C")
            )
            search_query = SearchQuery(query, search_type="websearch")
            posts = posts.annotate(
                search_document=vector,
                relevance=SearchRank(vector, search_query),
            ).filter(
                Q(search_document=search_query)
                | Q(hashtags__tag__icontains=query)
            ).order_by("-relevance", "-published_at")
        else:
            posts = posts.filter(
                Q(name__icontains=query)
                | Q(species__icontains=query)
                | Q(caption__icontains=query)
                | Q(location__icontains=query)
                | Q(country__icontains=query)
                | Q(district__icontains=query)
                | Q(hashtags__tag__icontains=query)
            ).distinct()
        if query.startswith("#"):
            posts = posts.distinct()
        if not (connection.vendor == "postgresql" and not query.startswith("#")):
            posts = posts.order_by("-published_at", "-updated_at")
        trees = posts[:30]
    return render(
        request,
        "trees/search.html",
        {"query": query, "people": users, "trees": trees},
    )


@login_required
def achievements(request):
    update_achievement_progress(request.user)
    unlocked = UserAchievement.objects.filter(
        user=request.user, unlocked_at__isnull=False
    ).select_related("achievement")
    locked = Achievement.objects.filter(is_active=True).exclude(
        pk__in=unlocked.values("achievement_id")
    )
    records = {
        record.achievement_id: record.progress
        for record in UserAchievement.objects.filter(user=request.user)
    }
    locked = [
        {"achievement": item, "progress": records.get(item.pk, 0)}
        for item in locked
    ]
    return render(
        request,
        "trees/achievements.html",
        {"unlocked": unlocked, "locked": locked},
    )


@login_required
def leaderboard(request):
    leaders = (
        get_user_model().objects.select_related("profile")
        .annotate(
            impact_points=Coalesce(F("impact_score__total_score"), Value(0)),
            achievement_points=Coalesce(
                Sum(
                    Case(
                        When(
                            achievements__unlocked_at__isnull=False,
                            then=F("achievements__achievement__points"),
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0),
            ),
        )
        .annotate(combined_score=F("impact_points") + F("achievement_points"))
        .order_by("-combined_score", "username")[:50]
    )
    return render(request, "trees/leaderboard.html", {"leaders": leaders})


@login_required
def garden_insights(request):
    user_trees = Tree.objects.filter(user=request.user, publication_status="published")
    since = timezone.now() - timedelta(days=180)
    monthly_counts = list(
        user_trees.filter(published_at__gte=since)
        .annotate(month=TruncMonth("published_at"))
        .values("month")
        .annotate(total=Count("pk"))
        .order_by("month")
    )
    max_monthly = max((row["total"] for row in monthly_counts), default=0)
    month_rows = [
        {
            **row,
            "percent": max(8, round(row["total"] * 100 / max_monthly))
            if max_monthly else 0,
        }
        for row in monthly_counts
    ]
    species = (
        user_trees.exclude(species="")
        .values("species")
        .annotate(total=Count("pk"))
        .order_by("-total", "species")[:5]
    )
    streak, _ = UserStreak.objects.get_or_create(user=request.user)
    return render(
        request,
        "trees/insights.html",
        {
            "tree_count": user_trees.count(),
            "species_count": user_trees.exclude(species="").values("species").distinct().count(),
            "reaction_count": Reaction.objects.filter(tree__in=user_trees).count(),
            "follower_count": UserFollow.objects.filter(following=request.user).count(),
            "month_rows": month_rows,
            "top_species": species,
            "streak": streak,
        },
    )


def get_daily_challenge(day=None, challenge_type="daily"):
    from .daily_jobs import ensure_daily_challenge

    return ensure_daily_challenge(
        day, challenge_type=challenge_type, generate_with_ai=False
    )


def daily_challenges(request):
    challenge = get_daily_challenge()
    week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
    weekly_challenge = get_daily_challenge(week_start, challenge_type="weekly")
    completed = (
        ChallengeParticipation.objects.filter(challenge=challenge, user=request.user).exists()
        if request.user.is_authenticated
        else False
    )
    weekly_completed = (
        ChallengeParticipation.objects.filter(
            challenge=weekly_challenge, user=request.user
        ).exists()
        if request.user.is_authenticated
        else False
    )
    recent = DailyChallenge.objects.filter(challenge_type="daily").prefetch_related(
        "participants"
    ).order_by("-date")[:7]
    return render(
        request,
        "trees/challenges.html",
        {
            "challenge": challenge,
            "completed": completed,
            "weekly_challenge": weekly_challenge,
            "weekly_completed": weekly_completed,
            "recent_challenges": recent,
        },
    )


@login_required
@require_POST
def complete_daily_challenge(request, challenge_id):
    challenge = get_object_or_404(DailyChallenge, pk=challenge_id)
    participation, created = ChallengeParticipation.objects.get_or_create(
        challenge=challenge,
        user=request.user,
        defaults={"note": request.POST.get("note", "").strip()[:240]},
    )
    if created:
        update_achievement_progress(request.user)
    return redirect("daily_challenges")


@require_GET
def daily_engagement_cron(request):
    secret = getattr(settings, "CRON_SECRET", "")
    provided = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(provided, f"Bearer {secret}"):
        return JsonResponse({"success": False, "error": "Unauthorized."}, status=401)
    from .daily_jobs import run_daily_engagement

    return JsonResponse({"success": True, **run_daily_engagement()})


def tree_list(request):
    trees = Tree.objects.filter(publication_status="published").select_related(
        'user', 'user__profile'
    ).prefetch_related(
        Prefetch('reactions', queryset=Reaction.objects.select_related('user').order_by('-created_at')),
        Prefetch('comments', queryset=Comment.objects.select_related('user').order_by('created_at')),
        Prefetch('media'),
        Prefetch('health_logs', queryset=HealthLog.objects.order_by('-date', '-pk')),
        Prefetch(
            'health_analyses',
            queryset=TreeHealthAnalysis.objects.order_by('-created_at'),
            to_attr='prefetched_health_analyses',
        ),
    ).annotate(
        inspiration_boost=Sum(
            Case(
                When(reactions__reaction='inspiring', then=F('reactions__intensity')),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    ).order_by('-inspiration_boost', '-updated_at')
    for tree in trees:
        profile = getattr(tree.user, 'profile', None)
        tree.profile_picture = profile.profile_picture if profile else None
        tree.reaction_counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
        tree.user_reaction_state = {}
        for reaction in tree.reactions.all():
            tree.reaction_counts[reaction.reaction] += 1
            if request.user.is_authenticated and reaction.user_id == request.user.id:
                tree.user_reaction_state[reaction.reaction] = reaction.intensity
        tree.reaction_state = ','.join(
            f'{reaction_type}:{intensity}'
            for reaction_type, intensity in tree.user_reaction_state.items()
        )
        tree.latest_reactions = list(tree.reactions.all())[:5]
        tree.latest_health_analysis = next(iter(tree.prefetched_health_analyses), None)
        tree.health_issues_json = json.dumps(tree.latest_health_analysis.issues) if tree.latest_health_analysis else '[]'
        tree.health_recommendations_json = json.dumps(
            tree.latest_health_analysis.recommendations
        ) if tree.latest_health_analysis else '[]'
        latest_health = next(iter(tree.health_logs.all()), None)
        tree.has_health_data = bool(latest_health)
        if tree.is_dead or (latest_health and latest_health.is_dead):
            tree.feed_status = 'struggling'
        elif latest_health and any(
            marker in latest_health.health_status.lower()
            for marker in ('struggl', 'poor', 'critical', 'declin', 'dead')
        ):
            tree.feed_status = 'struggling'
        elif latest_health and any(
            marker in latest_health.health_status.lower()
            for marker in ('thriv', 'healthy', 'excellent', 'good')
        ):
            tree.feed_status = 'thriving'
        else:
            tree.feed_status = 'unknown'
    response = render(request, 'trees/tree_list.html', {
        'trees': trees,
        'impact_reaction_types': Reaction.REACTION_TYPES,
    })
    if not request.user.is_authenticated:
        response["X-Public-Offline-Cacheable"] = "true"
    return response


@login_required
@require_POST
def identify_tree_species(request):
    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'success': False, 'error': 'Choose a tree image first.'}, status=400)
    try:
        result = identify_species(image)
    except AIServiceError as error:
        return JsonResponse({'success': False, 'error': str(error)}, status=error.status_code)
    if result['predictions']:
        predictions = request.session.get('species_identifications', {})
        predictions[result['image_hash']] = result
        request.session['species_identifications'] = predictions
    return JsonResponse({'success': True, **result})


@login_required
@require_POST
def analyze_tree(request, pk):
    tree = get_object_or_404(Tree, pk=pk)
    if tree.user_id != request.user.id:
        return JsonResponse(
            {'success': False, 'error': 'Only the tree owner can request a health analysis.'},
            status=403,
        )
    if not tree.image:
        return JsonResponse({'success': False, 'error': 'This tree has no image to analyze.'}, status=400)
    try:
        with tree.image.open('rb') as image:
            image_hash = image_digest(image)
        analysis = None
        if request.POST.get('force') != '1':
            analysis = tree.health_analyses.filter(image_hash=image_hash).first()
        if analysis is None:
            with tree.image.open('rb') as image:
                result = analyze_tree_health(image)
            analysis = TreeHealthAnalysis.objects.create(post=tree, **result)
            update_achievement_progress(request.user)
    except AIServiceError as error:
        return JsonResponse({'success': False, 'error': str(error)}, status=error.status_code)
    return JsonResponse({
        'success': True,
        'analysis': {
            'score': analysis.score,
            'issues': analysis.issues,
            'recommendations': analysis.recommendations,
            'confidence': analysis.confidence,
            'model_used': analysis.model_used,
            'created_at': analysis.created_at.isoformat(),
        },
    })

@login_required
def add_tree(request):
    if request.method == 'POST':
        form = TreeForm(request.POST, request.FILES)
        if form.is_valid():
            tree = form.save(commit=False)
            tree.user = request.user
            image = form.cleaned_data.get('image')
            predictions = request.session.get('species_identifications', {})
            prediction = predictions.pop(image_digest(image), None) if image else None
            if prediction:
                guess = prediction['predictions'][0]
                tree.ai_species_guess = guess['name'][:120]
                tree.ai_confidence = guess.get('confidence')
                tree.ai_species_corrected = (
                    tree.species.strip().casefold() != guess['name'].strip().casefold()
                )
                request.session['species_identifications'] = predictions
            if form.cleaned_data["save_as_draft"]:
                tree.publication_status = "draft"
                tree.scheduled_publish_at = None
            elif form.cleaned_data["scheduled_publish_at"]:
                tree.publication_status = "scheduled"
                tree.scheduled_publish_at = form.cleaned_data["scheduled_publish_at"]
            else:
                tree.publication_status = "published"
                tree.published_at = timezone.now()
            tree.save()
            position = 1
            for upload in form.cleaned_data["extra_images"]:
                TreeMedia.objects.create(
                    tree=tree, file=upload, media_type="image", position=position
                )
                position += 1
            video = form.cleaned_data["video"]
            if video:
                TreeMedia.objects.create(
                    tree=tree, file=video, media_type="video", position=position
                )
            TreeHashtag.objects.filter(tree=tree).delete()
            tags = set(re.findall(r"(?<!\w)#([\w-]{1,50})", tree.caption.casefold()))
            TreeHashtag.objects.bulk_create(
                [TreeHashtag(tree=tree, tag=tag) for tag in sorted(tags)]
            )
            if tree.publication_status == "published":
                record_activity(request.user, "post")
            update_achievement_progress(request.user)
            return redirect(
                "tree_list" if tree.publication_status == "published"
                else "user_profile", **(
                    {} if tree.publication_status == "published"
                    else {"username": request.user.username}
                )
            )
    else:
        form = TreeForm()
    return render(request, 'trees/add_tree.html', {'form': form})

@login_required
def tree_detail(request, pk):
    visible_trees = Tree.objects.filter(publication_status="published")
    if request.user.is_authenticated:
        visible_trees = Tree.objects.filter(
            Q(publication_status="published") | Q(user=request.user)
        )
    tree = get_object_or_404(visible_trees, pk=pk)
    health_logs = tree.health_logs.all().order_by('-date')
    tasks = tree.tasks.all().order_by('scheduled_date')
    comments = tree.comments.select_related('user').order_by('created_at')
    reactions = tree.reactions.select_related('user').order_by('-created_at')
    tree.latest_health_analysis = tree.health_analyses.first()
    tree.health_issues_json = json.dumps(tree.latest_health_analysis.issues) if tree.latest_health_analysis else '[]'
    tree.health_recommendations_json = json.dumps(
        tree.latest_health_analysis.recommendations
    ) if tree.latest_health_analysis else '[]'
    tree.reaction_counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
    tree.user_reaction_state = {}
    for reaction in reactions:
        tree.reaction_counts[reaction.reaction] += 1
        if reaction.user_id == request.user.id:
            tree.user_reaction_state[reaction.reaction] = reaction.intensity
    tree.reaction_state = ','.join(
        f'{reaction_type}:{intensity}'
        for reaction_type, intensity in tree.user_reaction_state.items()
    )
    tree.latest_reactions = list(reactions[:5])
    latest_health = health_logs.first()
    tree.has_health_data = bool(latest_health)
    if tree.is_dead or (latest_health and latest_health.is_dead):
        tree.feed_status = 'struggling'
    elif latest_health and any(
        marker in latest_health.health_status.lower()
        for marker in ('struggl', 'poor', 'critical', 'declin', 'dead')
    ):
        tree.feed_status = 'struggling'
    elif latest_health and any(
        marker in latest_health.health_status.lower()
        for marker in ('thriv', 'healthy', 'excellent', 'good')
    ):
        tree.feed_status = 'thriving'
    else:
        tree.feed_status = 'unknown'
    health_form = HealthLogForm()
    task_form = TaskForm()
    # Handle comments
    if request.method == 'POST' and request.POST.get('form_type') == 'comment':
        text = request.POST.get('comment_text')
        if text:
            Comment.objects.create(tree=tree, user=request.user, text=text)
            return redirect('tree_detail', pk=tree.pk)
    if request.method == 'POST':
        if request.POST.get('form_type') == 'health':
            health_form = HealthLogForm(request.POST)
            if health_form.is_valid():
                log = health_form.save(commit=False)
                log.tree = tree
                # If tree is dead, propagate to health log
                if tree.is_dead:
                    log.is_dead = True
                    log.death_reason = tree.death_reason
                log.save()
                return redirect('tree_detail', pk=tree.pk)
        elif request.POST.get('form_type') == 'task':
            task_form = TaskForm(request.POST)
            if task_form.is_valid():
                task = task_form.save(commit=False)
                task.tree = tree
                task.save()
                return redirect('tree_detail', pk=tree.pk)
        elif request.POST.get('form_type') == 'mark_dead':
            reason = request.POST.get('death_reason')
            tree.is_dead = True
            tree.death_reason = reason
            tree.save()
            # Propagate to health log
            from .models import HealthLog
            HealthLog.objects.create(
                tree=tree,
                date=tree.updated_at.date(),
                health_status='Dead',
                is_dead=True,
                death_reason=reason
            )
            return redirect('tree_detail', pk=tree.pk)
    return render(request, 'trees/tree_detail.html', {
        'tree': tree,
        'health_logs': health_logs,
        'tasks': tasks,
        'health_form': health_form,
        'task_form': task_form,
        'comments': comments,
        'reactions': reactions,
        'impact_reaction_types': Reaction.REACTION_TYPES,
    })

@login_required
def mark_task_completed(request, task_id):
    if request.method == 'POST':
        from .models import Task
        task = Task.objects.get(id=task_id)
        task.completed = True
        task.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    profile, created = Profile.objects.get_or_create(user=request.user)
    impact_score, _ = UserImpactScore.objects.get_or_create(user=request.user)
    user_form = UserForm(instance=request.user, profile=profile)
    profile_form = ProfileForm(instance=profile)
    password_form = PasswordChangeForm()
    message = None
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            previous_username = request.user.username
            user_form = UserForm(request.POST, instance=request.user, profile=profile)
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                if request.user.username != previous_username:
                    profile.username_changed_at = timezone.now()
                    profile.save(update_fields=['username_changed_at'])
                message = 'Profile updated successfully.'
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.POST)
            if password_form.is_valid():
                old = password_form.cleaned_data['old_password']
                new1 = password_form.cleaned_data['new_password1']
                new2 = password_form.cleaned_data['new_password2']
                if not request.user.check_password(old):
                    password_form.add_error('old_password', 'Old password is incorrect.')
                elif new1 != new2:
                    password_form.add_error('new_password2', 'Passwords do not match.')
                else:
                    request.user.set_password(new1)
                    request.user.save()
                    update_session_auth_hash(request, request.user)
                    message = 'Password changed successfully.'
    return render(request, 'registration/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'profile': profile,
        'message': message,
        'impact_score': impact_score,
        'pledges': Pledge.objects.filter(user=request.user).select_related('source_post').order_by('-created_at'),
        'notifications': Notification.objects.filter(user=request.user).select_related('actor', 'tree').order_by('-created_at')[:10],
    })


@login_required
@require_POST
def update_pledge_status(request, pledge_id):
    pledge = get_object_or_404(Pledge, pk=pledge_id, user=request.user)
    source_post = pledge.source_post
    status = request.POST.get('status')
    if status not in ('planted', 'abandoned'):
        return JsonResponse({'success': False, 'error': 'Invalid pledge status.'}, status=400)
    with transaction.atomic():
        pledge.status = status
        pledge.save(update_fields=['status'])
        refresh_user_impact_score(request.user)
        if status == 'planted' and source_post:
            update_achievement_progress(source_post.user)
    return redirect('profile')


@require_POST
def react_or_comment(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'You must be logged in to react or comment.'}, status=403)
    tree_id = request.POST.get('tree_id')
    form_type = request.POST.get('form_type')
    if not tree_id or not form_type:
        return JsonResponse({'success': False, 'error': 'Missing tree_id or form_type.'}, status=400)
    tree = get_object_or_404(Tree, pk=tree_id)
    if form_type == 'react':
        reaction_type = request.POST.get('reaction_type')
        if reaction_type not in dict(Reaction.REACTION_TYPES):
            return JsonResponse({'success': False, 'error': 'Invalid reaction_type.'}, status=400)
        try:
            intensity = int(request.POST.get('intensity', '1'))
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Intensity must be 1, 2, or 3.'}, status=400)
        if intensity not in dict(Reaction.INTENSITY_LEVELS):
            return JsonResponse({'success': False, 'error': 'Intensity must be 1, 2, or 3.'}, status=400)
        note = request.POST.get('note', '')
        if len(note) > 140:
            return JsonResponse({'success': False, 'error': 'Reaction notes must be 140 characters or fewer.'}, status=400)

        help_type = request.POST.get('help_type', 'water')
        help_message = request.POST.get('help_message', '')
        if reaction_type == 'help' and help_type not in dict(HelpOffer.HELP_TYPES):
            return JsonResponse({'success': False, 'error': 'Invalid help type.'}, status=400)
        if len(help_message) > 1000:
            return JsonResponse({'success': False, 'error': 'Help messages must be 1000 characters or fewer.'}, status=400)

        with transaction.atomic():
            reaction, _ = Reaction.objects.update_or_create(
                tree=tree,
                user=request.user,
                reaction=reaction_type,
                defaults={'intensity': intensity, 'note': note},
            )
            record_activity(request.user, "reaction")
            if reaction_type == 'planted':
                pledge, pledge_created = Pledge.objects.get_or_create(
                    user=request.user,
                    source_post=tree,
                    defaults={'species': tree.species},
                )
                if pledge_created and tree.user_id != request.user.id:
                    Notification.objects.create(
                        user=tree.user,
                        actor=request.user,
                        tree=tree,
                        message=f'{request.user.username} pledged to plant a tree like yours.',
                    )
            elif reaction_type == 'help':
                HelpOffer.objects.update_or_create(
                    reaction=reaction,
                    defaults={
                        'user': request.user,
                        'post': tree,
                        'help_type': help_type,
                        'message': help_message,
                    },
                )
            refresh_user_impact_score(request.user)
            update_achievement_progress(request.user)
            if tree.user_id != request.user.id:
                update_achievement_progress(tree.user)

        counts = {reaction_type: 0 for reaction_type, _ in Reaction.REACTION_TYPES}
        for item in tree.reactions.values('reaction').annotate(count=Count('pk')):
            counts[item['reaction']] = item['count']
        timeline = [
            {
                'username': item.user.username,
                'reaction': item.get_reaction_display(),
                'reaction_type': item.reaction,
                'note': item.note,
                'created_at': item.created_at.isoformat(),
            }
            for item in tree.reactions.select_related('user').order_by('-created_at')[:5]
        ]
        return JsonResponse({'success': True, 'counts': counts, 'timeline': timeline})
    if form_type == 'comment':
        text = request.POST.get('comment_text', '').strip()
        if not text:
            return JsonResponse({'success': False, 'error': 'Missing comment_text.'}, status=400)
        Comment.objects.create(tree=tree, user=request.user, text=text)
        update_achievement_progress(tree.user)
        comments = tree.comments.select_related('user').order_by('created_at')
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'trees/partials/comment_list.html', {'comments': comments})
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

@login_required
def delete_tree(request, pk):
    tree = get_object_or_404(Tree, pk=pk)
    if tree.user != request.user:
        return JsonResponse({'success': False, 'error': 'You do not have permission to delete this tree.'}, status=403)
    if request.method == 'POST':
        affected_user_ids = set(tree.reactions.values_list('user_id', flat=True))
        affected_user_ids.update(tree.help_offers.values_list('user_id', flat=True))
        with transaction.atomic():
            tree.delete()
            for affected_user in get_user_model().objects.filter(pk__in=affected_user_ids):
                refresh_user_impact_score(affected_user)
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)
