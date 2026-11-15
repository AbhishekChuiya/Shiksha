import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.knowledge.models import KBCategory, KBItem
from apps.learning.models import Module


class AdvancedAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.boss = User.objects.get(email="test_admin@vishakha.com")
        cls.root = User.objects.create_superuser(email="root@vishakha.com", password="Str0ng-Pass-9917")

    def test_panel_admin_has_no_django_admin(self):
        self.assertTrue(self.boss.is_shiksha_admin)
        self.assertFalse(self.boss.is_staff or self.boss.is_superuser)
        self.client.force_login(self.boss)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 302)       # bounced to the admin login
        self.assertNotContains(self.client.get(reverse("panel:dashboard")), "Advanced admin")

    def test_staff_flag_cannot_be_set_on_non_superusers(self):
        self.boss.is_staff = True
        self.boss.save()
        self.boss.refresh_from_db()
        self.assertFalse(self.boss.is_staff)

    def test_createsuperuser_account_gets_it(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertContains(self.client.get(reverse("panel:dashboard")), "Advanced admin")

    def test_panel_admin_cannot_edit_a_superuser(self):
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get(reverse("panel:user_edit", args=[self.root.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("panel:user_reset", args=[self.root.pk])).status_code, 403)


class SafetyColourTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def test_groups_are_colour_coded(self):
        self.client.force_login(User.objects.get(employee_id="test_user"))
        html = self.client.get(reverse("learning:module_detail", args=["vmpl_extrusion"]) + "?tab=sops").content.decode()
        for css in ("g-ppe", "g-hazard", "g-do", "g-dont", "g-env"):
            self.assertIn(f"gl-card {css}", html)
        self.assertIn("Safety helmet", html)

    def test_hindi_headings(self):
        u = User.objects.get(employee_id="test_user")
        self.client.force_login(u)
        self.client.post(reverse("set_language"), {"language": "hi", "next": "/"})
        html = self.client.get(reverse("learning:module_detail", args=["vmpl_extrusion"]) + "?tab=sops").content.decode()
        self.assertIn("क्या न करें", html)
        self.assertIn("सेफ्टी हेलमेट", html)


class KnowledgeBaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.learner = User.objects.get(employee_id="test_user")
        cls.boss = User.objects.get(employee_id="test_admin")

    def test_page_lists_sops_videos_and_documents_by_category(self):
        self.client.force_login(self.learner)
        html = self.client.get(reverse("knowledge:home")).content.decode()
        self.assertIn("Knowledge Base", html)
        self.assertIn("Safety &amp; compliance", html)
        self.assertIn("Emergency evacuation plan", html)

    def test_search_and_kind_filters(self):
        self.client.force_login(self.learner)
        r = self.client.get(reverse("knowledge:home"), {"q": "evacuation"})
        self.assertContains(r, "Emergency evacuation plan"); self.assertNotContains(r, "Shift handover")
        r = self.client.get(reverse("knowledge:home"), {"kind": "video"})
        self.assertContains(r, "Fire safety basics")
        self.assertNotContains(r, "Emergency evacuation plan")

    def test_pdf_opens_inline_and_downloads(self):
        self.client.force_login(self.learner)
        it = KBItem.objects.get(title="Emergency evacuation plan")
        self.assertEqual(it.kind, "pdf")
        self.assertContains(self.client.get(it.get_absolute_url()), "<iframe")
        r = self.client.get(reverse("knowledge:file", args=[it.pk]))
        self.assertEqual(r["Content-Type"], "application/pdf"); self.assertNotIn("attachment", r["Content-Disposition"])
        self.assertIn("attachment", self.client.get(reverse("knowledge:file", args=[it.pk]) + "?dl=1")["Content-Disposition"])

    def test_login_required_and_hidden_items(self):
        it = KBItem.objects.get(title="Emergency evacuation plan")
        self.assertEqual(self.client.get(it.get_absolute_url()).status_code, 302)
        it.is_active = False; it.save()
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get(it.get_absolute_url()).status_code, 404)

    def test_youtube_link_is_embedded(self):
        self.client.force_login(self.learner)
        it = KBItem.objects.get(title__startswith="Fire safety")
        self.assertEqual(it.kind, "video")
        self.assertContains(self.client.get(it.get_absolute_url()), "youtube.com/embed/")

    def test_admin_adds_and_removes_documents(self):
        self.client.force_login(self.boss)
        cat = KBCategory.objects.first()
        f = SimpleUploadedFile("Furnace manual.xlsx", b"x")
        r = self.client.post(reverse("panel:kb_new"), {"title": "Furnace sheet", "category": cat.pk, "is_active": "on", "order": 0, "file": f})
        it = KBItem.objects.get(title="Furnace sheet")
        self.assertRedirects(r, reverse("panel:kb_edit", args=[it.pk]), fetch_redirect_response=False)
        self.assertEqual(it.kind, "sheet")
        bad = self.client.post(reverse("panel:kb_new"), {"title": "Empty", "category": cat.pk, "order": 0})
        self.assertContains(bad, "Upload a file or paste a link")
        self.client.post(reverse("panel:kb_delete", args=[it.pk]))
        self.assertFalse(KBItem.objects.filter(pk=it.pk).exists())
        self.assertEqual(self.client.get(reverse("panel:kb")).status_code, 200)

    def test_learners_cannot_use_the_panel_pages(self):
        self.client.force_login(self.learner)
        self.assertNotEqual(self.client.get(reverse("panel:kb")).status_code, 200)

    def test_categories_editor_page(self):
        self.client.force_login(self.boss)
        self.assertContains(self.client.get(reverse("panel:kb_categories")), "Machine manuals")


class BestScoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())

    def test_chart_has_one_bar_per_module_with_the_best_score(self):
        from django.utils import timezone
        from apps.core.charts import learner_charts
        from apps.quizzes.models import Attempt, Quiz
        u = User.objects.get(employee_id="test_user2")
        quiz = Quiz.objects.get(module__slug="vmpl_melt_cast")
        for score in (50, 0, 50, 100, 50):                 # several tries, the last one is worse
            Attempt.objects.create(quiz=quiz, user=u, finished_at=timezone.now(), score_percent=score, passed=score >= 80)
        scores = learner_charts(u, quiz.module.plant)["scores"]
        self.assertEqual(len(scores), 1)
        self.assertEqual((scores[0]["value"], scores[0]["tone"]), (100, "ok"))

    def test_three_departments_exist(self):
        from apps.plants.models import Department
        names = set(Department.objects.filter(plant__code="vmpl-p1").values_list("name", flat=True))
        self.assertTrue({"Production", "QC", "Maintenance"} <= names)
        self.assertTrue(Module.objects.filter(department__name="Maintenance").exists())
