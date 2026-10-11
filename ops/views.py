from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.urls import reverse

from trees.models import Comment, Notification, Reaction, Tree

from .forms import AIFlagActionForm, ModerationActionForm, ReportForm
from .models import AIFlag, AuditLog, Report
from .permissions import has_ops_role, require_role


REPORTABLE_MODELS = {
    "tree": Tree,
    "comment": Comment,
    "user": get_user_model(),
}
CONTENT_MODELS = (Tree, Comment)


def _get_reportable_object(kind, object_id):
    model = REPORTABLE_MODELS.get(kind)
    if model is None:
        raise Http404
    obj = get_object_or_404(model, pk=object_id)
    if isinstance(obj, Tree) and (
        obj.publication_status != "published" or obj.moderation_status != "visible"
    ):
        raise Http404
    if isinstance(obj, Comment) and (
        obj.tree.publication_status != "published"
        or obj.tree.moderation_status != "visible"
        or obj.moderation_status != "visible"
    ):
        raise Http404
    return obj


def _content_owner(target):
    if isinstance(target, Tree):
        return target.user
    if isinstance(target, Comment):
        return target.user
    if hasattr(target, "pk") and target.__class__ is get_user_model():
        return target
    return None


def _target_label(target):
    if isinstance(target, Tree):
        return f"Tree post: {target.name}"[:255]
    if isinstance(target, Comment):
        return f"Comment on {target.tree.name}"[:255]
    if hasattr(target, "username"):
        return f"User: {target.username}"[:255]
    return f"{target.__class__.__name__}: {target}"[:255]


def _target_url(target):
    if isinstance(target, Tree):
        return reverse("tree_detail", args=[target.pk])
    if isinstance(target, Comment):
        return reverse("tree_detail", args=[target.tree_id])
    return reverse("user_profile", args=[target.username])


def _target_snapshot(target):
    if isinstance(target, Tree):
        return {
            "name": target.name,
            "species": target.species,
            "caption": target.caption[:1000],
            "moderation_status": target.moderation_status,
        }
    if isinstance(target, Comment):
        return {
            "text": target.text[:1000],
            "tree_id": target.tree_id,
            "moderation_status": target.moderation_status,
        }
    if hasattr(target, "username"):
        return {"username": target.username, "is_active": target.is_active}
    return {}


def _apply_action(target, action, actor, reason):
    owner = _content_owner(target)
    if action == "warn":
        if owner is None:
            raise ValidationError("This content has no user who can be warned.")
        Notification.objects.create(
            user=owner,
            actor=actor,
            notification_type="system",
            message=f"A moderator issued a warning: {reason[:180]}",
        )
        return owner, {"warning_sent": True}
    if action not in {"keep", "hide", "remove"} or not isinstance(
        target, CONTENT_MODELS
    ):
        raise ValidationError("That moderation action is not available for this item.")

    before = _target_snapshot(target)
    target.moderation_status = {
        "keep": "visible",
        "hide": "hidden",
        "remove": "removed",
    }[action]
    target.save(update_fields=["moderation_status"])
    after = {**before, "moderation_status": target.moderation_status}
    return owner, after


def _write_audit(actor, target, action, reason, before, after):
    content_type = ContentType.objects.get_for_model(target) if target is not None else None
    object_id = target.pk if target is not None else None
    AuditLog.objects.create(
        actor=actor,
        actor_label=actor.get_username(),
        action=action,
        content_type=content_type,
        object_id=object_id,
        target_label=_target_label(target) if target is not None else "Report",
        target_user=_content_owner(target) if target is not None else None,
        reason=reason,
        before=before,
        after=after,
    )


