from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Company email or Employee ID"),
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}))

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        domains = settings.ALLOWED_EMAIL_DOMAINS
        is_super = User.objects.filter(email__iexact=value, is_superuser=True).exists()
        if "@" in value and domains and value.rsplit("@", 1)[-1].lower() not in domains and not is_super:
            raise forms.ValidationError(
                _("Only company accounts can sign in. Please use your %(d)s email.") %
                {"d": ", ".join("@" + d for d in domains)})
        return value


import logging

log = logging.getLogger(__name__)


class AnyPasswordResetForm(PasswordResetForm):
    """Django skips accounts that have no password yet (admin-created, imported, Microsoft sign-in).
    Those people still need a way to set one, so include every active account."""

    def get_users(self, email):
        return (u for u in User._default_manager.filter(email__iexact=email, is_active=True))

    def save(self, **kwargs):
        email = self.cleaned_data["email"]
        self.found = User._default_manager.filter(email__iexact=email, is_active=True).exists()
        if self.found:
            log.info("Password reset: sending email to %s (backend: %s)", email, settings.EMAIL_BACKEND.rsplit(".", 1)[-1])
        else:
            log.warning("Password reset requested for %s but no ACTIVE account has this email address — nothing sent.", email)
        return super().save(**kwargs)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        labels = {"first_name": _("First name"), "last_name": _("Last name")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_first_name(self):
        return " ".join(self.cleaned_data["first_name"].split())

    def clean_last_name(self):
        return " ".join(self.cleaned_data["last_name"].split())


class SignupForm(forms.ModelForm):
    password1 = forms.CharField(label=_("Password"), widget=forms.PasswordInput(
        attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label=_("Confirm password"), widget=forms.PasswordInput(
        attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "employee_id"]
        labels = {"first_name": _("First name"), "last_name": _("Last name"), "email": _("Company email"), "employee_id": _("Employee ID (optional)")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["employee_id"].required = False

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        domain = email.rsplit("@", 1)[-1]
        if settings.ALLOWED_EMAIL_DOMAINS and domain not in settings.ALLOWED_EMAIL_DOMAINS:
            raise forms.ValidationError(
                _("Please use your company email (%(d)s).") %
                {"d": ", ".join("@" + d for d in settings.ALLOWED_EMAIL_DOMAINS)})
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("An account with this email already exists. Try signing in or resetting your password."))
        return email

    def clean_employee_id(self):
        eid = (self.cleaned_data.get("employee_id") or "").strip()
        if not eid:
            return None  # keep the unique column NULL, not ""
        if User.objects.filter(employee_id__iexact=eid).exists():
            raise forms.ValidationError(_("This Employee ID is already registered."))
        return eid

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("The two passwords do not match."))
        elif p1:
            candidate = User(email=data.get("email", ""), first_name=data.get("first_name", ""),
                             last_name=data.get("last_name", ""))
            try:
                password_validation.validate_password(p1, candidate)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = False  # activated after e-mail verification
        if commit:
            user.save()
        return user
