import io
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.certificates.models import Certificate
from apps.learning.models import Module


class V3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.learner = User.objects.get(employee_id="test_user")
        cls.admin = User.objects.get(employee_id="test_admin")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")
        cls.cert = Certificate.objects.create(user=cls.learner, module=cls.melt, score_percent=100)

    # ---- certificates ----
    def test_pdf_download_is_real_pdf_with_name_filename(self):
        self.client.force_login(self.learner)
        r = self.client.get(reverse("certificates:download", args=[self.cert.code]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertIn("Test_User_Melt_Cast", r["Content-Disposition"])
        self.assertGreater(len(r.content), 5000)

    def test_certificate_shows_profile_name_and_follows_edits(self):
        self.client.force_login(self.learner)
        self.assertContains(self.client.get(self.cert.get_absolute_url()), "Test User")
        self.client.post(reverse("accounts:profile_update"), {"first_name": "Ravi", "last_name": "Patel"})
        self.assertContains(self.client.get(self.cert.get_absolute_url()), "Ravi Patel")

    def test_name_falls_back_to_email_when_profile_blank(self):
        u = User.objects.create_user("anil.kumar@vishakha.com", "Pass-12345-xx")
        c = Certificate.objects.create(user=u, module=self.melt)
        self.assertEqual(c.holder_name, "Anil Kumar")

    def test_other_users_cannot_download_my_certificate(self):
        other = User.objects.get(employee_id="test_user2")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("certificates:download", args=[self.cert.code])).status_code, 404)

    def test_public_verify_page_works_without_login(self):
        r = self.client.get(reverse("certificates:verify", args=[self.cert.code]))
        self.assertContains(r, "Valid certificate")
        self.assertContains(r, "Test User")
        import uuid
        self.assertEqual(self.client.get(reverse("certificates:verify", args=[uuid.uuid4()])).status_code, 404)

    def test_profile_requires_both_names(self):
        self.client.force_login(self.learner)
        self.client.post(reverse("accounts:profile_update"), {"first_name": "", "last_name": "X"})
        self.learner.refresh_from_db()
        self.assertEqual(self.learner.first_name, "Test")

    # ---- admin: preview as learner ----
    def test_admin_can_preview_learner_view_and_return(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("core:dashboard")), "Manage Content")
        self.client.post(reverse("core:view_mode"), {"mode": "learner", "next": "/"})
        r = self.client.get(reverse("core:dashboard"))
        self.assertContains(r, "Learner view")
        self.assertNotContains(r, "Manage Content")
        self.assertContains(r, "Back to admin view")
        self.client.post(reverse("core:view_mode"), {"mode": "admin", "next": "/"})
        r = self.client.get(reverse("core:dashboard"))
        self.assertContains(r, "Manage Content")
        self.assertNotContains(r, "Learner view —")

    def test_learner_view_hides_admin_incident_controls(self):
        from apps.incidents.models import Incident
        inc = Incident.objects.create(plant=self.melt.plant, title="Leak", description="x", reported_by=self.learner)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(inc.get_absolute_url()), "Update status")
        self.client.post(reverse("core:view_mode"), {"mode": "learner"})
        self.assertEqual(self.client.get(inc.get_absolute_url()).status_code, 404)  # learner can't see others' incidents

    def test_learners_cannot_toggle_view_mode(self):
        self.client.force_login(self.learner)
        self.client.post(reverse("core:view_mode"), {"mode": "learner"})
        r = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(r, "Learner view —")
        self.assertNotContains(r, "Preview as learner")

    # ---- UI structure ----
    def test_modules_grouped_into_swipe_sections(self):
        self.client.force_login(self.learner)
        r = self.client.get(reverse("learning:module_list"))
        self.assertContains(r, "mod-section")
        self.assertContains(r, "hscroll")
        self.assertEqual([s["dept"].name for s in r.context["sections"]], ["Production", "QC", "Maintenance"])

    def test_bottom_nav_marks_current_page(self):
        self.client.force_login(self.learner)
        r = self.client.get(reverse("quizzes:list"))
        self.assertRegex(r.content.decode(), r'<a href="/quizzes/" class="active"><span class="bn-ico">')

    def test_brand_name_is_vishakha_ai(self):
        self.client.force_login(self.learner)
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn("Vishakha AI", html)
        self.assertNotIn("VIVI", html)


class CelebrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user2")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")

    def setUp(self):
        self.client.force_login(self.user)
        self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))

    def _complete_all(self):
        for st in self.melt.steps.all():
            self.client.post(reverse("learning:toggle_step", args=[self.melt.slug, st.number]))

    def test_finishing_last_step_celebrates_once(self):
        url = reverse("learning:module_detail", args=[self.melt.slug]) + "?tab=sops"
        self._complete_all()
        r = self.client.get(url)
        self.assertContains(r, 'id="celebrate-src"')
        self.assertContains(r, "All steps complete!")
        self.assertNotContains(self.client.get(url), 'id="celebrate-src"')  # one-shot

    def test_ordinary_step_does_not_celebrate(self):
        self.client.post(reverse("learning:toggle_step", args=[self.melt.slug, 1]))
        r = self.client.get(reverse("learning:module_detail", args=[self.melt.slug]) + "?tab=sops")
        self.assertNotContains(r, 'id="celebrate-src"')

    def test_passing_quiz_celebrates_on_result_once(self):
        self._complete_all()
        self.client.get(reverse("learning:module_detail", args=[self.melt.slug]))  # consume the steps popup
        self.client.post(reverse("quizzes:start", args=[self.melt.slug]))
        from apps.quizzes.models import Attempt
        att = Attempt.objects.filter(user=self.user).first()
        for _ in att.question_ids:
            q = self.client.get(reverse("quizzes:take", args=[att.pk])).context["question"]
            self.client.post(reverse("quizzes:take", args=[att.pk]), {"choice": q.choices.get(is_correct=True).pk})
        self.client.get(reverse("quizzes:take", args=[att.pk]))
        res = reverse("quizzes:result", args=[att.pk])
        self.assertContains(self.client.get(res), "You passed!")
        self.assertNotContains(self.client.get(res), 'id="celebrate-src"')

    def test_soft_navigation_hooks_present(self):
        html = self.client.get(reverse("learning:module_detail", args=[self.melt.slug]) + "?tab=sops").content.decode()
        for needle in ('id="sop-area"', 'id="mod-head"', 'id="mod-tabs"', "data-soft-form", "data-soft "):
            self.assertIn(needle, html)

    def test_mobile_logo_in_topbar(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn('class="top-logo"', html)
