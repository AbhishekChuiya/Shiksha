import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext as _

from apps.plants.models import Plant

from . import sso
from .avatar import AvatarError, process_avatar
from .emailing import send_branded
from .forms import AnyPasswordResetForm, ProfileForm, SignupForm

log = logging.getLogger(__name__)
User = get_user_model()
BACKEND = "apps.accounts.backends.EmailOrEmployeeIdBackend"


def _send_verification(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(reverse("accounts:verify_email", args=[uid, token]))
    send_branded(_("Verify your Project Shiksha account"), user.email,
                 "accounts/emails/verify.txt", "accounts/emails/verify.html",
                 {"user": user, "link": link})


def signup(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            _send_verification(request, user)
        except Exception:  # SMTP down / not configured — don't leave a half-made account behind
            log.exception("Could not send verification email to %s", user.email)
            user.delete()
            msg = _("We couldn't send the verification email right now. Please try again in a few minutes or contact the Shiksha admin.")
            if settings.DEBUG:
                import sys
                msg += f"  [{sys.exc_info()[0].__name__}: {sys.exc_info()[1]}]"
            form.add_error(None, msg)
        else:
            return render(request, "accounts/signup_done.html", {"email": user.email})
    return render(request, "accounts/signup.html", {"form": form})


class PasswordResetView(auth_views.PasswordResetView):
    form_class = AnyPasswordResetForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/emails/password_reset.txt"
    html_email_template_name = "accounts/emails/password_reset.html"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    extra_email_context = {"logo_url": getattr(settings, "EMAIL_LOGO_URL", "")}

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except Exception as exc:
            log.exception("Could not send password reset email")
            msg = _("We couldn't send the email right now. Please try again in a few minutes.")
            if settings.DEBUG:                                  # developers see the real reason; users never do
                msg += f"  [{type(exc).__name__}: {exc}]"
            form.add_error(None, msg)
            return self.form_invalid(form)
        if settings.DEBUG and not getattr(form, "found", True):
            messages.warning(self.request, "Developer note: no active account has this email address, so no email was sent. "
                                           "(This hint is hidden when DEBUG is off.)")
        return response


def verify_email(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        messages.success(request, _("Email verified. You can sign in now."))
        return redirect("accounts:login")
    return render(request, "accounts/verify_failed.html", status=400)


def _redirect_uri(request):
    return settings.ENTRA_REDIRECT_URI or request.build_absolute_uri(reverse("accounts:sso_callback"))


def sso_login(request):
    if not settings.SSO_ENABLED:
        messages.error(request, _("Microsoft sign-in is not configured yet."))
        return redirect("accounts:login")
    return redirect(sso.begin(request, _redirect_uri(request)))


def sso_callback(request):
    if not settings.SSO_ENABLED:
        return redirect("accounts:login")
    try:
        email, first, last = sso.finish(request, _redirect_uri(request))
    except Exception as exc:  # MSAL / network errors must not become a 500 page
        log.warning("SSO failed: %s", exc)
        messages.error(request, _("Microsoft sign-in failed. Please try again."))
        return redirect("accounts:login")

    domain = email.rsplit("@", 1)[-1]
    if settings.ALLOWED_EMAIL_DOMAINS and domain not in settings.ALLOWED_EMAIL_DOMAINS:
        messages.error(request, _("This Microsoft account is not part of the company domain."))
        return redirect("accounts:login")

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User(email=email, first_name=first, last_name=last)
        user.set_unusable_password()  # SSO-only until they use "Forgot password"
        user.save()
        plants = Plant.objects.filter(code__in=settings.DEFAULT_NEW_USER_PLANT_CODES)
        user.plants.set(plants)
    if not user.is_active:
        user.is_active = True  # Microsoft has verified the mailbox
        user.save(update_fields=["is_active"])
    login(request, user, backend=BACKEND)
    return redirect(settings.LOGIN_REDIRECT_URL)


class AccountView(auth_views.PasswordChangeView):
    """My account: photo, name, password and read-only account details on one page."""
    template_name = "accounts/account.html"
    success_url = reverse_lazy("accounts:account")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["old_password"].widget.attrs.pop("autofocus", None)  # don't scroll past the photo on page load
        return form

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        user = self.request.user
        ctx.setdefault("profile_form", ProfileForm(instance=user))
        ctx["plants_list"] = user.accessible_plants()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, _("Password updated."))
        return super().form_valid(form)   # PasswordChangeView keeps the user signed in


def profile_update(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Your name was updated. It will appear on your certificates."))
    elif request.method == "POST":
        messages.error(request, _("Please enter both first and last name."))
    return redirect("accounts:account")


@require_POST
def photo_update(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    user = request.user
    if request.POST.get("action") == "remove":
        if user.photo:
            user.photo.delete(save=False)
            user.photo = ""
            user.save(update_fields=["photo"])
        messages.success(request, _("Profile photo removed."))
        return redirect("accounts:account")
    upload = request.FILES.get("photo")
    if not upload:
        messages.error(request, _("Please choose a photo first."))
        return redirect("accounts:account")
    try:
        processed = process_avatar(upload)
    except AvatarError as exc:
        messages.error(request, _("The photo is too large. Please use an image under 5 MB.") if str(exc) == "big"
                       else _("Please upload a JPG, PNG or WEBP image."))
        return redirect("accounts:account")
    if user.photo:
        user.photo.delete(save=False)
    user.photo.save(processed.name, processed, save=True)
    messages.success(request, _("Profile photo updated."))
    return redirect("accounts:account")