@require_role("read")
def dashboard(request):
    now = timezone.now()
    today = timezone.localdate()
    User = get_user_model()
    signup_start = now - timedelta(days=7)
    post_start = now - timedelta(days=7)
    signups = dict(
        User.objects.filter(date_joined__gte=signup_start)
        .annotate(day=TruncDate("date_joined"))
        .values("day")
        .annotate(total=Count("pk"))
        .values_list("day", "total")
    )
    posts = dict(
        Tree.objects.filter(
            publication_status="published",
            moderation_status="visible",
            published_at__gte=post_start,
        )
        .annotate(day=TruncDate("published_at"))
        .values("day")
        .annotate(total=Count("pk"))
        .values_list("day", "total")
    )
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    day_rows = [
        {"day": day, "signups": signups.get(day, 0), "posts": posts.get(day, 0)}
        for day in days
    ]
    context = {
        "active_24h": User.objects.filter(last_login__gte=now - timedelta(days=1)).count(),
        "active_7d": User.objects.filter(last_login__gte=now - timedelta(days=7)).count(),
        "active_30d": User.objects.filter(last_login__gte=now - timedelta(days=30)).count(),
        "signups_today": User.objects.filter(date_joined__date=today).count(),
        "posts_today": Tree.objects.filter(
            publication_status="published",
            moderation_status="visible",
            published_at__date=today,
        ).count(),
        "pending_reports": Report.objects.filter(status="pending").count(),
        "pending_flags": AIFlag.objects.filter(status="pending").count(),
        "total_public_posts": Tree.objects.filter(
            publication_status="published", moderation_status="visible"
        ).count(),
        "total_reactions": Reaction.objects.count(),
        "total_comments": Comment.objects.filter(moderation_status="visible").count(),
        "day_rows": day_rows,
        "recent_activity": AuditLog.objects.select_related("actor")[:8],
    }
    return render(request, "ops/dashboard.html", context)


@require_role("read")
def reports(request):
    status = request.GET.get("status", "pending")
    valid_statuses = {value for value, _ in Report.STATUSES}
    if status not in valid_statuses | {"all"}:
        status = "pending"
    queryset = Report.objects.select_related(
        "reporter", "reviewed_by", "content_type"
    )
    if status != "all":
        queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "ops/reports.html",
        {"page": page, "selected_status": status, "statuses": Report.STATUSES},
    )


@require_role("read")
def report_detail(request, report_id):
    report = get_object_or_404(
        Report.objects.select_related("reporter", "reviewed_by", "content_type"),
        pk=report_id,
    )
    target = report.content_object
    if target is None:
        preview = "The reported item is no longer available."
        owner = None
        action_choices = [("dismiss", "Dismiss report")]
    else:
        preview = _target_snapshot(target)
        owner = _content_owner(target)
        action_choices = [("dismiss", "Dismiss report")]
        if isinstance(target, CONTENT_MODELS):
            action_choices.extend(
                [
                    ("keep", "Keep content"),
                    ("warn", "Warn content owner"),
                    ("hide", "Hide content"),
                    ("remove", "Remove content"),
                ]
            )
        elif owner:
            action_choices.append(("warn", "Warn user"))
    action_form = ModerationActionForm()
    action_form.fields["action"].choices = action_choices
    return render(
        request,
        "ops/report_detail.html",
        {
            "report": report,
            "target": target,
            "preview": preview,
            "owner": owner,
            "action_form": action_form,
            "can_moderate": has_ops_role(request.user, "moderate"),
        },
    )


@require_role("moderate")
@require_POST
def report_action(request, report_id):
    form = ModerationActionForm(request.POST)
    report = get_object_or_404(
        Report.objects.select_related("content_type"), pk=report_id, status="pending"
    )
    target = report.content_object
    if target is None:
        form.fields["action"].choices = [("dismiss", "Dismiss report")]
    elif not isinstance(target, CONTENT_MODELS):
        form.fields["action"].choices = [
            ("dismiss", "Dismiss report"),
            ("warn", "Warn user"),
        ]
    if not form.is_valid():
        messages.error(request, "Choose an action and provide a reason.")
        return redirect("ops:report_detail", report_id=report.pk)
    action = form.cleaned_data["action"]
    reason = form.cleaned_data["reason"].strip()
    if not reason:
        messages.error(request, "A reason is required for every moderation action.")
        return redirect("ops:report_detail", report_id=report.pk)
    try:
        with transaction.atomic():
            report = get_object_or_404(
                Report.objects.select_for_update().select_related("content_type"),
                pk=report_id,
                status="pending",
            )
            target = report.content_object
            before = _target_snapshot(target) if target is not None else {}
            if action != "dismiss" and target is None:
                raise ValidationError("The reported content is no longer available.")
            if action != "dismiss":
                owner, after = _apply_action(target, action, request.user, reason)
            else:
                owner, after = _content_owner(target), {}
            report.status = "dismissed" if action == "dismiss" else "action_taken"
            report.reviewed_by = request.user
            report.resolved_at = timezone.now()
            report.save(update_fields=["status", "reviewed_by", "resolved_at"])
            _write_audit(
                request.user,
                target if target is not None else report,
                f"report_{action}",
                reason,
                before,
                after,
            )
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("ops:report_detail", report_id=report.pk)
    messages.success(request, "Report reviewed and the action was recorded.")
    return redirect("ops:reports")


