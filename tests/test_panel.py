import shutil
import tempfile
from io import BytesIO

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.learning.models import Module, ModuleImage, ProblemSolution, SafetyGuideline, SOPStep, VideoLesson
from apps.plants.models import Department, Plant, PlantPhoto, Process
from apps.quizzes.models import Choice, Question, Quiz
from apps.sops.models import SOPDocument, SOPVersion

TMP = tempfile.mkdtemp(prefix="shiksha-panel-")


def img(size=(800, 600), color=(200, 30, 50), name="p.png", fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def editor_data(key, rows):
    """rows: list of dicts with 'uid' (+ optional 'id') and field values -> POST payload for an Editor."""
    data = {f"{key}-order": ",".join(r["uid"] for r in rows)}
    for r in rows:
        uid = r["uid"]
        data[f"{key}-{uid}-id"] = r.get("id", "")
        for k, v in r.items():
            if k not in ("uid", "id"):
                data[f"{key}-{uid}-{k}"] = v
    return data


@override_settings(MEDIA_ROOT=TMP)
class PanelBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        cls.admin = User.objects.get(employee_id="test_admin")
        cls.learner = User.objects.get(employee_id="test_user")
        cls.plant = Plant.objects.get(code="vmpl-p1")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.admin)


class AccessTests(PanelBase):
    def test_learner_and_anonymous_blocked(self):
        self.client.force_login(self.learner)
        for name in ("panel:dashboard", "panel:modules", "panel:users", "panel:reports"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("panel:dashboard")).status_code, 302)

    def test_learner_cannot_post_to_panel(self):
        self.client.force_login(self.learner)
        r = self.client.post(reverse("panel:module_status", args=[self.melt.pk]))
        self.assertEqual(r.status_code, 403)
        self.melt.refresh_from_db()
        self.assertEqual(self.melt.status, "published")

    def test_admin_in_learner_preview_is_redirected_out(self):
        self.client.post(reverse("core:view_mode"), {"mode": "learner"})
        self.assertRedirects(self.client.get(reverse("panel:dashboard")), reverse("core:dashboard"), fetch_redirect_response=False)
        self.assertNotContains(self.client.get(reverse("core:dashboard")), reverse("panel:dashboard"))

    def test_every_page_loads(self):
        q = self.melt.quiz.questions.first()
        paths = [reverse(n) for n in ["panel:dashboard", "panel:help", "panel:plants", "panel:plant_new", "panel:modules", "panel:module_new", "panel:quizzes", "panel:sops",
                                      "panel:sop_new", "panel:users", "panel:user_new", "panel:user_import", "panel:discussion", "panel:incidents", "panel:certificates", "panel:reports"]]
        paths += [reverse("panel:plant_tab", args=[self.plant.pk, t]) for t in ("details", "gallery", "structure")]
        paths += [reverse("panel:module_tab", args=[self.melt.pk, t]) for t in ("details", "images", "steps", "safety", "videos", "problems", "quiz")]
        paths += [reverse("panel:question_new", args=[self.melt.pk]), reverse("panel:question_edit", args=[self.melt.pk, q.pk]), reverse("panel:module_delete", args=[self.melt.pk]),
                  reverse("panel:report_export", args=["modules"]), reverse("panel:report_export", args=["learners"])]
        for p in paths:
            self.assertEqual(self.client.get(p).status_code, 200, p)

    def test_dashboard_flags_content_problems(self):
        Module.objects.create(slug="empty_one", plant=self.plant, department=self.melt.department, title="Empty one")
        html = self.client.get(reverse("panel:dashboard")).content.decode()
        self.assertIn("no SOP steps", html)


