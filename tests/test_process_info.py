import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learning.models import Module, ModuleSOP, SOPAcknowledgement, SOPStep, SafetyGuideline


class ProcessInfoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.module = Module.objects.filter(title="Extrusion", sops__isnull=False).distinct().get()
        cls.learner = User.objects.get(employee_id="test_user2")
        cls.admin = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.learner)

    def url(self, **q):
        return reverse("learning:module_detail", args=[self.module.slug]) + "?" + "&".join(f"{k}={v}" for k, v in q.items())

    def test_overview_shows_purpose_roles_records_and_escalation(self):
        html = self.client.get(self.url(tab="overview")).content.decode()
        for needle in ("Purpose", "Maintain production of EVA/POE/EPE", "Who does what", "Sampling of finished rolls", "Production Supervisor / QC Head",
                       "Records", "VRPL/IMS/PRD/F/01", "Who to call", "Process parameter outage", "Escalate immediately"):
            self.assertIn(needle, html)

    def test_accountable_names_are_listed_once(self):
        self.assertEqual(self.module.accountable_summary, "Production Supervisor / QC Head")

    def test_four_sops_each_with_own_steps(self):
        sops = list(self.module.sops.all())
        self.assertEqual(len(sops), 4)
        self.assertEqual([s.steps.count() for s in sops], [37, 22, 27, 22])
        html = self.client.get(self.url(tab="sops")).content.decode()
        self.assertEqual(html.count('class="sop-pick-card'), 4)
        self.assertIn("0/37", html)
        self.assertIn("EPE Extrusion Line Startup Procedure (SOP 4)", html)

    def test_document_info_and_safety_cards_belong_to_the_selected_sop(self):
        html = self.client.get(self.url(tab="sops", sop=self.module.sops.first().pk)).content.decode()
        for needle in ("VRPL-MANF-SOP-04", "Revision", "20-08-2025", "English + हिंदी", "Pre-start checks", "Hazards", "Safe operating practices", "Protective clothing",
                       "No production target is more important than safety"):
            self.assertIn(needle, html)
        second = self.module.sops.all()[1]
        other = self.client.get(self.url(tab="sops", sop=second.pk)).content.decode()
        self.assertNotIn("Barrel &amp; Die", other)               # SOP 1's hazards do not leak into SOP 2

    def test_each_sop_needs_its_own_safety_agreement(self):
        s1, s2 = self.module.sops.all()[:2]
        self.client.post(reverse("learning:ack_safety", args=[self.module.slug]), {"sop": s1.pk})
        self.assertTrue(SOPAcknowledgement.objects.filter(user=self.learner, sop=s1).exists())
        self.assertNotIn("sop-progress", self.client.get(self.url(tab="sops", sop=s2.pk)).content.decode())   # still locked
        self.assertIn("sop-progress", self.client.get(self.url(tab="sops", sop=s1.pk)).content.decode())

    def test_marking_steps_in_a_sop_counts_only_that_sop(self):
        s1, s2 = self.module.sops.all()[:2]
        self.client.post(reverse("learning:ack_safety", args=[self.module.slug]), {"sop": s2.pk})
        self.client.post(reverse("learning:toggle_step", args=[self.module.slug, 1]), {"sop": s2.pk})
        html = self.client.get(self.url(tab="sops", sop=s1.pk)).content.decode()
        self.assertIn("0/37", html); self.assertIn("1/22", html)
        locked = self.client.post(reverse("learning:toggle_step", args=[self.module.slug, 1]), {"sop": s1.pk})   # SOP 1 not agreed yet
        self.assertEqual(self.module.steps.filter(sop=s1).count(), 37)
        r = self.client.get(self.url(tab="sops", sop=s1.pk))
        self.assertIn("0/37", r.content.decode())

    def test_step_numbers_restart_in_every_sop(self):
        for sop in self.module.sops.all():
            self.assertEqual(sop.steps.order_by("number").first().number, 1)

    def test_plain_modules_without_sops_still_work(self):
        melt = Module.objects.get(slug="vmpl_melt_cast")
        self.assertFalse(melt.sops.exists())
        self.client.post(reverse("learning:ack_safety", args=[melt.slug]))
        html = self.client.get(reverse("learning:module_detail", args=[melt.slug]) + "?tab=sops").content.decode()
        self.assertIn("sop-progress", html)
        self.assertNotIn("sop-pick-card", html)

    def test_process_sections_are_optional(self):
        melt = Module.objects.get(slug="vmpl_melt_cast")
        html = self.client.get(reverse("learning:module_detail", args=[melt.slug])).content.decode()
        for absent in ("Who does what", "Who to call", "esc-card", "roles-table"):
            self.assertNotIn(absent, html)

    def test_content_in_gujarati_when_translated(self):
        role = self.module.roles.first()
        role.activity_gu = "જોબ માટે પરિમાણો સેટ કરો"; role.save()
        self.client.cookies["django_language"] = "gu"
        self.assertIn("જોબ માટે પરિમાણો સેટ કરો", self.client.get(self.url(tab="overview")).content.decode())

    # ------------------------------------------------------------------ admin panel
    def test_admin_tabs_exist_and_load(self):
        self.client.force_login(self.admin)
        for tab in ("process", "sops", "steps", "safety", "details"):
            r = self.client.get(reverse("panel:module_tab", args=[self.module.pk, tab]))
            self.assertEqual(r.status_code, 200, tab)
        self.assertContains(self.client.get(reverse("panel:module_tab", args=[self.module.pk, "process"])), "Who does what")
        self.assertContains(self.client.get(reverse("panel:module_tab", args=[self.module.pk, "steps"])), "Steps for:")

    def test_admin_edits_steps_of_the_chosen_sop(self):
        self.client.force_login(self.admin)
        sop = self.module.sops.all()[1]
        r = self.client.get(reverse("panel:module_tab", args=[self.module.pk, "steps"]) + f"?sop={sop.pk}")
        self.assertContains(r, "Mixing Batch Transfer")

    def test_importing_steps_into_a_sop_with_excel_sop_column(self):
        from apps.learning.importers import import_steps_bulk
        n, groups = import_steps_bulk([{"module": self.module.slug, "sop": "Mixing Batch Transfer to Extrusion Line", "text": "New first step", "_row": 2},
                                       {"module": self.module.slug, "sop": "Brand New SOP", "text": "Only step", "_row": 3}], replace=True)
        self.assertEqual((n, groups), (2, 2))
        self.assertEqual(self.module.sops.get(title="Mixing Batch Transfer to Extrusion Line").steps.count(), 1)
        self.assertTrue(ModuleSOP.objects.filter(module=self.module, title="Brand New SOP").exists())
        self.assertEqual(self.module.sops.first().steps.count(), 37)       # untouched

    def test_prestart_group_has_its_own_colour(self):
        self.assertIn("prestart", dict(SafetyGuideline.Section.choices))
