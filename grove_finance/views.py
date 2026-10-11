from io import BytesIO
from xml.sax.saxutils import escape

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from grove.models import Plot
from grove.permissions import can_manage, membership_for
from .forms import TransactionForm
from .models import Transaction


def _financial_totals(org):
    totals = Transaction.objects.filter(org=org).values("trans_type").annotate(total=Sum("amount"))
    amount_by_type = {row["trans_type"]: row["total"] or 0 for row in totals}
    return {
        "revenue": amount_by_type.get("revenue", 0),
        "expenses": amount_by_type.get("expense", 0),
        "net": amount_by_type.get("revenue", 0) - amount_by_type.get("expense", 0),
    }


@login_required
def overview(request, slug):
    membership = membership_for(request.user, slug)
    if membership.role == "worker":
        return HttpResponse("Financial records are limited to non-field workspace roles.", status=403)
    transactions = Transaction.objects.filter(org=membership.org).select_related("plot")[:100]
    return render(
        request,
        "grove_finance/overview.html",
        {
            "membership": membership,
            "org": membership.org,
            "transactions": transactions,
            "totals": _financial_totals(membership.org),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_transaction(request, slug):
    membership = membership_for(request.user, slug)
    if not can_manage(membership):
        return HttpResponse("You do not have permission to add transactions.", status=403)
    form = TransactionForm(request.POST or None, request.FILES or None)
    form.fields["plot"].queryset = Plot.objects.filter(org=membership.org)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.org = membership.org
        entry.created_by = request.user
        entry.save()
        messages.success(request, "Transaction saved.")
        return redirect("grove_finance:overview", slug=slug)
    return render(
        request,
        "grove_finance/transaction_form.html",
        {"membership": membership, "org": membership.org, "form": form},
    )


@login_required
def pdf_report(request, slug):
    membership = membership_for(request.user, slug)
    if membership.role == "worker":
        return HttpResponse("Financial reports are limited to non-field workspace roles.", status=403)
    org = membership.org
    transactions = Transaction.objects.filter(org=org).select_related("plot")
    totals = _financial_totals(org)
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, title=f"{org.name} financial report")
    styles = getSampleStyleSheet()
    content = [
        Paragraph(f"{escape(org.name)} — Financial summary", styles["Title"]),
        Paragraph("Figures reflect records entered in Grove.", styles["Normal"]),
        Spacer(1, 16),
        Paragraph(
            f"Revenue: BDT {totals['revenue']:,.2f} &nbsp;&nbsp; "
            f"Expenses: BDT {totals['expenses']:,.2f} &nbsp;&nbsp; "
            f"Net: BDT {totals['net']:,.2f}",
            styles["Normal"],
        ),
        Spacer(1, 16),
    ]
    rows = [["Date", "Type", "Category", "Plot", "Description", "Amount (BDT)"]]
    for item in transactions[:1000]:
        rows.append(
            [
                item.date.isoformat(),
                item.get_trans_type_display(),
                item.category,
                item.plot.name if item.plot else "",
                item.description,
                f"{item.amount:,.2f}",
            ]
        )
    table = Table(rows, repeatRows=1, colWidths=[55, 48, 65, 60, 200, 75])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14532d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fdf4")]),
            ]
        )
    )
    content.append(table)
    document.build(content)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{org.slug}-financial-report.pdf"'
    return response