class PlantTests(PanelBase):
    def test_create_plant_autocode_and_banner_optimised(self):
        r = self.client.post(reverse("panel:plant_new"), {"name": "VGPL 3", "company": "X", "order": 9, "is_active": "on", "banner": img((3000, 1200))})
        p = Plant.objects.get(name="VGPL 3")
        self.assertEqual(p.code, "vgpl-3")
        self.assertRedirects(r, reverse("panel:plant_tab", args=[p.pk, "details"]), fetch_redirect_response=False)
        with Image.open(p.banner.path) as im:
            self.assertLessEqual(max(im.size), 1600)
            self.assertEqual(im.format, "JPEG")

    def test_plant_code_unique_and_locked_after_create(self):
        self.client.post(reverse("panel:plant_new"), {"name": "VMPL P1", "order": 1, "is_active": "on"})
        self.assertEqual(Plant.objects.filter(name="VMPL P1").count(), 2)
        self.assertEqual(len({p.code for p in Plant.objects.filter(name="VMPL P1")}), 2)
        r = self.client.post(reverse("panel:plant_edit", args=[self.plant.pk]), {"name": "VMPL P1", "code": "hacked", "order": 2, "is_active": "on"})
        self.plant.refresh_from_db()
        self.assertEqual(self.plant.code, "vmpl-p1")

    def test_bad_banner_rejected(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        r = self.client.post(reverse("panel:plant_edit", args=[self.plant.pk]), {"name": "VMPL P1", "order": 1, "is_active": "on", "banner": bad})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Plant.objects.get(pk=self.plant.pk).banner)

    def test_gallery_add_reorder_caption_hindi_and_delete(self):
        url = reverse("panel:plant_tab", args=[self.plant.pk, "gallery"])
        r = self.client.post(url, {**editor_data("photos", [{"uid": "a", "caption": "Furnace", "caption_hi": "फ़र्नेस"}, {"uid": "b", "caption": "Press"}]),
                                   "photos-a-image": img(), "photos-b-image": img(color=(0, 0, 200), name="b.png")})
        self.assertRedirects(r, url, fetch_redirect_response=False)
        photos = list(PlantPhoto.objects.filter(plant=self.plant))
        self.assertEqual([p.caption for p in photos], ["Furnace", "Press"])
        a, b = photos
        # swap order, drop none; keep ids
        self.client.post(url, editor_data("photos", [{"uid": f"r{b.pk}", "id": str(b.pk), "caption": "Press"}, {"uid": f"r{a.pk}", "id": str(a.pk), "caption": "Furnace", "caption_hi": "फ़र्नेस"}]))
        self.assertEqual([p.caption for p in PlantPhoto.objects.filter(plant=self.plant)], ["Press", "Furnace"])
        import os
        path = a.image.path
        self.assertTrue(os.path.exists(path))
        # remove Furnace
        self.client.post(url, editor_data("photos", [{"uid": f"r{b.pk}", "id": str(b.pk), "caption": "Press"}]))
        self.assertEqual(PlantPhoto.objects.filter(plant=self.plant).count(), 1)
        self.assertFalse(os.path.exists(path))  # file cleaned up too

    def test_plant_page_and_learner_view_show_gallery_with_hindi_caption(self):
        PlantPhoto.objects.create(plant=self.plant, image=img(name="g.png"), caption="Furnace", caption_hi="फ़र्नेस")
        self.client.force_login(self.learner)
        self.assertContains(self.client.get(reverse("core:plant_overview")), 'data-lightbox="plant"')
        self.client.cookies["django_language"] = "hi"
        self.assertContains(self.client.get(reverse("core:plant_overview")), "फ़र्नेस")

    def test_departments_and_processes(self):
        url = reverse("panel:plant_tab", args=[self.plant.pk, "structure"])
        existing = [{"uid": f"r{d.pk}", "id": str(d.pk), "name": d.name, "name_hi": d.name_hi} for d in self.plant.departments.order_by("order", "id")]
        self.client.post(url, {**editor_data("depts", existing + [{"uid": "n1", "name": "Maintenance", "name_hi": "मेंटेनेंस"}])})
        dept = Department.objects.get(plant=self.plant, name="Maintenance")
        procs = [{"uid": f"r{p.pk}", "id": str(p.pk), "department": str(p.department_id), "name": p.name} for p in Process.objects.filter(department__plant=self.plant)]
        self.client.post(url, {**editor_data("depts", existing + [{"uid": f"r{dept.pk}", "id": str(dept.pk), "name": "Maintenance", "name_hi": "मेंटेनेंस"}]),
                               **editor_data("procs", procs + [{"uid": "n2", "department": str(dept.pk), "name": "Preventive maintenance"}])})
        self.assertTrue(Process.objects.filter(department=dept, name="Preventive maintenance").exists())

    def test_plant_with_incidents_cannot_be_deleted(self):
        from apps.incidents.models import Incident
        Incident.objects.create(plant=self.plant, title="x", description="y", reported_by=self.learner)
        self.client.post(reverse("panel:plant_delete", args=[self.plant.pk]))
        self.assertTrue(Plant.objects.filter(pk=self.plant.pk).exists())


