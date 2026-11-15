from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.generic import RedirectView

from . import views
from .forms import LoginForm

app_name = "accounts"
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html",
                                                authentication_form=LoginForm,
                                                redirect_authenticated_user=True), name="login"),
    # POST only. `?next=` lets "Switch account" log out and land on the sign-in page.
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", views.signup, name="signup"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("sso/login/", views.sso_login, name="sso_login"),
    path("sso/callback/", views.sso_callback, name="sso_callback"),
    path("me/", views.account_home, name="account"),
    path("me/profile/", views.profile_update, name="profile_update"),
    path("me/photo/", views.photo_update, name="photo_update"),
    path("me/details/", views.profile_update, name="details"),
    path("me/password/", views.PasswordPage.as_view(), name="password_change"),
    path("password/change/", RedirectView.as_view(pattern_name="accounts:password_change")),
    path("password/reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:login")), name="password_reset_confirm"),
]
