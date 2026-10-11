import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    OrganizationForm,
    OrganizationMemberForm,
    PlotForm,
    TaskCompletionForm,
    TaskForm,
)
from .models import (
    Organization,
    OrganizationMember,
    Plot,
    PlotHealthAnalysis,
    PlotHealthSnapshot,
    Task,
    TreeBatch,
)
from .permissions import can_manage, membership_for
from trees.ai_services import AIServiceError, analyze_tree_health, image_digest


@login_required
def workspace(request):
    memberships = (
        OrganizationMember.objects.filter(user=request.user)
        .select_related("org")
        .annotate(plot_count=Count("org__plots", distinct=True))
        .order_by("org__name")
    )
    return render(request, "grove/workspace.html", {"memberships": memberships})


@login_required
def create_organization(request):
    if request.method == "POST":
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                org = form.save(commit=False)
                org.owner = request.user
                org.save()
                OrganizationMember.objects.create(org=org, user=request.user, role="owner")
                from trees.models import Profile

                profile, _ = Profile.objects.get_or_create(user=request.user)
                profile.account_type = "business"
                profile.save(update_fields=["account_type"])
            messages.success(request, "Your Grove workspace is ready.")
            return redirect("grove:dashboard", slug=org.slug)
    else:
        form = OrganizationForm()
    return render(request, "grove/organization_form.html", {"form": form})


@login_required
def dashboard(request, slug):
    membership = membership_for(request.user, slug)
    org = membership.org
    plots = org.plots.annotate(tree_total=Sum("batches__quantity")).order_by("name")
    tasks = Task.objects.filter(plot__org=org).select_related("plot", "assigned_to")[:8]
    totals = TreeBatch.objects.filter(plot__org=org).aggregate(total=Sum("quantity"))
    stats = {
        "plot_count": org.plots.count(),
        "tree_count": totals["total"] or 0,
        "worker_count": org.members.filter(role="worker").count(),
        "open_tasks": Task.objects.filter(plot__org=org, completed_at__isnull=True).count(),
    }
    team = org.members.select_related("user")
    return render(
        request,
        "grove/dashboard.html",
        {
            "membership": membership,
            "org": org,
            "plots": plots,
            "tasks": tasks,
            "stats": stats,
            "team": team,
            "member_form": OrganizationMemberForm(
                org=org, actor_role=membership.role
            ) if can_manage(membership) else None,
        },
    )


@login_required
def create_plot(request, slug):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to manage plots.", status=403)
    if request.method == "POST":
        form = PlotForm(request.POST)
        if form.is_valid():
            plot = form.save(commit=False)
            plot.org = membership.org
            plot.save()
            messages.success(request, "Plot added to the workspace.")
            return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    else:
        form = PlotForm()
    return render(
        request,
        "grove/plot_form.html",
        {"membership": membership, "org": membership.org, "form": form},
    )


@login_required
def plot_detail(request, slug, pk):
    membership = membership_for(request.user, slug)
    plot = get_object_or_404(Plot, pk=pk, org=membership.org)
    tasks = plot.tasks.select_related("assigned_to", "created_by")
    batches = plot.batches.select_related("created_by")
    latest_health = plot.health_snapshots.first()
    latest_ai_analysis = plot.ai_health_analyses.first()
    return render(
        request,
        "grove/plot_detail.html",
        {
            "membership": membership,
            "org": membership.org,
            "plot": plot,
            "tasks": tasks,
            "batches": batches,
            "latest_health": latest_health,
            "latest_ai_analysis": latest_ai_analysis,
            "can_manage": can_manage(membership),
        },
    )


