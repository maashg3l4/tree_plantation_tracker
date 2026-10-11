from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render

from grove.models import TreeBatch
from grove.permissions import membership_for
from .forms import CarbonEstimateForm
from .models import CarbonCalculation


@login_required
def overview(request, slug):
    membership = membership_for(request.user, slug)
    form = CarbonEstimateForm(request.POST or None, org=membership.org)
    if request.method == "POST" and form.is_valid():
        plot = form.cleaned_data["plot"]
        years = form.cleaned_data["horizon_years"]
        trees = TreeBatch.objects.filter(plot=plot).aggregate(total=Sum("quantity"))["total"] or 0
        tonnes = Decimal(trees * years * 22) / Decimal(1000)
        CarbonCalculation.objects.create(
            org=membership.org,
            plot=plot,
            co2_tonnes=tonnes.quantize(Decimal("0.01")),
            methodology="Grove screening proxy: 22 kg CO2/tree/year",
            eligible_credits=None,
            notes=f"{trees} recorded trees over {years} year(s); not a verified inventory.",
            calculated_by=request.user,
        )
        messages.info(
            request,
            "Screening estimate saved. It is not a verified carbon inventory or credit eligibility assessment.",
        )
        return redirect("grove_carbon:overview", slug=slug)
    calculations = membership.org.carbon_calculations.select_related("plot", "calculated_by")
    return render(
        request,
        "grove_carbon/overview.html",
        {
            "membership": membership,
            "org": membership.org,
            "form": form,
            "calculations": calculations,
        },
    )
