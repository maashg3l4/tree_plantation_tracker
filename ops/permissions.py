from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


ROLE_GROUPS = {
    "admin": "Ops Admin",
    "moderator": "Moderator",
    "support": "Support",
    "analyst": "Analyst",
}


def has_ops_role(user, role):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.groups.filter(name=ROLE_GROUPS["admin"]).exists():
        return True
    if role == "read":
        return user.groups.filter(
            name__in=[ROLE_GROUPS["moderator"], ROLE_GROUPS["support"], ROLE_GROUPS["analyst"]]
        ).exists()
    if role == "moderate":
        return user.groups.filter(name=ROLE_GROUPS["moderator"]).exists()
    if role == "admin":
        return False
    raise ValueError(f"Unknown operations role: {role}")


def require_role(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"/login/?next={request.path}")
            if not has_ops_role(request.user, role):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