@login_required
@require_POST
def import_batches(request, slug, pk):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to import tree batches.", status=403)
    plot = get_object_or_404(Plot, pk=pk, org=membership.org)
    upload = request.FILES.get("csv_file")
    if not upload:
        messages.error(request, "Choose a CSV file to import.")
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    if upload.size > 2 * 1024 * 1024:
        messages.error(request, "CSV files must be 2 MB or smaller.")
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)

    try:
        source = StringIO(upload.read().decode("utf-8-sig"))
        reader = csv.DictReader(source)
        if reader.fieldnames:
            reader.fieldnames = [name.strip() for name in reader.fieldnames if name]
        required = {"species", "quantity", "planted_date"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("CSV must contain species, quantity, and planted_date columns.")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if row_number > 502:
                raise ValueError("A single import can contain no more than 500 batches.")
            species = (row.get("species") or "").strip()
            if not species or len(species) > 120:
                raise ValueError(
                    f"Row {row_number}: species is required and must be 120 characters or fewer."
                )
            try:
                quantity = int(row.get("quantity", ""))
                planted_date = date.fromisoformat((row.get("planted_date") or "").strip())
                spacing_value = (row.get("spacing_m") or "").strip()
                spacing = Decimal(spacing_value) if spacing_value else None
            except (ValueError, InvalidOperation):
                raise ValueError(
                    f"Row {row_number}: use a whole quantity, YYYY-MM-DD date, and valid spacing."
                )
            if quantity < 1 or quantity > 1_000_000:
                raise ValueError(f"Row {row_number}: quantity must be between 1 and 1,000,000.")
            if spacing is not None and (spacing <= 0 or spacing > 999):
                raise ValueError(f"Row {row_number}: spacing must be between 0 and 999 metres.")
            rows.append(
                TreeBatch(
                    plot=plot,
                    species=species,
                    quantity=quantity,
                    planted_date=planted_date,
                    spacing_m=spacing,
                    source_nursery=(row.get("source_nursery") or "").strip()[:200],
                    created_by=request.user,
                )
            )
        if not rows:
            raise ValueError("The CSV contains no batch rows.")
    except (UnicodeDecodeError, csv.Error, ValueError) as error:
        messages.error(request, str(error))
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)

    TreeBatch.objects.bulk_create(rows)
    messages.success(request, f"Imported {len(rows)} tree batches.")
    return redirect("grove:plot_detail", slug=slug, pk=plot.pk)


@login_required
def create_task(request, slug):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to create tasks.", status=403)
    form = TaskForm(request.POST or None)
    form.fields["plot"].queryset = Plot.objects.filter(org=membership.org)
    member_user_ids = OrganizationMember.objects.filter(
        org=membership.org, role__in=["owner", "manager", "worker"]
    ).values("user_id")
    form.fields["assigned_to"].queryset = get_user_model().objects.filter(pk__in=member_user_ids)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        task.save()
        messages.success(request, "Task assigned.")
        return redirect("grove:dashboard", slug=slug)
    return render(
        request,
        "grove/task_form.html",
        {"membership": membership, "org": membership.org, "form": form},
    )


@login_required
@require_POST
def add_member(request, slug):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to manage the team.", status=403)
    form = OrganizationMemberForm(
        request.POST,
        org=membership.org,
        actor_role=membership.role,
    )
    if form.is_valid():
        team_member = form.save(commit=False)
        team_member.org = membership.org
        team_member.save()
        messages.success(request, f"{team_member.user.username} added to the workspace.")
    else:
        messages.error(request, "Choose an existing user and a role permitted for your account.")
    return redirect("grove:dashboard", slug=slug)


@login_required
@require_POST
def complete_task(request, slug, pk):
    membership = membership_for(request.user, slug)
    task = get_object_or_404(Task, pk=pk, plot__org=membership.org)
    if not can_manage(membership) and task.assigned_to_id != request.user.id:
        return HttpResponse("Only managers or the assigned worker can update this task.", status=403)
    if task.completed_at:
        messages.info(request, "This task is already complete.")
        return redirect("grove:dashboard", slug=slug)
    form = TaskCompletionForm(request.POST, request.FILES)
    if not form.is_valid():
        return HttpResponseBadRequest("Upload a valid task proof image of 10 MB or smaller.")
    task.completed_at = timezone.now()
    if form.cleaned_data["proof_image"]:
        task.proof_image = form.cleaned_data["proof_image"]
    messages.success(request, "Task marked complete.")
    task.save(update_fields=["completed_at", "proof_image"])
    return redirect("grove:dashboard", slug=slug)


