from django.shortcuts import render


def csrf_failure(request, reason=""):
    """Shown when a form is submitted from an expired page — never a bare, scary error."""
    return render(request, "errors/csrf.html", status=403)
