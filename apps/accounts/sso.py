"""Microsoft Entra ID (Azure AD) sign-in using the OAuth2 authorization-code flow (MSAL)."""
import msal
from django.conf import settings

SCOPES = []  # openid/profile/email are added by MSAL automatically


def _app():
    return msal.ConfidentialClientApplication(
        settings.ENTRA_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}",
        client_credential=settings.ENTRA_CLIENT_SECRET)


def begin(request, redirect_uri):
    flow = _app().initiate_auth_code_flow(SCOPES, redirect_uri=redirect_uri)
    request.session["sso_flow"] = flow
    return flow["auth_uri"]


def finish(request, redirect_uri):
    """Return (email, first_name, last_name) of the signed-in Microsoft user, or raise ValueError."""
    flow = request.session.pop("sso_flow", None)
    if not flow:
        raise ValueError("Sign-in session expired. Please try again.")
    result = _app().acquire_token_by_auth_code_flow(flow, request.GET.dict())
    if "error" in result:
        raise ValueError(result.get("error_description") or result["error"])
    claims = result.get("id_token_claims") or {}
    email = (claims.get("email") or claims.get("preferred_username") or "").strip().lower()
    if not email:
        raise ValueError("Microsoft did not return an email address for this account.")
    name = claims.get("name") or ""
    first, _, last = name.partition(" ")
    return email, first, last
