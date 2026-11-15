import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.i18n import localized
from apps.learning.models import Module, SOPStep

GU = "[઀-૿]"


class GujaratiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        call_command("seed_hindi", stdout=io.StringIO())
        call_command("seed_gujarati", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")
        cls.admin = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.user)

    def page(self, name, lang="gu", *args):
        self.client.cookies["django_language"] = lang
        return self.client.get(reverse(name, args=args)).content.decode()

    def test_language_menu_offers_three_languages(self):
        html = self.page("core:dashboard", "en")
        for label in ("English", "हिन्दी", "ગુજરાતી"):
            self.assertIn(label, html)

    def test_set_language_to_gujarati(self):
        r = self.client.post(reverse("set_language"), {"language": "gu", "next": "/"}, follow=True)
        self.assertIn('<html lang="gu">', r.content.decode())

    def test_ui_and_content_in_gujarati(self):
        html = self.page("learning:module_list")
        for needle in ("લર્નિંગ મોડ્યુલ", "મેલ્ટ અને કાસ્ટ", "પ્રોડક્શન", "મેન્ટેનન્સ"):
            self.assertIn(needle, html)
        self.assertNotIn(">Melt &amp; Cast<", html)

    def test_dashboard_and_nav_in_gujarati(self):
        html = self.page("core:dashboard")
        for needle in ("ડેશબોર્ડ", "જ્ઞાન ભંડાર", "તમે શું કરવા માંગો છો?"):
            self.assertIn(needle, html)

    def test_safety_rules_and_steps_in_gujarati(self):
        self.client.post(reverse("learning:ack_safety", args=["vmpl_melt_cast"]))
        html = self.page("learning:module_detail", "gu", "vmpl_melt_cast") + self.client.get(reverse("learning:module_detail", args=["vmpl_melt_cast"]) + "?tab=sops").content.decode()
        self.assertIn("સેફ્ટી હેલ્મેટ", html)
        self.assertIn("શું ન કરવું", html)

    def test_missing_gujarati_falls_back_to_english_not_hindi(self):
        m = Module.objects.get(slug="vmpl_melt_cast")
        m.title_gu = ""; m.title_hi = "हिन्दी शीर्षक"; m.save()
        self.client.cookies["django_language"] = "gu"
        from django.utils import translation
        with translation.override("gu"):
            self.assertEqual(localized(m, "title"), m.title)
        with translation.override("hi"):
            self.assertEqual(localized(m, "title"), "हिन्दी शीर्षक")

    def test_translation_note_names_the_gap(self):
        SOPStep.objects.filter(module__slug="vmpl_melt_cast", number=1).update(text_gu="")
        self.client.post(reverse("learning:ack_safety", args=["vmpl_melt_cast"]))
        self.client.cookies["django_language"] = "gu"
        html = self.client.get(reverse("learning:module_detail", args=["vmpl_melt_cast"]) + "?tab=sops&step=1").content.decode()
        self.assertIn("અનુવાદ ઉપલબ્ધ નથી", html)

    def test_seed_gujarati_never_overwrites(self):
        m = Module.objects.get(slug="vmpl_melt_cast")
        m.title_gu = "મારું પોતાનું શીર્ષક"; m.save()
        call_command("seed_gujarati", stdout=io.StringIO())
        m.refresh_from_db()
        self.assertEqual(m.title_gu, "મારું પોતાનું શીર્ષક")

    def test_quiz_in_gujarati(self):
        from apps.quizzes.models import Quiz
        q = Quiz.objects.get(module__slug="vmpl_melt_cast")
        self.client.post(reverse("learning:ack_safety", args=["vmpl_melt_cast"]))
        self.client.cookies["django_language"] = "gu"
        self.assertRegex(self.client.get(reverse("quizzes:list")).content.decode(), GU)
        self.assertTrue(q.questions.filter(text_gu__gt="").exists())

    def test_knowledge_base_in_gujarati(self):
        html = self.page("knowledge:home")
        self.assertIn("જ્ઞાન ભંડાર", html)
        self.assertIn("સુરક્ષા અને અનુપાલન", html)

    def test_admin_panel_can_edit_gujarati_text(self):
        self.client.force_login(self.admin)
        m = Module.objects.get(slug="vmpl_melt_cast")
        html = self.client.get(reverse("panel:module_edit", args=[m.pk])).content.decode()
        self.assertIn("Gujarati (optional)", html)
        r = self.client.get(reverse("panel:module_tab", args=[m.pk, "steps"])).content.decode()
        self.assertIn("Gujarati (optional)", r)

    def test_gujarati_columns_import(self):
        from apps.learning.importers import import_steps_bulk
        import_steps_bulk([{"module": "vmpl_melt_cast", "text": "Step A", "text_gu": "પગલું અ", "_row": 2}], replace=True)
        self.assertEqual(SOPStep.objects.get(module__slug="vmpl_melt_cast", number=1).text_gu, "પગલું અ")

    def test_every_page_works_in_every_language(self):
        """The 'never collapse' guarantee: crawl the learner and admin sites in all three languages."""
        from tests.test_crawl import CrawlTests  # reuse the crawler
        for lang in ("en", "hi", "gu"):
            for who, name in ((self.user, "learner"), (self.admin, "admin")):
                self.client.force_login(who)
                self.client.cookies["django_language"] = lang
                seen, queue, bad = set(), ["/"] + (["/manage/"] if name == "admin" else []), []
                import re
                while queue and len(seen) < 120:
                    u = queue.pop(0)
                    if u in seen or u.startswith(("/static", "/media", "/accounts/logout", "/i18n")):
                        continue
                    seen.add(u)
                    r = self.client.get(u, follow=True)
                    if r.status_code >= 500:
                        bad.append((lang, name, u, r.status_code))
                    if r.status_code == 200 and "text/html" in r["Content-Type"]:
                        queue += re.findall(r'href="(/[^"#]*)', r.content.decode())
                self.assertEqual(bad, [], f"{lang}/{name}")


class ReadAloudAndErrorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def setUp(self):
        self.client.force_login(User.objects.get(employee_id="test_user"))

    def test_plant_overview_has_read_aloud(self):
        html = self.client.get(reverse("core:plant_overview")).content.decode()
        self.assertIn('data-speak="#plant-read"', html)
        self.assertIn('id="plant-read"', html)

    def test_every_read_aloud_page_has_the_stop_script_and_buttons(self):
        js = open("static/js/shiksha.js", encoding="utf8").read()
        self.assertIn("addStopButtons", js)
        self.assertIn("data-speak-stop", js)

    def test_error_pages_are_friendly(self):
        from django.test import override_settings
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            self.client.raise_request_exception = False
            r = self.client.get("/definitely/not/here/")
            self.assertEqual(r.status_code, 404)
            self.assertContains(r, "Page not found", status_code=404)

    def test_expired_form_shows_friendly_page(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(User.objects.get(employee_id="test_user"))
        r = c.post(reverse("core:set_plant"), {"plant": 1})
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "Your page expired", status_code=403)

    def test_500_template_renders_without_any_context(self):
        from django.template.loader import render_to_string
        from django.utils import translation
        with translation.override("en"):
            html = render_to_string("500.html")
        self.assertIn("Something went wrong", html)


class GujaratiContentEverywhereTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        call_command("seed_gujarati", stdout=io.StringIO())

    def setUp(self):
        self.client.force_login(User.objects.get(employee_id="test_user"))
        self.client.cookies["django_language"] = "gu"

    def test_plant_overview_about_is_gujarati(self):
        html = self.client.get(reverse("core:plant_overview")).content.decode()
        self.assertIn("વિશાખા મેટલ્સ પ્રાઇવેટ લિમિટેડ", html)
        self.assertNotIn("is one of India's leading manufacturers", html)
        self.assertIn('data-speak="#plant-read"', html)

    def test_dates_use_gujarati_month_names(self):
        from django.template import Context, Template
        from django.utils import translation
        import datetime
        with translation.override("gu"):
            out = Template('{{ d|date:"d M Y" }}').render(Context({"d": datetime.date(2026, 11, 13)}))
        self.assertEqual(out, "13 નવે 2026")

    def test_incident_form_is_translated_with_localised_departments(self):
        html = self.client.get(reverse("incidents:create")).content.decode()
        self.assertIn("વિભાગ", html)                  # "Department" label
        self.assertIn("પ્રોડક્શન (", html)            # localised department name in the dropdown

    def test_module_objectives_in_gujarati(self):
        html = self.client.get(reverse("learning:module_detail", args=["vmpl_melt_cast"])).content.decode()
        self.assertIn("ઠંડી ફર્નેસ શરૂ કરવાની તપાસ સમજો", html)

    def test_speech_engine_falls_back_to_hindi_voice_for_gujarati(self):
        js = open("static/js/shiksha.js", encoding="utf8").read()
        self.assertIn("gu2dev", js)
        self.assertIn("0x180", js)
        self.assertIn("pieces(", js)
