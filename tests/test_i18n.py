import io
import re
import sys
from pathlib import Path

import polib
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learning.models import Module, SOPStep

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import extract_strings  # noqa: E402

PH = re.compile(r"%\((\w+)\)s")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


class CatalogCoverageTests(TestCase):
    """Every wrapped UI string must have a Hindi translation — new untranslated text fails this test."""

    def _check(self, lang):
        po = polib.pofile(str(ROOT / "locale" / lang / "LC_MESSAGES" / "django.po"))
        have = {e.msgid: e for e in po}
        missing, broken = [], []
        for msgid, plural in extract_strings.all_strings().items():
            e = have.get(msgid)
            if e is None or not (e.msgstr or any(e.msgstr_plural.values())):
                missing.append(msgid); continue
            forms = [e.msgstr] if not plural else list(e.msgstr_plural.values())
            for f in forms:
                if set(PH.findall(f)) != set(PH.findall(msgid)):
                    broken.append(msgid)
        self.assertEqual(missing, [], f"{lang}: strings without translation — add them to scripts/translations_more.py")
        self.assertEqual(broken, [], f"{lang}: placeholders changed")

    def test_hindi_complete(self):
        self._check("hi")

    def test_gujarati_complete(self):
        self._check("gu")

    def test_hinglish_is_gone(self):
        from django.conf import settings
        self.assertEqual([c for c, _ in settings.LANGUAGES], ["en", "hi", "gu"])
        self.assertFalse((ROOT / "locale" / "hi_Latn").exists())

    def test_compiled_catalogs_are_fresh(self):
        for lang in ("hi", "gu"):
            base = ROOT / "locale" / lang / "LC_MESSAGES"
            self.assertGreaterEqual((base / "django.mo").stat().st_mtime + 5, (base / "django.po").stat().st_mtime)


class HindiPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")

    def setUp(self):
        self.client.force_login(self.user)
        self.client.cookies["django_language"] = "hi"

    def get(self, name, *args, qs=""):
        return self.client.get(reverse(name, args=list(args)) + qs).content.decode()

    def test_module_list_is_hindi(self):
        html = self.get("learning:module_list")
        for needle in ("मेल्ट और कास्ट", "प्रोडक्शन", "सभी", "फ़िल्टर", "जारी रखें" if False else "शुरू करें"):
            self.assertIn(needle, html)
        self.assertNotIn(">Melt &amp; Cast<", html)

    def test_dashboard_navigation_and_greeting_hindi(self):
        html = self.get("core:dashboard")
        for needle in ("डैशबोर्ड", "सीखें", "सहायता", "आप क्या करना चाहेंगे?", "जल्द"):
            self.assertIn(needle, html)

    def test_safety_and_steps_hindi_and_read_aloud_target_is_devanagari(self):
        self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))
        html = self.get("learning:module_detail", self.melt.slug, qs="?tab=sops")
        self.assertIn("सुरक्षा", html)
        self.assertIn("पर्यावरण, गुणवत्ता और अनुशासन", html)
        self.assertIn("हर नियर-मिस घटना की सूचना", html)
        m = re.search(r'id="step-text">([^<]+)<', html)
        self.assertTrue(DEVANAGARI.search(m.group(1)), "read-aloud reads #step-text — it must be Hindi text")

    def test_no_english_note_when_hindi_exists_but_shown_when_missing(self):
        self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))
        url = ("learning:module_detail", self.melt.slug)
        self.assertNotIn("Hindi translation not available", self.get(*url, qs="?tab=sops"))
        SOPStep.objects.filter(module=self.melt, number=1).update(text_hi="")
        self.assertIn("अनुवाद उपलब्ध नहीं", self.get(*url, qs="?tab=sops&step=1"))

    def test_plant_overview_and_departments_hindi(self):
        html = self.get("core:plant_overview")
        self.assertIn("विशाखा मेटल्स प्राइवेट लिमिटेड", html)
        self.assertIn("मुंद्रा, गुजरात", html)
        self.assertIn("क्यूसी", html)

    def test_quiz_question_options_hindi(self):
        for st in self.melt.steps.all():
            self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))
            self.client.post(reverse("learning:toggle_step", args=[self.melt.slug, st.number]))
        self.client.post(reverse("quizzes:start", args=[self.melt.slug]))
        from apps.quizzes.models import Attempt
        att = Attempt.objects.filter(user=self.user).first()
        html = self.client.get(reverse("quizzes:take", args=[att.pk])).content.decode()
        self.assertTrue(DEVANAGARI.search(html.split('class="question"')[1][:200]))
        self.assertIn("नैदानिक", html)  # the "Diagnostic" label

    def test_english_ui_unchanged(self):
        self.client.cookies["django_language"] = "en"
        html = self.get("learning:module_list")
        self.assertIn("Melt &amp; Cast", html)
        self.assertNotIn("मेल्ट", html)

    def test_seed_hindi_never_overwrites_existing_hindi(self):
        self.melt.title_hi = "मेरा अपना शीर्षक"
        self.melt.save()
        call_command("seed_hindi", stdout=io.StringIO())
        self.melt.refresh_from_db()
        self.assertEqual(self.melt.title_hi, "मेरा अपना शीर्षक")

    def test_html_lang_and_i18n_json_for_js(self):
        html = self.get("core:dashboard")
        self.assertIn('<html lang="hi">', html)
        self.assertIn('"copied":"', html)
        self.assertIn('"copied":"लिंक कॉपी हो गया।"', html)  # Hindi toast text reaches the JS dictionary

    def test_plant_switch_from_detail_page_goes_to_dashboard(self):
        from apps.plants.models import Plant
        other = Plant.objects.exclude(pk=self.melt.plant_id).first()
        r = self.client.post(reverse("core:set_plant"), {"plant": other.pk,
                             "next": reverse("learning:module_detail", args=[self.melt.slug])})
        self.assertRedirects(r, reverse("core:dashboard"), fetch_redirect_response=False)
        r = self.client.post(reverse("core:set_plant"), {"plant": other.pk, "next": "/modules/"})
        self.assertRedirects(r, "/modules/", fetch_redirect_response=False)

    def test_opening_a_module_follows_its_plant(self):
        from apps.plants.models import Plant
        other = Plant.objects.exclude(pk=self.melt.plant_id).first()
        self.client.post(reverse("core:set_plant"), {"plant": other.pk, "next": "/"})
        html = self.get("learning:module_detail", self.melt.slug)
        self.assertRegex(html, r'<span class="lbl">VMPL P1</span>')
