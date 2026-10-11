from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from grove.permissions import can_manage
from .forms import MarketplaceListingForm
from .models import MarketplaceListing


def listings(request):
    queryset = MarketplaceListing.objects.filter(
        status="active", org__is_public=True
    ).select_related("org")
    listing_type = request.GET.get("type", "")
    if listing_type in {"sell", "buy", "hire"}:
        queryset = queryset.filter(listing_type=listing_type)
    region = request.GET.get("region", "").strip()[:120]
    if region:
        queryset = queryset.filter(region__icontains=region)
    return render(
        request,
        "grove_market/listings.html",
        {"listings": queryset, "listing_type": listing_type, "region": region},
    )


@login_required
def create_listing(request):
    memberships = [
        member
        for member in request.user.organizationmember_set.select_related("org")
        if can_manage(member)
    ]
    if not memberships:
        messages.error(request, "An organization owner or manager account is required to post.")
        return redirect("grove_market:listings")
    selected_slug = request.GET.get("org") or request.POST.get("org")
    if selected_slug and not any(member.org.slug == selected_slug for member in memberships):
        return HttpResponseForbidden("You cannot publish for that organization.")
    selected_membership = next(
        (member for member in memberships if member.org.slug == selected_slug),
        memberships[0],
    )
    if not selected_membership.org.is_public:
        return HttpResponseForbidden("Make this organization's profile public before posting.")
    form = MarketplaceListingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        listing = form.save(commit=False)
        listing.org = selected_membership.org
        listing.created_by = request.user
        listing.save()
        messages.success(request, "Your marketplace listing is live.")
        return redirect("grove_market:listings")
    return render(
        request,
        "grove_market/listing_form.html",
        {"form": form, "membership": selected_membership, "organizations": memberships},
    )
