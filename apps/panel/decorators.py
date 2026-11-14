from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def admin_required(view):
    """Only Shiksha admins. An admin previewing the learner view is sent back to the dashboard."""
    @wraps(view)
    @login_required
    def wrapper(request, *a, **kw):
        u = request.user
        if not u.is_shiksha_admin:
            if u.real_admin:
                messages.info(request, "You are in learner view — switch back to the admin view to manage content.")
                return redirect("core:dashboard")
            raise PermissionDenied
        return view(request, *a, **kw)
    return wrapper