class ModuleTests(PanelBase):
    def test_create_module_autoslug_then_lands_on_steps(self):
        dept = self.melt.department
        r = self.client.post(reverse("panel:module_new"), {"title": "Cooling Tower", "plant": self.plant.pk, "department": dept.pk, "library": "production", "est_minutes": 15,
                                                         "status": "draft", "order": 50, "cover": img()})
        m = Module.objects.get(title="Cooling Tower")
        self.assertEqual(m.slug, "cooling_tower")
        self.assertRedirects(r, reverse("panel:module_tab", args=[m.pk, "steps"]), fetch_redirect_response=False)
        self.assertTrue(m.cover)

    def test_department_must_belong_to_plant(self):
        other = Plant.objects.exclude(pk=self.plant.pk).first()
        d2 = Department.objects.create(plant=other, name="Other dept")
        r = self.client.post(reverse("panel:module_new"), {"title": "Bad", "plant": self.plant.pk, "department": d2.pk, "library": "production", "est_minutes": 5, "status": "draft", "order": 1})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Module.objects.filter(title="Bad").exists())
        self.assertContains(r, "different plant")

    def test_steps_editor_add_reorder_delete_renumber(self):
        m = Module.objects.create(slug="steps_demo", plant=self.plant, department=self.melt.department, title="Steps demo")
        url = reverse("panel:module_tab", args=[m.pk, "steps"])
        self.client.post(url, editor_data("steps", [{"uid": "a", "text": "First"}, {"uid": "b", "text": "Second", "text_hi": "दूसरा"}, {"uid": "c", "text": "Third"}]))
        self.assertEqual([(s.number, s.text) for s in m.steps.all()], [(1, "First"), (2, "Second"), (3, "Third")])
        s1, s2, s3 = list(m.steps.all())
        # move Third to the top, delete First -> numbers must be 1..2 with no clash
        self.client.post(url, editor_data("steps", [{"uid": f"r{s3.pk}", "id": str(s3.pk), "text": "Third"}, {"uid": f"r{s2.pk}", "id": str(s2.pk), "text": "Second", "text_hi": "दूसरा"}]))
        self.assertEqual([(s.number, s.text) for s in m.steps.all()], [(1, "Third"), (2, "Second")])
        self.assertEqual(m.steps.get(number=2).text_hi, "दूसरा")
        self.assertFalse(SOPStep.objects.filter(pk=s1.pk).exists())

    def test_blank_rows_ignored_and_invalid_row_blocks_everything(self):
        m = Module.objects.create(slug="v_demo", plant=self.plant, department=self.melt.department, title="V demo")
        url = reverse("panel:module_tab", args=[m.pk, "steps"])
        self.client.post(url, editor_data("steps", [{"uid": "a", "text": "Real"}, {"uid": "b", "text": ""}]))
        self.assertEqual(m.steps.count(), 1)
        r = self.client.post(url, {**editor_data("steps", [{"uid": "a", "text": "Another"}, {"uid": "z", "text": ""}]), "steps-z-image": img()})
        self.assertEqual(r.status_code, 200)               # re-rendered with errors
        self.assertContains(r, "Required.")
        self.assertEqual(m.steps.count(), 1)               # nothing half-saved

    def test_steps_paste_import_csv_and_numbered_lines(self):
        m = Module.objects.create(slug="imp_demo", plant=self.plant, department=self.melt.department, title="Imp demo")
        self.client.post(reverse("panel:module_import", args=[m.pk, "steps"]), {"paste": "1. Open valve\n2) Check gauge\n\nWear gloves"})
        self.assertEqual([s.text for s in m.steps.all()], ["Open valve", "Check gauge", "Wear gloves"])
        self.client.post(reverse("panel:module_import", args=[m.pk, "steps"]), {"paste": "Close valve"})
        self.assertEqual(m.steps.count(), 4)
        csv_file = SimpleUploadedFile("s.csv", "step,text,text_hi\n1,Alpha,अल्फ़ा\n2,Beta,\n".encode("utf-8-sig"), content_type="text/csv")
        self.client.post(reverse("panel:module_import", args=[m.pk, "steps"]), {"csv": csv_file, "mode": "replace"})
        self.assertEqual([(s.number, s.text, s.text_hi) for s in m.steps.all()], [(1, "Alpha", "अल्फ़ा"), (2, "Beta", "")])
        r = self.client.post(reverse("panel:module_import", args=[m.pk, "steps"]), {}, follow=True)
        self.assertContains(r, "Paste some steps")

    def test_gallery_safety_videos_problems_editors(self):
        m = Module.objects.create(slug="tabs_demo", plant=self.plant, department=self.melt.department, title="Tabs demo")
        self.client.post(reverse("panel:module_tab", args=[m.pk, "images"]), {**editor_data("gallery", [{"uid": "a", "caption": "Die", "caption_hi": "डाई"}]), "gallery-a-image": img()})
        self.assertEqual(ModuleImage.objects.get(module=m).caption_hi, "डाई")
        self.client.post(reverse("panel:module_tab", args=[m.pk, "safety"]), {**editor_data("safe_mod", [{"uid": "a", "section": "safety", "text": "Wear PPE"}]),
                                                                              **editor_data("safe_plant", [{"uid": "p", "section": "environment", "text": "Segregate waste"}])})
        self.assertEqual(SafetyGuideline.objects.filter(module=m).count(), 1)
        self.assertTrue(SafetyGuideline.objects.filter(plant=self.plant, module__isnull=True, text="Segregate waste").exists())
        self.client.post(reverse("panel:module_tab", args=[m.pk, "videos"]), editor_data("videos", [{"uid": "a", "title": "Intro", "url": "https://example.com/v.mp4", "duration_minutes": "5"}]))
        self.assertEqual(VideoLesson.objects.get(module=m).duration_minutes, 5)
        self.client.post(reverse("panel:module_tab", args=[m.pk, "problems"]), editor_data("problems", [{"uid": "a", "problem": "Scratches", "solution": "Clean die", "solution_hi": "डाई साफ़ करें"}]))
        self.assertEqual(ProblemSolution.objects.get(module=m).solution_hi, "डाई साफ़ करें")

    def test_module_gallery_visible_to_learners_in_overview(self):
        ModuleImage.objects.create(module=self.melt, image=img(name="m.png"), caption="Furnace", caption_hi="फ़र्नेस")
        self.client.force_login(self.learner)
        html = self.client.get(reverse("learning:module_detail", args=[self.melt.slug])).content.decode()
        self.assertIn("data-gallery", html)
        self.assertIn('data-lightbox="module"', html)
        self.client.cookies["django_language"] = "hi"
        self.assertIn("फ़र्नेस", self.client.get(reverse("learning:module_detail", args=[self.melt.slug])).content.decode())

    def test_publish_toggle_bulk_and_draft_hidden_from_learners(self):
        self.client.post(reverse("panel:module_status", args=[self.melt.pk]))
        self.melt.refresh_from_db()
        self.assertEqual(self.melt.status, "draft")
        self.assertEqual(self.client.get(reverse("learning:module_detail", args=[self.melt.slug])).status_code, 200)   # admin can preview
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get(reverse("learning:module_detail", args=[self.melt.slug])).status_code, 404)
        self.client.force_login(self.admin)
        self.client.post(reverse("panel:module_bulk"), {"ids": [self.melt.pk], "action": "publish"})
        self.melt.refresh_from_db()
        self.assertEqual(self.melt.status, "published")

    def test_module_list_filters_and_search(self):
        Module.objects.create(slug="zzz", plant=self.plant, department=self.melt.department, title="Zzz unique title", status="draft")
        r = self.client.get(reverse("panel:modules") + "?q=unique&status=draft")
        self.assertEqual([m.title for m in r.context["page"]], ["Zzz unique title"])
        self.assertTrue(self.client.get(reverse("panel:modules") + "?issue=nosteps").context["total"] >= 1)

    def test_delete_module_needs_post_and_cleans_up(self):
        m = Module.objects.create(slug="to_go", plant=self.plant, department=self.melt.department, title="To go")
        self.assertContains(self.client.get(reverse("panel:module_delete", args=[m.pk])), "permanently deletes")
        self.assertTrue(Module.objects.filter(pk=m.pk).exists())
        self.client.post(reverse("panel:module_delete", args=[m.pk]))
        self.assertFalse(Module.objects.filter(pk=m.pk).exists())


