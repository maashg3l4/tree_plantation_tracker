from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from grove.permissions import can_manage, membership_for
from .forms import CertificationDocumentForm
from .models import CertificationDocument


@login_required
def overview(request, slug):
    membership = membership_for(request.user, slug)
    if membership.role == "worker":
        return HttpResponse("Compliance records are limited to non-field workspace roles.", status=403)
    documents = membership.org.documents.select_related("uploaded_by")
    return render(
        request,
        "grove_compliance/overview.html",
        {"membership": membership, "org": membership.org, "documents": documents},
    )


@login_required
def upload_document(request, slug):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to manage compliance documents.", status=403)
    form = CertificationDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        upload = form.cleaned_data["document"]
        if upload.size > 15 * 1024 * 1024:
            form.add_error("document", "Documents must be 15 MB or smaller.")
        elif Path(upload.name).suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg"}:
            form.add_error("document", "Upload a PDF, PNG, or JPEG document.")
        else:
            document = form.save(commit=False)
            document.org = membership.org
            document.uploaded_by = request.user
            document.save()
            messages.success(request, "Document added to the private vault.")
            return redirect("grove_compliance:overview", slug=slug)
    return render(
        request,
        "grove_compliance/document_form.html",
        {"membership": membership, "org": membership.org, "form": form},
    )


@login_required
def download_document(request, slug, pk):
    membership = membership_for(request.user, slug)
    if membership.role == "worker":
        return HttpResponse("Compliance records are limited to non-field workspace roles.", status=403)
    document = get_object_or_404(CertificationDocument, pk=pk, org=membership.org)
    return FileResponse(
        document.document.open("rb"),
        as_attachment=True,
        filename=Path(document.document.name).name,
    )
