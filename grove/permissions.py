from django.shortcuts import get_object_or_404

from .models import OrganizationMember


MANAGER_ROLES = {"owner", "manager"}


def membership_for(user, slug):
    return get_object_or_404(
        OrganizationMember.objects.select_related("org", "user"),
        org__slug=slug,
        user=user,
    )


def can_manage(membership):
    return membership.role in MANAGER_ROLES