class QuizPanelTests(PanelBase):
    def _choices(self, texts, correct):
        return editor_data("choices", [{"uid": f"c{i}", "text": t, "is_correct": ""} for i, t in enumerate(texts)]) | {"choices-is_correct": f"c{correct}"}

    def test_create_question_with_choices_and_validation(self):
        m = Module.objects.create(slug="q_demo", plant=self.plant, department=self.melt.department, title="Q demo")
        new_url = reverse("panel:question_new", args=[m.pk])
        # no correct answer -> rejected
        data = editor_data("choices", [{"uid": "a", "text": "One"}, {"uid": "b", "text": "Two"}])
        r = self.client.post(new_url, {"text": "Pick one", "kind": "Safety", **data})
        self.assertContains(r, "exactly one")
        self.assertFalse(Question.objects.filter(text="Pick one").exists())
        # one option only -> rejected
        r = self.client.post(new_url, {"text": "Pick one", "kind": "Safety", **editor_data("choices", [{"uid": "a", "text": "Only"}]), "choices-is_correct": "a"})
        self.assertContains(r, "at least two")
        # valid
        r = self.client.post(new_url, {"text": "Pick one", "kind": "Safety", "text_hi": "एक चुनें", **self._choices(["One", "Two", "Three"], 1)})
        self.assertRedirects(r, reverse("panel:module_tab", args=[m.pk, "quiz"]), fetch_redirect_response=False)
        q = Question.objects.get(text="Pick one")
        self.assertEqual([(c.text, c.is_correct) for c in q.choices.all()], [("One", False), ("Two", True), ("Three", False)])
        self.assertEqual(q.text_hi, "एक चुनें")

    def test_edit_question_changes_correct_and_removes_option(self):
        q = self.melt.quiz.questions.first()
        cs = list(q.choices.all())
        rows = [{"uid": f"r{c.pk}", "id": str(c.pk), "text": c.text} for c in cs[:3]]
        self.client.post(reverse("panel:question_edit", args=[self.melt.pk, q.pk]), {"text": q.text, "kind": q.kind, **editor_data("choices", rows), "choices-is_correct": f"r{cs[0].pk}"})
        q.refresh_from_db()
        self.assertEqual(q.choices.count(), 3)
        self.assertEqual([c.pk for c in q.choices.filter(is_correct=True)], [cs[0].pk])

    def test_quiz_settings_reorder_delete_and_import(self):
        quiz = self.melt.quiz
        r = self.client.post(reverse("panel:module_tab", args=[self.melt.pk, "quiz"]), {"pass_percent": "70", "questions_per_attempt": "1", "shuffle_questions": "on", "is_active": "on", "requires_all_steps": "on"})
        quiz.refresh_from_db()
        self.assertEqual((quiz.pass_percent, quiz.questions_per_attempt, quiz.shuffle_choices), (70, 1, False))
        qs = list(quiz.questions.all())
        self.client.post(reverse("panel:question_action", args=[self.melt.pk, qs[1].pk, "up"]))
        self.assertEqual(list(quiz.questions.values_list("pk", flat=True)), [qs[1].pk, qs[0].pk])
        csv_file = SimpleUploadedFile("q.csv", "question,option_a,option_b,option_c,option_d,correct\nQ new?,A1,B1,C1,D1,C\n".encode(), content_type="text/csv")
        self.client.post(reverse("panel:module_import", args=[self.melt.pk, "quiz"]), {"csv": csv_file})
        self.assertEqual(quiz.questions.count(), 3)
        self.client.post(reverse("panel:question_action", args=[self.melt.pk, qs[0].pk, "delete"]))
        self.assertEqual(quiz.questions.count(), 2)
        bad = SimpleUploadedFile("q.csv", "question,option_a,option_b,correct\nQ?,A,B,Z\n".encode(), content_type="text/csv")
        r = self.client.post(reverse("panel:module_import", args=[self.melt.pk, "quiz"]), {"csv": bad}, follow=True)
        self.assertContains(r, "must be one of")

    def test_create_quiz_button(self):
        m = Module.objects.create(slug="nq", plant=self.plant, department=self.melt.department, title="No quiz")
        self.client.post(reverse("panel:module_tab", args=[m.pk, "quiz"]), {"pass_percent": "80", "shuffle_questions": "on", "shuffle_choices": "on", "requires_all_steps": "on", "is_active": "on"})
        self.assertEqual(Quiz.objects.get(module=m).pass_percent, 80)


