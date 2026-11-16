import io
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.plants.models import Plant


class SignupTests(TestCase):
    def signup(self, email="new.person@vishakha.com", **extra):
        data = {"first_name": "New", "last_name": "Person", "email": email, "employee_id": "",
                "password1": "Str0ng-Pass-9917", "password2": "Str0ng-Pass-9917"}
        data.update(extra)
        return self.client.post(reverse("accounts:signup"), data)

    def test_signup_requires_verification_before_login(self):
        r = self.signup()
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(email="new.person@vishakha.com")
        self.assertFalse(u.is_active)
        self.assertIsNone(u.employee_id)  # blank must be NULL, not ""
        self.assertFalse(self.client.login(username=u.email, password="Str0ng-Pass-9917"))
        link = next(l for l in mail.outbox[0].body.split() if "/verify/" in l)
        r = self.client.get(link.replace("http://testserver", ""))
        self.assertRedirects(r, reverse("accounts:login"))
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        self.assertTrue(self.client.login(username=u.email, password="Str0ng-Pass-9917"))

    def test_two_signups_without_employee_id_do_not_collide(self):
        self.signup("a.one@vishakha.com")
        self.signup("b.two@vishakha.com")
        self.assertEqual(User.objects.filter(employee_id__isnull=True).count(), 2)

    def test_other_domains_rejected(self):
        self.signup("someone@gmail.com")
        self.assertFalse(User.objects.filter(email="someone@gmail.com").exists())

    def test_duplicate_email_rejected(self):
        self.signup()
        self.signup()
        self.assertEqual(User.objects.filter(email="new.person@vishakha.com").count(), 1)

    def test_bad_verification_link(self):
        r = self.client.get(reverse("accounts:verify_email", args=["abc", "bad-token"]))
        self.assertEqual(r.status_code, 400)

    def test_password_reset_sends_mail(self):
        User.objects.create_user("known@vishakha.com", "Old-Pass-12345")
        self.client.post(reverse("accounts:password_reset"), {"email": "known@vishakha.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)


class AccessTests(TestCase):
    def test_everyone_signed_in_can_use_the_app_without_plant_assignment(self):
        Plant.objects.create(code="p1", name="P1")
        Plant.objects.create(code="p2", name="P2")
        u = User.objects.create_user("noplant@vishakha.com", "Pass-12345-xx")
        self.client.force_login(u)
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(u.accessible_plants().count(), 2)

    def test_explicit_plant_assignment_still_restricts(self):
        p1 = Plant.objects.create(code="p1", name="P1")
        Plant.objects.create(code="p2", name="P2")
        u = User.objects.create_user("scoped@vishakha.com", "Pass-12345-xx")
        u.plants.add(p1)
        self.assertEqual(list(u.accessible_plants()), [p1])

    def test_switch_account_logs_out_and_shows_login(self):
        u = User.objects.create_user("sw@vishakha.com", "Pass-12345-xx")
        self.client.force_login(u)
        r = self.client.post(reverse("accounts:logout") + "?next=" + reverse("accounts:login"))
        self.assertRedirects(r, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)


class DomainRuleTests(TestCase):
    def test_only_company_domain_can_sign_in(self):
        User.objects.create_user("ok@vishakha.com", "Pass-12345-xx")
        User.objects.create_user("bad@gmail.com", "Pass-12345-xx")
        login = reverse("accounts:login")
        r = self.client.post(login, {"username": "bad@gmail.com", "password": "Pass-12345-xx"})
        self.assertContains(r, "Only company accounts can sign in")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(self.client.login(username="bad@gmail.com", password="Pass-12345-xx"))  # backend too
        r = self.client.post(login, {"username": "ok@vishakha.com", "password": "Pass-12345-xx"})
        self.assertRedirects(r, reverse("core:dashboard"), fetch_redirect_response=False)

    def test_domain_check_is_case_insensitive(self):
        User.objects.create_user("Mixed.Case@vishakha.com", "Pass-12345-xx")
        self.assertTrue(self.client.login(username="mixed.case@VISHAKHA.com", password="Pass-12345-xx"))


class TestAccountsTests(TestCase):
    def test_test_accounts_can_sign_in_by_short_name(self):
        from django.core.management import call_command
        call_command("create_test_users", stdout=io.StringIO())
        for name in ("test_user", "test_admin", "test_manager"):
            self.client.logout()
            r = self.client.post(reverse("accounts:login"), {"username": name, "password": "Test@12345"})
            self.assertRedirects(r, reverse("core:dashboard"), fetch_redirect_response=False, msg_prefix=name)
        self.assertTrue(User.objects.get(employee_id="test_admin").is_shiksha_admin)
        self.assertFalse(User.objects.get(employee_id="test_user").is_shiksha_admin)


@override_settings(SSO_ENABLED=True, ENTRA_TENANT_ID="t", ENTRA_CLIENT_ID="c", ENTRA_CLIENT_SECRET="s")
class SSOTests(TestCase):
    def test_login_page_shows_microsoft_button(self):
        self.assertContains(self.client.get(reverse("accounts:login")), "Continue with Microsoft")

    @mock.patch("apps.accounts.views.sso.finish")
    def test_callback_creates_user_and_logs_in(self, finish):
        Plant.objects.create(code="vrpl", name="VRPL")
        finish.return_value = ("raj.kumar@vishakha.com", "Raj", "Kumar")
        with override_settings(DEFAULT_NEW_USER_PLANT_CODES=["vrpl"]):
            r = self.client.get(reverse("accounts:sso_callback"))
        self.assertRedirects(r, reverse("core:dashboard"), fetch_redirect_response=False)
        u = User.objects.get(email="raj.kumar@vishakha.com")
        self.assertEqual(u.role, "learner")
        self.assertEqual(list(u.plants.values_list("code", flat=True)), ["vrpl"])
        self.assertFalse(u.has_usable_password())

    @mock.patch("apps.accounts.views.sso.finish")
    def test_callback_rejects_foreign_domain(self, finish):
        finish.return_value = ("outsider@example.com", "O", "S")
        self.client.get(reverse("accounts:sso_callback"))
        self.assertFalse(User.objects.filter(email="outsider@example.com").exists())
        self.assertNotIn("_auth_user_id", self.client.session)

    @mock.patch("apps.accounts.views.sso.finish", side_effect=ValueError("boom"))
    def test_callback_error_is_handled(self, _):
        r = self.client.get(reverse("accounts:sso_callback"))
        self.assertRedirects(r, reverse("accounts:login"))

    def test_sso_not_configured_shows_button_and_a_friendly_page(self):
        with override_settings(SSO_ENABLED=False):
            self.assertContains(self.client.get(reverse("accounts:login")), "Login via SSO")
            r = self.client.get(reverse("accounts:sso_login"))
            self.assertContains(r, "SSO is being set up")
            self.assertContains(r, "Back to employee sign in")
            self.assertContains(r, reverse("accounts:login"))


class EmailTests(TestCase):
    def test_verification_email_is_html_and_text(self):
        self.client.post(reverse("accounts:signup"), {
            "first_name": "A", "last_name": "B", "email": "html.check@vishakha.com", "employee_id": "",
            "password1": "Str0ng-Pass-9917", "password2": "Str0ng-Pass-9917"})
        m = mail.outbox[0]
        self.assertIn("/verify/", m.body)
        html = m.alternatives[0][0]
        self.assertIn("Verify my email", html)
        self.assertIn("/verify/", html)

    def test_reset_email_is_html_with_link(self):
        User.objects.create_user("r@vishakha.com", "Old-Pass-12345")
        self.client.post(reverse("accounts:password_reset"), {"email": "r@vishakha.com"})
        m = mail.outbox[0]
        self.assertEqual(m.subject, "Reset your Project Shiksha password")
        self.assertIn("/accounts/password/reset/", m.alternatives[0][0])

    @mock.patch("apps.accounts.views.send_branded", side_effect=OSError("smtp down"))
    def test_signup_survives_smtp_failure_and_leaves_no_ghost_account(self, _):
        r = self.client.post(reverse("accounts:signup"), {
            "first_name": "A", "last_name": "B", "email": "ghost@vishakha.com", "employee_id": "",
            "password1": "Str0ng-Pass-9917", "password2": "Str0ng-Pass-9917"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "couldn&#x27;t send the verification email")
        self.assertFalse(User.objects.filter(email="ghost@vishakha.com").exists())

    def test_reset_survives_smtp_failure(self):
        User.objects.create_user("down@vishakha.com", "Old-Pass-12345")
        with mock.patch("django.contrib.auth.forms.PasswordResetForm.send_mail", side_effect=OSError("x")):
            r = self.client.post(reverse("accounts:password_reset"), {"email": "down@vishakha.com"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "send the email right now")


class ThemeAndResetDiagnosticsTests(TestCase):
    def test_sign_in_pages_are_always_light(self):
        for name in ("accounts:login", "accounts:signup", "accounts:password_reset"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIn('setAttribute("data-theme","light")', html, name)
            self.assertNotIn("prefers-color-scheme", html, name)

    def test_app_defaults_to_light_even_if_phone_is_dark(self):
        from django.core.management import call_command
        call_command("seed_demo", stdout=io.StringIO())
        self.client.force_login(User.objects.get(employee_id="test_user"))
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertNotIn("prefers-color-scheme", html)
        self.assertIn('var t="light"', html)

    def test_dev_note_when_no_account_has_the_email(self):
        from django.test import override_settings
        with override_settings(DEBUG=True):
            r = self.client.post(reverse("accounts:password_reset"), {"email": "ghost@vishakha.com"}, follow=True)
        self.assertContains(r, "no active account has this email")
        self.assertEqual(len(mail.outbox), 0)
        with override_settings(DEBUG=False):   # never reveals whether an address exists in production
            r = self.client.post(reverse("accounts:password_reset"), {"email": "ghost@vishakha.com"}, follow=True)
        self.assertNotContains(r, "no active account")

    def test_smtp_error_reason_visible_only_in_debug(self):
        from django.test import override_settings
        User.objects.create_user("real@vishakha.com", "Old-Pass-12345")
        with mock.patch("django.contrib.auth.forms.PasswordResetForm.send_mail", side_effect=OSError("SMTP boom")):
            with override_settings(DEBUG=True):
                r = self.client.post(reverse("accounts:password_reset"), {"email": "real@vishakha.com"})
                self.assertContains(r, "SMTP boom")
            with override_settings(DEBUG=False):
                r = self.client.post(reverse("accounts:password_reset"), {"email": "real@vishakha.com"})
                self.assertNotContains(r, "SMTP boom")
                self.assertContains(r, "send the email right now")

    def test_send_reset_link_command_reports_each_case(self):
        from io import StringIO
        from django.core.management import call_command
        User.objects.create_user("cmd@vishakha.com", "Old-Pass-12345")
        User.objects.create_user("off@vishakha.com", "Old-Pass-12345", is_active=False)
        out = StringIO(); call_command("send_reset_link", "cmd@vishakha.com", stdout=out)
        self.assertIn("Sent.", out.getvalue()); self.assertEqual(len(mail.outbox), 1)
        out = StringIO(); call_command("send_reset_link", "nobody@vishakha.com", stdout=out)
        self.assertIn("No account exists", out.getvalue())
        out = StringIO(); call_command("send_reset_link", "off@vishakha.com", stdout=out)
        self.assertIn("INACTIVE", out.getvalue())
