import io
from datetime import date

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.certificates.models import Certificate
from apps.learning.models import Module
from apps.plants.models import Department, Plant
from apps.quizzes.models import Attempt
from apps.sops.models import SOPDocument, SOPVersion


class FlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.learner = User.objects.get(email="test_user@vishakha.com")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")

    def setUp(self):
        self.client.force_login(self.learner)

    def url(self, **q):
        base = reverse("learning:module_detail", args=[self.melt.slug])
        return base + ("?" + "&".join(f"{k}={v}" for k, v in q.items()) if q else "")

    def test_login_with_employee_id(self):
        self.client.logout()
        r = self.client.post(reverse("accounts:login"), {"username": "test_user", "password": "Test@12345"})
        self.assertRedirects(r, reverse("core:dashboard"))

    def test_pages_render(self):
        for name in ["core:dashboard", "core:plant_overview", "learning:module_list",
                     "quizzes:list", "sops:list", "certificates:list", "incidents:list",
                     "incidents:create"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        for tab in ["overview", "videos", "sops", "quiz", "problems", "discussion"]:
            self.assertEqual(self.client.get(self.url(tab=tab)).status_code, 200, tab)
        self.assertEqual(self.client.get(reverse("core:search") + "?q=furnace").status_code, 200)

    def test_plant_isolation(self):
        self.learner.plants.add(self.melt.plant)  # an admin restricted this user to VMPL P1
        other = Plant.objects.get(code="vrpl")
        dept = Department.objects.create(plant=other, name="Production")
        m = Module.objects.create(slug="vrpl_x", plant=other, department=dept, title="VRPL only")
        self.assertEqual(self.client.get(m.get_absolute_url()).status_code, 403)
        # cannot switch to a plant you don't have
        self.client.post(reverse("core:set_plant"), {"plant": other.pk})
        r = self.client.get(reverse("learning:module_list"))
        self.assertNotContains(r, "VRPL only")

    def test_safety_gate_steps_quiz_certificate(self):
        step1 = reverse("learning:toggle_step", args=[self.melt.slug, 1])
        # steps locked before safety acknowledgement
        self.client.post(step1)
        self.assertEqual(self.learner.module_progress.get(module=self.melt).steps_done, 0)
        # quiz locked before all steps
        r = self.client.post(reverse("quizzes:start", args=[self.melt.slug]))
        self.assertFalse(Attempt.objects.exists())

        self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))
        for step in self.melt.steps.all():
            self.client.post(reverse("learning:toggle_step", args=[self.melt.slug, step.number]))
        self.assertTrue(self.learner.module_progress.get(module=self.melt).all_steps_done)

        # fail once (pick wrong answers), then pass
        for pick_correct in (False, True):
            self.client.post(reverse("quizzes:start", args=[self.melt.slug]))
            attempt = Attempt.objects.filter(user=self.learner).first()
            for _ in attempt.question_ids:
                r = self.client.get(reverse("quizzes:take", args=[attempt.pk]))
                q = r.context["question"]
                choice = q.choices.filter(is_correct=pick_correct).first()
                self.client.post(reverse("quizzes:take", args=[attempt.pk]), {"choice": choice.pk})
            self.client.get(reverse("quizzes:take", args=[attempt.pk]))
            attempt.refresh_from_db()
            self.assertEqual(attempt.passed, pick_correct)
            self.assertEqual(Certificate.objects.filter(user=self.learner).exists(), pick_correct)

        cert = Certificate.objects.get(user=self.learner)
        self.assertEqual(self.client.get(cert.get_absolute_url()).status_code, 200)
        self.assertIsNotNone(self.learner.module_progress.get(module=self.melt).completed_at)

    def test_cannot_view_other_users_attempt(self):
        other = User.objects.create_user("x@y.com", "pw-12345678")
        other.plants.add(self.melt.plant)
        a = Attempt.objects.create(quiz=self.melt.quiz, user=other, question_ids=[])
        self.assertEqual(self.client.get(reverse("quizzes:take", args=[a.pk])).status_code, 404)

    def test_sop_versioning_only_one_active(self):
        dept = self.melt.department
        sop = SOPDocument.objects.create(plant=self.melt.plant, department=dept,
                                         code="VMPL/PRD/01", title="Melting")
        v1 = SOPVersion.objects.create(sop=sop, version="01", effective_date=date(2026, 1, 1),
                                       status="approved")
        v2 = SOPVersion.objects.create(sop=sop, version="02", effective_date=date(2026, 6, 1),
                                       status="approved")
        v1.refresh_from_db()
        self.assertEqual(v1.status, "superseded")
        self.assertEqual(sop.active_version, v2)
        r = self.client.get(reverse("sops:list"))
        self.assertContains(r, "Melting")
        # Draft-only SOPs are hidden from learners
        SOPDocument.objects.create(plant=self.melt.plant, department=dept, code="D1", title="DraftOnly")
        self.assertNotContains(self.client.get(reverse("sops:list")), "DraftOnly")

    def test_incident_report(self):
        r = self.client.post(reverse("incidents:create") + f"?module={self.melt.slug}", {
            "category": "safety", "title": "Hot metal splash", "description": "Near miss at tapping",
            "occurred_at": "2026-11-13T10:00"})
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse("incidents:list"))
        self.assertContains(r, "Hot metal splash")


class SuggestTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.learner = User.objects.get(email="test_user@vishakha.com")

    def setUp(self):
        self.client.force_login(self.learner)

    def test_suggest_returns_modules(self):
        r = self.client.get(reverse("core:suggest") + "?q=melt")
        self.assertEqual(r.status_code, 200)
        data = r.json()["results"]
        self.assertTrue(any(x["title"] == "Melt & Cast" and x["type"] == "module" for x in data))

    def test_suggest_short_query_empty_and_login_required(self):
        self.assertEqual(self.client.get(reverse("core:suggest") + "?q=m").json()["results"], [])
        self.client.logout()
        self.assertEqual(self.client.get(reverse("core:suggest") + "?q=melt").status_code, 302)

    def test_suggest_is_plant_scoped(self):
        other = Plant.objects.get(code="vrpl")
        dept = Department.objects.create(plant=other, name="Production")
        Module.objects.create(slug="vrpl_secret", plant=other, department=dept, title="Secret VRPL melt")
        titles = [x["title"] for x in self.client.get(reverse("core:suggest") + "?q=melt").json()["results"]]
        self.assertNotIn("Secret VRPL melt", titles)

    def test_step_dots_and_consent_gate_render(self):
        r = self.client.get(reverse("learning:module_detail", args=["vmpl_melt_cast"]) + "?tab=sops")
        self.assertContains(r, 'data-consent="agree-btn"')
        self.client.post(reverse("learning:ack_safety", args=["vmpl_melt_cast"]))
        r = self.client.get(reverse("learning:module_detail", args=["vmpl_melt_cast"]) + "?tab=sops")
        self.assertEqual(len(r.context["step_dots"]), 31)