class SopPanelTests(PanelBase):
    def test_create_sop_versions_approval_supersedes(self):
        dept = self.melt.department
        r = self.client.post(reverse("panel:sop_new"), {"code": "VMPL/T/1", "title": "Test SOP", "plant": self.plant.pk, "department": dept.pk, "language": "en", "allow_download": "on"})
        sop = SOPDocument.objects.get(code="VMPL/T/1")
        self.assertRedirects(r, reverse("panel:sop_edit", args=[sop.pk]), fetch_redirect_response=False)
        url = reverse("panel:sop_edit", args=[sop.pk])
        pdf = SimpleUploadedFile("sop.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        self.client.post(url, {**editor_data("versions", [{"uid": "a", "version": "01", "effective_date": "2026-01-01", "status": "approved"}]), "versions-a-file": pdf})
        v1 = sop.versions.get(version="01")
        self.assertEqual(sop.active_version, v1)
        self.assertEqual(v1.uploaded_by, self.admin)
        self.client.post(url, editor_data("versions", [{"uid": f"r{v1.pk}", "id": str(v1.pk), "version": "01", "effective_date": "2026-01-01", "status": "approved"},
                                                       {"uid": "n", "version": "02", "effective_date": "2026-06-01", "status": "approved", "change_summary": "Updated temps"}]))
        v1.refresh_from_db()
        self.assertEqual(v1.status, "superseded")
        self.assertEqual(sop.active_version.version, "02")

    def test_duplicate_version_number_and_bad_file_rejected(self):
        sop = SOPDocument.objects.create(plant=self.plant, department=self.melt.department, code="D/1", title="Dup")
        url = reverse("panel:sop_edit", args=[sop.pk])
        r = self.client.post(url, editor_data("versions", [{"uid": "a", "version": "01", "effective_date": "2026-01-01", "status": "draft"}, {"uid": "b", "version": "01", "effective_date": "2026-02-01", "status": "draft"}]))
        self.assertContains(r, "same version number")
        exe = SimpleUploadedFile("evil.exe", b"MZ", content_type="application/octet-stream")
        r = self.client.post(url, {**editor_data("versions", [{"uid": "a", "version": "01", "effective_date": "2026-01-01", "status": "draft"}]), "versions-a-file": exe})
        self.assertContains(r, "not allowed")
        self.assertEqual(sop.versions.count(), 0)

    def test_sop_delete_and_list_filter(self):
        sop = SOPDocument.objects.create(plant=self.plant, department=self.melt.department, code="X/1", title="Unapproved")
        self.assertIn(sop, list(self.client.get(reverse("panel:sops") + "?issue=unapproved").context["page"]))
        self.client.post(reverse("panel:sop_delete", args=[sop.pk]))
        self.assertFalse(SOPDocument.objects.filter(pk=sop.pk).exists())


class UserPanelTests(PanelBase):
    def _post(self, **over):
        data = {"first_name": "Asha", "last_name": "Mehta", "email": "asha.mehta@vishakha.com", "employee_id": "", "designation": "Operator", "role": "learner", "is_active": "on"}
        data.update(over)
        return self.client.post(reverse("panel:user_new"), data)

    def test_create_user_emails_password_link(self):
        r = self._post()
        u = User.objects.get(email="asha.mehta@vishakha.com")
        self.assertRedirects(r, reverse("panel:user_edit", args=[u.pk]), fetch_redirect_response=False)
        self.assertFalse(u.has_usable_password())
        self.assertIsNone(u.employee_id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_admin_role_is_a_panel_admin_but_never_django_staff(self):
        self._post(email="boss@vishakha.com", role="admin", new_password="Str0ng-Pass-9917")
        u = User.objects.get(email="boss@vishakha.com")
        self.assertTrue(u.check_password("Str0ng-Pass-9917"))
        self.assertTrue(u.is_shiksha_admin)
        self.assertFalse(u.is_staff or u.is_superuser)   # no Advanced admin
        self.assertEqual(len(mail.outbox), 0)

    def test_company_domain_and_duplicates_enforced(self):
        self._post(email="x@gmail.com")
        self.assertFalse(User.objects.filter(email="x@gmail.com").exists())
        r = self._post(email="TEST_USER@vishakha.com")
        self.assertEqual(User.objects.filter(email__iexact="test_user@vishakha.com").count(), 1)
        self._post(email="a1@vishakha.com", employee_id="test_user")
        self.assertFalse(User.objects.filter(email="a1@vishakha.com").exists())

    def test_cannot_demote_or_deactivate_yourself_or_last_admin(self):
        url = reverse("panel:user_edit", args=[self.admin.pk])
        base = {"first_name": "Test", "last_name": "Admin", "email": self.admin.email, "employee_id": "test_admin", "designation": "", "role": "admin", "is_active": "on"}
        r = self.client.post(url, {**base, "role": "learner"})
        self.assertContains(r, "own admin access")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")
        r = self.client.post(url, {k: v for k, v in base.items() if k != "is_active"})
        self.assertContains(r, "deactivate yourself")
        # another admin may demote the last other admin only if a different admin remains
        other = User.objects.create_user("o@vishakha.com", "Pass-12345-xx", role="admin", is_staff=True)
        self.client.force_login(other)
        r = self.client.post(reverse("panel:user_edit", args=[self.admin.pk]), {**base, "role": "learner"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "learner")   # allowed: 'other' remains an admin

    def test_deactivated_user_cannot_sign_in(self):
        u = User.objects.get(employee_id="test_user2")
        self.client.post(reverse("panel:user_edit", args=[u.pk]), {"first_name": u.first_name, "last_name": u.last_name, "email": u.email, "employee_id": "test_user2", "role": "learner"})
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.client.logout()
        r = self.client.post(reverse("accounts:login"), {"username": "test_user2", "password": "Test@12345"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_plant_restriction_saved_and_enforced(self):
        u = User.objects.get(employee_id="test_user2")
        self.client.post(reverse("panel:user_edit", args=[u.pk]), {"first_name": "T", "last_name": "U", "email": u.email, "employee_id": "test_user2", "role": "learner", "is_active": "on", "plants": [self.plant.pk]})
        self.assertEqual(list(u.accessible_plants()), [self.plant])

    def test_send_reset_link_and_import_csv(self):
        u = User.objects.get(employee_id="test_user")
        self.client.post(reverse("panel:user_reset", args=[u.pk]))
        self.assertEqual(len(mail.outbox), 1)
        csv_file = SimpleUploadedFile("u.csv", ("email,first_name,last_name,employee_id,designation,role\n"
                                               "n1@vishakha.com,N,One,E1,Operator,learner\nbad@gmail.com,B,Ad,E2,,learner\ntest_user@vishakha.com,D,Up,E3,,learner\n"
                                               "n2@vishakha.com,N,Two,E1,,admin\n").encode("utf-8-sig"), content_type="text/csv")
        r = self.client.post(reverse("panel:user_import"), {"csv": csv_file}, follow=True)
        self.assertContains(r, "2 user(s) created")
        self.assertContains(r, "not a company address")
        self.assertContains(r, "already exists")
        self.assertEqual(User.objects.get(email="n2@vishakha.com").role, "admin")
        self.assertIsNone(User.objects.get(email="n2@vishakha.com").employee_id)   # duplicate employee id dropped, not crashed

    def test_user_list_filters(self):
        r = self.client.get(reverse("panel:users") + "?role=admin")
        self.assertTrue(all(u.role == "admin" for u in r.context["page"]))
        self.assertEqual(self.client.get(reverse("panel:users") + "?q=test_user2").context["total"], 1)


class OpsPanelTests(PanelBase):
    def test_incident_status_update_and_audit(self):
        from apps.incidents.models import Incident
        from apps.core.models import AuditLog
        inc = Incident.objects.create(plant=self.plant, title="Leak", description="x", reported_by=self.learner)
        self.client.post(reverse("panel:incident_status", args=[inc.pk]), {"status": "closed", "closure_notes": "Fixed"})
        inc.refresh_from_db()
        self.assertEqual((inc.status, inc.closure_notes), ("closed", "Fixed"))
        self.assertTrue(AuditLog.objects.filter(action="incident.status", object_id=str(inc.pk)).exists())
        self.assertContains(self.client.get(reverse("panel:incidents") + "?status=closed"), "Leak")

    def test_certificate_revoke(self):
        from apps.certificates.models import Certificate
        c = Certificate.objects.create(user=self.learner, module=self.melt, score_percent=90)
        self.assertContains(self.client.get(reverse("panel:certificates") + "?q=Test"), "Test User")
        self.client.post(reverse("panel:certificate_revoke", args=[c.pk]))
        self.assertFalse(Certificate.objects.filter(pk=c.pk).exists())

    def test_reports_numbers_and_csv(self):
        from apps.learning.models import ModuleProgress
        from django.utils import timezone
        ModuleProgress.objects.create(user=self.learner, module=self.melt, completed_at=timezone.now(), seconds_spent=3600)
        r = self.client.get(reverse("panel:reports"))
        row = next(x for x in r.context["modules"] if x["module"] == self.melt)
        self.assertEqual((row["started"], row["completed"], row["hours"]), (1, 1, 1.0))
        csv_text = self.client.get(reverse("panel:report_export", args=["modules"])).content.decode("utf-8-sig")
        self.assertIn("Melt & Cast", csv_text)
        self.assertTrue(self.client.get(reverse("panel:report_export", args=["learners"]))["Content-Disposition"].startswith("attachment"))
        self.assertEqual(self.client.get(reverse("panel:report_export", args=["nope"])).status_code, 404)

    def test_samples_download(self):
        for kind in ("steps", "quiz"):
            self.assertIn("text/csv", self.client.get(reverse("panel:sample_csv", args=[kind]))["Content-Type"])


class ResetForNoPasswordUsersTests(PanelBase):
    def test_forgot_password_works_for_users_without_a_password(self):
        u = User.objects.create_user("nopw@vishakha.com", None)
        self.assertFalse(u.has_usable_password())
        self.client.logout()
        self.client.post(reverse("accounts:password_reset"), {"email": "nopw@vishakha.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)


class NewModuleDefaultsTest(PanelBase):
    def test_new_module_form_defaults_to_draft(self):
        r = self.client.get(reverse("panel:module_new"))
        self.assertEqual(r.context["form"].initial.get("status"), "draft")