@login_required
@require_POST
def add_health_snapshot(request, slug, pk):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to add health data.", status=403)
    plot = get_object_or_404(Plot, pk=pk, org=membership.org)
    try:
        ndvi = Decimal(request.POST.get("ndvi", ""))
    except InvalidOperation:
        return HttpResponseBadRequest("Enter a valid NDVI reading.")
    if not ndvi.is_finite() or not Decimal("-1") <= ndvi <= Decimal("1"):
        return HttpResponseBadRequest("NDVI must be between -1 and 1.")
    PlotHealthSnapshot.objects.create(
        plot=plot,
        ndvi=ndvi,
        source="manual",
        notes=request.POST.get("notes", "").strip()[:240],
        captured_by=request.user,
    )
    messages.success(request, "NDVI observation recorded.")
    return redirect("grove:plot_detail", slug=slug, pk=plot.pk)


@login_required
@require_POST
def analyze_plot_health(request, slug, pk):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("Only workspace managers can request paid AI analysis.", status=403)
    plot = get_object_or_404(Plot, pk=pk, org=membership.org)
    image = request.FILES.get("image")
    if not image:
        messages.error(request, "Choose a field image to analyze.")
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    try:
        image_hash = image_digest(image)
    except AIServiceError as error:
        messages.error(request, str(error))
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    if plot.ai_health_analyses.filter(image_hash=image_hash).exists():
        messages.info(request, "This field image already has a saved AI analysis.")
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    try:
        result = analyze_tree_health(image)
    except AIServiceError as error:
        messages.error(request, str(error))
        return redirect("grove:plot_detail", slug=slug, pk=plot.pk)
    PlotHealthAnalysis.objects.get_or_create(
        plot=plot,
        image_hash=result["image_hash"],
        defaults={
            "score": result["score"],
            "issues": result["issues"],
            "recommendations": result["recommendations"],
            "confidence": result["confidence"],
            "model_used": result["model_used"],
            "analyzed_by": request.user,
        },
    )
    messages.success(request, "AI plot health summary saved.")
    return redirect("grove:plot_detail", slug=slug, pk=plot.pk)


def public_farm(request, slug):
    org = get_object_or_404(Organization, slug=slug, is_public=True)
    plots = org.plots.annotate(tree_total=Sum("batches__quantity"))
    tree_totals = TreeBatch.objects.filter(plot__org=org).aggregate(total=Sum("quantity"))
    return render(
        request,
        "grove/public_farm.html",
        {"org": org, "plots": plots, "tree_count": tree_totals["total"] or 0},
    )


def public_batch(request, code):
    batch = get_object_or_404(
        TreeBatch.objects.select_related("plot__org"),
        qr_batch_code=code,
        plot__org__is_public=True,
    )
    return render(request, "grove/public_batch.html", {"batch": batch})


@login_required
def batch_qr(request, slug, code):
    membership = membership_for(request.user, slug)
    batch = get_object_or_404(
        TreeBatch, qr_batch_code=code, plot__org=membership.org, plot__org__is_public=True
    )
    try:
        import qrcode
    except ImportError as error:
        raise RuntimeError("Install the qrcode dependency to generate batch QR codes.") from error

    image = qrcode.make(request.build_absolute_uri(f"/grove/batch/{batch.qr_batch_code}/"))
    response = HttpResponse(content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="grove-batch-{batch.qr_batch_code}.png"'
    image.save(response, format="PNG")
    return response