@require_role("read")
def ai_flags(request):
    status = request.GET.get("status", "pending")
    valid_statuses = {value for value, _ in AIFlag.STATUSES}
    if status not in valid_statuses | {"all"}:
        status = "pending"
    queryset = AIFlag.objects.select_related("content_type", "reviewed_by")
    if status != "all":
        queryset = queryset.filter(status=status)
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "ops/ai_flags.html",
        {
            "page": page,
            "selected_status": status,
            "statuses": AIFlag.STATUSES,
            "can_moderate": has_ops_role(request.user, "moderate"),
        },
    )


@require_role("moderate")
@require_POST
def ai_flag_action(request, flag_id):
    flag = get_object_or_404(
        AIFlag.objects.select_related("content_type"), pk=flag_id, status="pending"
    )
    form = AIFlagActionForm(request.POST)
    target = flag.content_object
    if target is None:
        form.fields["action"].choices = [("keep", "Resolve flag")]
    elif not isinstance(target, CONTENT_MODELS):
        form.fields["action"].choices = [("warn", "Warn user")]
    if not form.is_valid():
        messages.error(request, "Choose an action and provide a reason.")
        return redirect("ops:ai_flags")
    action = form.cleaned_data["action"]
    reason = form.cleaned_data["reason"].strip()
    if not reason:
        messages.error(request, "A reason is required for every moderation action.")
        return redirect("ops:ai_flags")
    try:
        with transaction.atomic():
            flag = get_object_or_404(
                AIFlag.objects.select_for_update().select_related("content_type"),
                pk=flag_id,
                status="pending",
            )
            target = flag.content_object
            before = _target_snapshot(target) if target is not None else {}
            if target is None:
                after = {}
                owner = None
            else:
                owner, after = _apply_action(target, action, request.user, reason)
            flag.status = "dismissed" if action == "keep" else "action_taken"
            flag.reviewed_by = request.user
            flag.resolved_at = timezone.now()
            flag.save(update_fields=["status", "reviewed_by", "resolved_at"])
            _write_audit(
                request.user,
                target if target is not None else flag,
                f"ai_flag_{action}",
                reason,
                before,
                after,
            )
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("ops:ai_flags")
    messages.success(request, "AI flag reviewed and the action was recorded.")
    return redirect("ops:ai_flags")


@require_role("read")
def audit_log(request):
    queryset = AuditLog.objects.select_related("actor", "target_user", "content_type")
    action = request.GET.get("action", "").strip()[:40]
    if action:
        queryset = queryset.filter(action=action)
    page = Paginator(queryset, 50).get_page(request.GET.get("page"))
    actions = AuditLog.objects.order_by().values_list("action", flat=True).distinct()
    return render(
        request,
        "ops/audit_log.html",
        {"page": page, "actions": actions, "selected_action": action},
    )


@require_POST
def submit_report(request, content_type, object_id):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")
    target = _get_reportable_object(content_type, object_id)
    if _content_owner(target) == request.user:
        messages.error(request, "You cannot report your own content.")
        return redirect(_target_url(target))
    model_content_type = ContentType.objects.get_for_model(target)
    already_reported = Report.objects.filter(
        reporter=request.user,
        content_type=model_content_type,
        object_id=target.pk,
        status="pending",
    ).exists()
    if already_reported:
        messages.info(request, "You have already reported this item. Moderators will review it.")
        return redirect(_target_url(target))
    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Choose a report reason and try again.")
        return redirect(_target_url(target))
    _, created = Report.objects.get_or_create(
        reporter=request.user,
        content_type=model_content_type,
        object_id=target.pk,
        status="pending",
        defaults={
            "reason": form.cleaned_data["reason"],
            "details": form.cleaned_data["details"],
        },
    )
    if not created:
        messages.info(request, "You have already reported this item. Moderators will review it.")
        return redirect(_target_url(target))
    messages.success(request, "Thanks. Your report has been sent to the moderation team.")
    return redirect(_target_url(target))
