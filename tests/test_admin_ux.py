import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learning.models import Module
from apps.panel.readiness import module_checks, setup_guide
from apps.quizzes.models import Question, Quiz


class QuizCategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.admin = User.objects.get(employee_id="test_admin")
        cls.learner = User.objects.get(employee_id="test_user")
        # a quiz in each of the three categories at VMPL P1
        for slug in ("vmpl_extrusion", "vmpl_incoming_inspection", "vmpl_preventive_maintenance"):
            m = Module.objects.get(slug=slug)
            q = Quiz.objects.create(module=m)
            Question.objects.create(quiz=q, text="Q?")

    def test_learner_sees_quizzes_grouped_by_category(self):
        self.client.force_login(self.learner)
        html = self.client.get(reverse("quizzes:list")).content.decode()
        for name in ("Production", "QC", "Maintenance"):
            self.assertIn(f"<h2>{name}</h2>", html)
        self.assertIn("qcat", html)

    def test_learner_can_filter_one_category(self):
        self.client.force_login(self.learner)
        dept = Module.objects.get(slug="vmpl_preventive_maintenance").department
        html = self.client.get(reverse("quizzes:list") + f"?dept={dept.pk}").content.decode()
        self.assertIn("Preventive Maintenance", html)
        self.assertNotIn("<h3>Extrusion</h3>", html)

    def test_admin_quiz_list_filters_by_category(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("panel:quizzes") + "?cat=Maintenance").content.decode()
        self.assertIn("Preventive Maintenance", html)
        self.assertNotIn(">Extrusion<", html)
        self.assertIn("Create a quiz", html)

    def test_create_quiz_step_by_step(self):
        self.client.force_login(self.admin)
        m = Module.objects.get(slug="vmpl_homogenizing")
        page = self.client.get(reverse("panel:quiz_new"))
        self.assertContains(page, "Where does the quiz belong?")
        r = self.client.post(reverse("panel:quiz_new"), {"plant": m.plant_id, "department": m.department_id, "module": m.pk, "pass_percent": 70, "max_attempts": 3})
        self.assertRedirects(r, reverse("panel:module_tab", args=[m.pk, "quiz"]), fetch_redirect_response=False)
        quiz = Quiz.objects.get(module=m)
        self.assertEqual((quiz.pass_percent, quiz.max_attempts), (70, 3))

    def test_create_quiz_rejects_mismatched_choices(self):
        self.client.force_login(self.admin)
        m = Module.objects.get(slug="vmpl_homogenizing")
        other_dept = Module.objects.get(slug="vmpl_preventive_maintenance").department
        r = self.client.post(reverse("panel:quiz_new"), {"plant": m.plant_id, "department": other_dept.pk, "module": m.pk, "pass_percent": 80})
        self.assertContains(r, "different department")
        self.assertFalse(Quiz.objects.filter(module=m).exists())


class AdminGuidanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.admin = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_checklist_says_what_is_missing(self):
        m = Module.objects.get(slug="vmpl_homogenizing")
        checks, percent, nxt = module_checks(m)
        done = {c["key"]: c["done"] for c in checks}
        self.assertTrue(done["steps"]); self.assertFalse(done["quiz"])
        self.assertEqual(nxt["key"], "basics" if not done["basics"] else ("safety" if not done["safety"] else "quiz"))
        self.assertLess(percent, 100)

    def test_module_page_shows_the_checklist(self):
        m = Module.objects.get(slug="vmpl_homogenizing")
        html = self.client.get(reverse("panel:module_tab", args=[m.pk, "details"])).content.decode()
        self.assertIn("Setup checklist", html)
        self.assertIn("Quiz with questions", html)

    def test_module_list_shows_setup_progress(self):
        html = self.client.get(reverse("panel:modules")).content.decode()
        self.assertIn("setup-cell", html)
        self.assertIn("Next:", html)

    def test_dashboard_has_getting_started_until_done(self):
        g = setup_guide()
        self.assertEqual(g["total"], 7)
        html = self.client.get(reverse("panel:dashboard")).content.decode()
        self.assertEqual("Getting started" in html, not g["finished"])


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        call_command("seed_hindi", stdout=io.StringIO())
        call_command("seed_gujarati", stdout=io.StringIO())
        cls.admin = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.admin)

    def sheet(self, kind, name=None):
        from openpyxl import load_workbook
        r = self.client.get(reverse("panel:export", args=[kind]))
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.assertIn("shiksha_" + ("everything" if kind == "all" else kind) + "_", r["Content-Disposition"])
        wb = load_workbook(io.BytesIO(r.content))
        return wb, wb[name] if name else wb.worksheets[0]

    def rows(self, ws):
        data = [[c.value for c in row] for row in ws.iter_rows()]
        return data[0], [dict(zip(data[0], r)) for r in data[1:]]

    def test_every_download_works(self):
        for kind in ("plants", "modules", "steps", "quiz", "users", "knowledge", "sops", "rules", "process", "all"):
            self.sheet(kind)

    def test_plants_file_has_all_languages(self):
        head, rows = self.rows(self.sheet("plants")[1])
        vmpl = next(r for r in rows if r["name"] == "VMPL P1")
        self.assertIn("Production", vmpl["departments"]); self.assertIn("Maintenance", vmpl["departments"])
        self.assertTrue(vmpl["about_hi"]); self.assertIn("વિશાખા", vmpl["about_gu"]); self.assertEqual(vmpl["location_gu"], "મુન્દ્રા, ગુજરાત")
        self.assertEqual(head[:4], ["name", "code", "company", "location"])

    def test_modules_file_and_round_trip_through_import(self):
        from apps.learning.importers import import_modules
        from apps.learning.tables import read_table
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.get(reverse("panel:export", args=["modules"]))
        rows = read_table(SimpleUploadedFile("m.xlsx", r.content))
        n = Module.objects.count()
        created, updated = import_modules(rows)
        self.assertEqual((created, updated), (0, n))                  # nothing duplicated, everything matched by slug
        melt = Module.objects.get(slug="vmpl_melt_cast")
        self.assertEqual(melt.objectives.count("\n"), 2)

    def test_steps_round_trip_keeps_sops_and_order(self):
        from apps.learning.importers import import_steps_bulk
        from apps.learning.models import SOPStep
        from apps.learning.tables import read_table
        from django.core.files.uploadedfile import SimpleUploadedFile
        before = list(SOPStep.objects.values_list("module__slug", "sop__title", "number", "text").order_by("module_id", "sop_id", "number"))
        r = self.client.get(reverse("panel:export", args=["steps"]))
        import_steps_bulk(read_table(SimpleUploadedFile("s.xlsx", r.content)), replace=True)
        after = list(SOPStep.objects.values_list("module__slug", "sop__title", "number", "text").order_by("module_id", "sop_id", "number"))
        self.assertEqual(sorted(before, key=str), sorted(after, key=str))

    def test_quiz_file_has_correct_letter_and_gujarati(self):
        head, rows = self.rows(self.sheet("quiz")[1])
        q = rows[0]
        self.assertIn(q["correct"], "ABCD"); self.assertTrue(q["question_gu"]); self.assertIn("option_a_gu", head)

    def test_users_file_has_no_passwords(self):
        wb, ws = self.sheet("users")
        text = " ".join(str(c.value) for row in ws.iter_rows() for c in row)
        self.assertNotIn("pbkdf2", text); self.assertNotIn("password", " ".join(h.lower() for h in [c.value for c in ws[1]]))

    def test_everything_workbook_has_all_sheets(self):
        wb, _ = self.sheet("all")
        for name in ("Plants", "Modules", "SOP steps", "Quiz questions", "Users", "Knowledge base", "Safety rules", "About this file"):
            self.assertIn(name, wb.sheetnames)

    def test_formula_like_text_stays_text(self):
        from apps.plants.models import Plant
        Plant.objects.filter(code="vmpl-p1").update(tagline='=HYPERLINK("http://x")')
        wb, ws = self.sheet("plants")
        cell = next(c for row in ws.iter_rows(min_row=2) for c in row if c.value and str(c.value).startswith("=HYPERLINK"))
        self.assertEqual(cell.data_type, "s")

    def test_learners_cannot_download(self):
        self.client.force_login(User.objects.get(employee_id="test_user"))
        self.assertNotEqual(self.client.get(reverse("panel:export", args=["users"])).status_code, 200)

    def test_unknown_kind_is_404_and_page_lists_downloads(self):
        self.assertEqual(self.client.get(reverse("panel:export", args=["nope"])).status_code, 404)
        self.assertContains(self.client.get(reverse("panel:import")), "Download everything")
