import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learning.models import Module, SOPStep
from apps.quizzes.models import Question


def xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO(); wb.save(b)
    return SimpleUploadedFile("data.xlsx", b.getvalue())


class ImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.boss = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.boss)

    def up(self, kind, f, **extra):
        return self.client.post(reverse("panel:import"), {"kind": kind, "file": f, **extra}, follow=True)

    def test_page_and_samples_download(self):
        self.assertContains(self.client.get(reverse("panel:import")), "Download sample (Excel)")
        for kind in ("plants", "modules", "steps", "quiz"):
            for ext in ("xlsx", "csv"):
                r = self.client.get(reverse("panel:import_sample", args=[kind, ext]))
                self.assertEqual(r.status_code, 200)
        self.assertTrue(self.client.get(reverse("panel:import_sample", args=["steps", "xlsx"])).content.startswith(b"PK"))

    def test_sample_files_import_cleanly_round_trip(self):
        plant = Module.objects.first().plant
        for ext in ("xlsx", "csv"):
            f = self.client.get(reverse("panel:import_sample", args=["modules", ext])).content
            r = self.up("modules", SimpleUploadedFile(f"m.{ext}", f), plant=plant.pk)
            self.assertContains(r, "Done")
        self.assertTrue(Module.objects.filter(title="Homogenizing", status="draft").exists())
        for kind in ("steps", "quiz"):
            f = self.client.get(reverse("panel:import_sample", args=[kind, "xlsx"])).content
            self.assertContains(self.up(kind, SimpleUploadedFile("s.xlsx", f)), "Done")

    def test_modules_created_and_updated(self):
        plant = Module.objects.first().plant
        r = self.up("modules", xlsx([["title", "department", "est_minutes", "objectives", "status"],
                                      ["Brand New Module", "Production", 40, "One|Two", "published"]]), plant=plant.pk)
        self.assertContains(r, "1 module(s) added")
        m = Module.objects.get(title="Brand New Module")
        self.assertEqual((m.est_minutes, m.status, m.objectives), (40, "published", "One\nTwo"))
        r = self.up("modules", xlsx([["title", "department", "est_minutes"], ["brand new module", "Production", 55]]), plant=plant.pk)
        self.assertContains(r, "0 module(s) added, 1 updated")
        m.refresh_from_db(); self.assertEqual(m.est_minutes, 55)

    def test_steps_for_two_modules_ordered_and_replace(self):
        a, b = "vmpl_melt_cast", "vmpl_extrusion"
        self.up("steps", xlsx([["module", "step", "text"], [a, 2, "Second"], [a, 1, "First"], [b, "", "Only step"]]), mode="replace")
        self.assertEqual(list(SOPStep.objects.filter(module__slug=a).values_list("text", flat=True)), ["First", "Second"])
        self.assertEqual(SOPStep.objects.filter(module__slug=b).count(), 1)
        self.up("steps", xlsx([["module", "text"], [a, "Third"]]))      # append
        self.assertEqual(SOPStep.objects.filter(module__slug=a).count(), 3)

    def test_bad_rows_import_nothing_and_name_the_row(self):
        before = SOPStep.objects.count()
        r = self.up("steps", xlsx([["module", "text"], ["vmpl_melt_cast", "ok"], ["no such module", "x"]]), mode="replace")
        self.assertContains(r, "Row 3"); self.assertContains(r, "no such module")
        self.assertEqual(SOPStep.objects.count(), before)

    def test_quiz_bulk_and_validation(self):
        good = [["module", "question", "option_a", "option_b", "correct"], ["vmpl_melt_cast", "Q1?", "yes", "no", "A"]]
        self.assertContains(self.up("quiz", xlsx(good), mode="replace"), "1 question(s) replaced")
        self.assertEqual(Question.objects.filter(quiz__module__slug="vmpl_melt_cast").count(), 1)
        bad = [good[0], ["vmpl_melt_cast", "Q2?", "yes", "no", "Z"]]
        self.assertContains(self.up("quiz", xlsx(bad)), "Row 2")

    def test_wrong_file_types(self):
        self.assertContains(self.up("steps", SimpleUploadedFile("a.xls", b"x")), "Save As")
        self.assertContains(self.up("steps", SimpleUploadedFile("a.pdf", b"x")), "Excel file")
        self.assertContains(self.up("steps", SimpleUploadedFile("a.xlsx", b"not a zip")), "real .xlsx")

    def test_semicolon_csv_from_european_excel(self):
        csvf = SimpleUploadedFile("a.csv", "module;text\nvmpl_melt_cast;Hello step\n".encode("utf-8-sig"))
        self.assertContains(self.up("steps", csvf, mode="replace"), "1 step(s) replaced")

    def test_learners_cannot_import(self):
        self.client.force_login(User.objects.get(employee_id="test_user"))
        self.assertNotEqual(self.client.get(reverse("panel:import")).status_code, 200)

    def test_per_module_import_accepts_excel(self):
        m = Module.objects.get(slug="vmpl_melt_cast")
        self.client.post(reverse("panel:module_import", args=[m.pk, "steps"]), {"csv": xlsx([["step", "text"], [1, "From Excel"]]), "mode": "replace"})
        self.assertEqual(list(m.steps.values_list("text", flat=True)), ["From Excel"])


    def test_plants_import_creates_plants_and_departments(self):
        from apps.plants.models import Department, Plant
        f = self.client.get(reverse("panel:import_sample", args=["plants", "xlsx"])).content
        r = self.up("plants", SimpleUploadedFile("p.xlsx", f))
        self.assertContains(r, "plant(s) added")
        p = Plant.objects.get(name="VRPL")
        self.assertEqual(set(p.departments.values_list("name", flat=True)) >= {"Production", "QC", "Maintenance"}, True)
        self.assertEqual(p.departments.get(name="QC").name_gu, "ક્યુસી")
        self.assertEqual(p.location_gu, "ગુજરાત")
        r = self.up("plants", xlsx([["name", "about"], ["vrpl", "Updated text"]]))
        self.assertContains(r, "0 plant(s) added, 1 updated")
        p.refresh_from_db(); self.assertEqual(p.about, "Updated text")

    def test_plant_code_conflict_is_reported(self):
        r = self.up("plants", xlsx([["name", "code"], ["Brand New Plant", "vrpl"]]))
        self.assertContains(r, "already used")

    def test_steps_sample_has_no_step_number_column_and_has_languages(self):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(self.client.get(reverse("panel:import_sample", args=["steps", "xlsx"])).content))
        head = [c.value for c in wb.worksheets[0][1]]
        self.assertEqual(head, ["module", "sop", "text", "text_hi", "text_gu"])
        self.assertIn("do NOT need a step number", " ".join(str(c.value) for row in wb["How to fill"].iter_rows() for c in row))
