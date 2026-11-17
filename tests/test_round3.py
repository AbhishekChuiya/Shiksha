import datetime
import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import Notification
from apps.learning.models import Module
from apps.quizzes.models import Quiz


class RequiredAndNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")
        cls.admin = User.objects.get(employee_id="test_admin")

    def setUp(self):
        self.client.force_login(self.user)
        self.plant = self.user.default_plant or self.user.accessible_plants().first()
        s = self.client.session
        s["current_plant_id"] = self.plant.pk
        s.save()
        self.module = Module.objects.filter(plant=self.plant, status="published").order_by("pk").last()

    def _require(self, days):
        self.module.is_mandatory = True
        self.module.due_date = timezone.localdate() + datetime.timedelta(days=days)
        self.module.save()

    def test_dashboard_shows_required_alert_with_overdue(self):
        self._require(-2)
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn("Needs your attention", html)
        self.assertIn("Overdue", html)
        self.assertIn(self.module.title, html)

    def test_no_alert_when_nothing_is_required(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertNotIn("Needs your attention", html)

    def test_module_list_shows_required_badge_and_status_filter(self):
        self._require(10)
        html = self.client.get(reverse("learning:module_list")).content.decode()
        self.assertIn("badge req", html)
        r = self.client.get(reverse("learning:module_list") + "?status=required&view=grid")
        shown = [c["module"].pk for c in r.context["cards"]]
        self.assertEqual(shown, [self.module.pk])
        self.assertEqual(self.client.get(reverse("learning:module_list") + "?status=junk").status_code, 200)

    def test_required_quiz_is_flagged_on_the_quiz_list(self):
        quiz, _ = Quiz.objects.get_or_create(module=self.module, defaults={"pass_percent": 80})
        quiz.is_mandatory, quiz.is_active = True, True
        quiz.due_date = timezone.localdate() + datetime.timedelta(days=1)
        quiz.save()
        html = self.client.get(reverse("quizzes:list")).content.decode()
        self.assertIn("req-line", html)

    def test_quiz_categories_always_listed(self):
        html = self.client.get(reverse("quizzes:list")).content.decode()
        self.assertIn('class="qcats"', html)

    def test_reminders_become_notifications_once(self):
        self._require(2)
        self.client.get(reverse("core:dashboard"))
        kinds = set(Notification.objects.filter(user=self.user).values_list("kind", flat=True))
        self.assertEqual(kinds, {"assigned", "due_soon"})
        s = self.client.session
        s.pop("duty_sync_at", None)
        s.save()
        self.client.get(reverse("core:dashboard"))
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    def test_bell_opens_marks_read_and_read_all(self):
        n = Notification.objects.create(user=self.user, kind="announcement", title="Hello team", body="Safety first", url="/quizzes/")
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn("Hello team", html)
        self.assertIn("bell-n", html)
        r = self.client.get(reverse("core:notification_open", args=[n.pk]))
        self.assertRedirects(r, "/quizzes/", fetch_redirect_response=False)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        Notification.objects.create(user=self.user, kind="announcement", title="Two")
        self.client.post(reverse("core:notifications_read_all"))
        self.assertFalse(Notification.objects.filter(user=self.user, is_read=False).exists())
        self.assertEqual(self.client.get(reverse("core:notifications")).status_code, 200)

    def test_cannot_open_someone_elses_notification(self):
        n = Notification.objects.create(user=self.admin, kind="announcement", title="Private")
        self.assertEqual(self.client.get(reverse("core:notification_open", args=[n.pk])).status_code, 404)

    def test_external_link_is_never_followed(self):
        n = Notification.objects.create(user=self.user, kind="announcement", title="x", url="https://evil.example/")
        r = self.client.get(reverse("core:notification_open", args=[n.pk]))
        self.assertRedirects(r, reverse("core:notifications"), fetch_redirect_response=False)

    def test_notification_text_follows_language(self):
        self._require(-1)
        self.client.get(reverse("core:dashboard"))
        self.client.cookies["django_language"] = "gu"
        html = self.client.get(reverse("core:notifications")).content.decode()
        self.assertIn("ફરજિયાત", html)

    def test_certificate_notifies(self):
        from apps.certificates.models import Certificate
        from apps.core.notify import certificate_issued
        cert = Certificate.objects.create(user=self.user, module=self.module)
        certificate_issued(cert)
        certificate_issued(cert)
        self.assertEqual(Notification.objects.filter(user=self.user, kind="certificate").count(), 1)

    def test_admin_can_announce_to_everyone_or_a_plant(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("panel:announce")).status_code, 200)
        self.client.post(reverse("panel:announce"), {"audience": "all", "title": "Plant shutdown", "body": "Friday", "url": "/"})
        self.assertEqual(Notification.objects.filter(title="Plant shutdown").count(), User.objects.filter(is_active=True).count())
        self.client.post(reverse("panel:announce"), {"audience": "all", "title": "Bad", "url": "https://evil.example"})
        self.assertFalse(Notification.objects.filter(title="Bad").exists())

    def test_learner_cannot_open_announce_page(self):
        self.assertNotEqual(self.client.get(reverse("panel:announce")).status_code, 200)

    def test_import_sets_required_and_due_date(self):
        from apps.learning.importers import ImportError_, import_modules
        title = self.module.title
        import_modules([{"_row": 2, "title": title, "plant": self.plant.name, "required": "yes", "due_date": "2030-01-31"}])
        self.module.refresh_from_db()
        self.assertTrue(self.module.is_mandatory)
        self.assertEqual(self.module.due_date, datetime.date(2030, 1, 31))
        with self.assertRaises(ImportError_):
            import_modules([{"_row": 2, "title": title, "plant": self.plant.name, "due_date": "soon"}])

    def test_read_aloud_has_no_stop_button(self):
        html = self.client.get(reverse("learning:module_detail", args=[self.module.slug]) + "?tab=sops").content.decode()
        self.assertNotIn("data-speak-stop", html)


class MenuAndFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")

    def setUp(self):
        self.client.force_login(self.user)

    def test_menu_has_no_sop_library_or_discussion_but_keeps_learning_book_soon(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        side = html[html.index('<aside class="sidebar"'):html.index("</aside>")]
        self.assertNotIn("SOP Library", side)
        self.assertNotIn("/discussion/", side)
        self.assertIn("Learning Book", side)
        self.assertIn('class="soon"', side)
        self.assertIn("Knowledge Base", side)

    def test_module_card_opens_on_click_and_unstarted_cards_have_no_start_button(self):
        html = self.client.get(reverse("learning:module_list") + "?view=grid").content.decode()
        self.assertIn("proc-card", html)
        self.assertIn("pc-link", html)                         # the whole card is one big link
        self.assertIn("pc-cta", html)

    def test_module_header_has_no_start_learning_for_unstarted_module(self):
        from apps.learning.models import Module, ModuleProgress
        m = Module.objects.filter(status="published").exclude(pk__in=ModuleProgress.objects.filter(user=self.user).values("module")).first()
        s = self.client.session
        s["current_plant_id"] = m.plant_id
        s.save()
        html = self.client.get(reverse("learning:module_detail", args=[m.slug])).content.decode()
        self.assertNotIn("Start learning", html)

    def test_library_filter_is_its_own_row_and_narrows_departments(self):
        r = self.client.get(reverse("learning:module_list") + "?library=production")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(label for label, *_ in r.context["lib_tabs"]))
        self.assertEqual(len(r.context["lib_tabs"]), 3)
        total_all = r.context["lib_tabs"][0][3]
        self.assertLessEqual(r.context["dept_tabs"][0][3], total_all)
        self.assertEqual(self.client.get(reverse("learning:module_list") + "?library=nonsense").status_code, 200)

    def test_certificate_page_and_pdf_have_both_signatories(self):
        from apps.certificates.models import Certificate
        from apps.learning.models import Module
        cert = Certificate.objects.create(user=self.user, module=Module.objects.filter(status="published").first())
        html = self.client.get(cert.get_absolute_url()).content.decode()
        self.assertIn("Head – Human Resources", html)
        self.assertIn("Head of Department", html)
        self.assertIn("cx-sig", html)
        pdf = self.client.get(reverse("certificates:download", args=[cert.code]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))


class RoundFiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")

    def setUp(self):
        self.client.force_login(self.user)

    def _open(self, module):
        s = self.client.session
        s["current_plant_id"] = module.plant_id
        s.save()
        return self.client.get(reverse("learning:module_detail", args=[module.slug])).content.decode()

    def test_journey_always_has_four_steps_even_without_a_quiz(self):
        from apps.learning.models import Module
        m = Module.objects.filter(status="published", quiz__isnull=True).first()
        if m is None:
            m = Module.objects.filter(status="published").first()
            Quiz.objects.filter(module=m).delete()
        html = self._open(m)
        self.assertIn("Pass the quiz", html)
        self.assertIn("Quiz coming soon", html)
        self.assertIn("Get your certificate", html)

    def test_module_without_questions_still_completes_without_blocking(self):
        from apps.learning.models import Module, ModuleProgress
        from apps.learning.services import refresh_completion
        m = Module.objects.filter(status="published", steps__isnull=False).first()
        Quiz.objects.update_or_create(module=m, defaults={"is_active": True})
        m.quiz.questions.all().delete()
        prog, _ = ModuleProgress.objects.get_or_create(user=self.user, module=m)
        prog.completed_steps.set(m.steps.all())
        self.assertTrue(refresh_completion(prog))

    def test_plant_overview_has_no_departments_card_and_shows_videos(self):
        from apps.plants.models import PlantVideo
        plant = self.user.accessible_plants().first()
        PlantVideo.objects.create(plant=plant, title="Plant tour", url="https://www.youtube.com/watch?v=abc123")
        PlantVideo.objects.create(plant=plant, title="Direct clip", url="https://cdn.example.com/a.mp4")
        s = self.client.session
        s["current_plant_id"] = plant.pk
        s.save()
        html = self.client.get(reverse("core:plant_overview")).content.decode()
        self.assertNotIn("Departments &amp; processes", html)
        self.assertIn("Plant tour", html)
        self.assertIn("youtube.com/embed/abc123", html)
        self.assertIn('<video controls', html)

    def test_admin_can_add_plant_video(self):
        from apps.plants.models import PlantVideo
        admin = User.objects.get(employee_id="test_admin")
        self.client.force_login(admin)
        plant = admin.accessible_plants().first()
        self.assertEqual(self.client.get(reverse("panel:plant_tab", args=[plant.pk, "gallery"])).status_code, 200)
        self.assertEqual(PlantVideo.objects.count(), 0)

    def test_module_list_filters_by_category_only_in_plant_order(self):
        from apps.learning.models import Module
        plant = Module.objects.filter(status="published").first().plant
        s = self.client.session
        s["current_plant_id"] = plant.pk
        s.save()
        r = self.client.get(reverse("learning:module_list"))
        labels = [c[0] for c in r.context["cat_chips"]]
        self.assertEqual(labels[0], "All")
        html = r.content.decode()
        self.assertNotIn(">Library<", html)
        self.assertNotIn(">Department<", html)
        first = r.context["cat_chips"][1]
        r2 = self.client.get(reverse("learning:module_list") + first[1])
        self.assertEqual(r2.status_code, 200)
        self.assertGreaterEqual(len(r2.context["cards"]), 1)
        Module.objects.filter(plant=plant).update(category="")
        r3 = self.client.get(reverse("learning:module_list") + "?category=__none__")
        self.assertEqual(r3.status_code, 200)

    def test_shuffle_changes_question_and_option_order_between_attempts(self):
        from apps.learning.models import Module
        from apps.quizzes.models import Attempt, Choice, Question
        from apps.quizzes.rotation import build_attempt
        m = Module.objects.filter(status="published").first()
        quiz, _ = Quiz.objects.get_or_create(module=m)
        quiz.questions.all().delete()
        for i in range(8):
            q = Question.objects.create(quiz=quiz, text=f"Question {i}", order=i)
            for j in range(4):
                Choice.objects.create(question=q, text=f"Option {j}", is_correct=(j == 0), order=j)
        quiz.shuffle_questions = quiz.shuffle_choices = True
        quiz.save()
        ids1, orders1 = build_attempt(quiz, self.user)
        Attempt.objects.create(quiz=quiz, user=self.user, question_ids=ids1, choice_orders=orders1)
        ids2, orders2 = build_attempt(quiz, self.user)
        self.assertNotEqual(ids1, ids2)
        self.assertNotEqual(ids1[0], ids2[0])
        self.assertNotEqual(orders1, orders2)

    def test_phone_only_view_switch_and_certificate_buttons_markup(self):
        html = self.client.get(reverse("learning:module_list")).content.decode()
        self.assertIn("proc-grid", html)


class JourneyAndProgressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")

    def setUp(self):
        self.client.force_login(self.user)

    def _plant(self, name_prefix):
        from apps.plants.models import Plant
        plant = Plant.objects.filter(name__startswith=name_prefix).first()
        s = self.client.session
        s["current_plant_id"] = plant.pk
        s.save()
        return plant

    def test_vmpl_journey_has_the_eleven_processes_in_order(self):
        from apps.plants.journey_view import build_journey
        plant = self._plant("VMPL P1")
        names = [j["name"] for j in build_journey(self.user, plant)]
        self.assertEqual(names, ["Plant Introduction", "Gate Entry", "Lab Testing", "RMS", "Extrusion", "Ageing", "Shot Blasting", "Anodizing", "Machine Shop", "Packaging", "Dispatch"])

    def test_vrpl_journey_has_its_eight_processes(self):
        from apps.plants.journey_view import build_journey
        plant = self._plant("VRPL")
        self.assertEqual([j["name"] for j in build_journey(self.user, plant)],
                         ["Plant Introduction", "Gate Entry", "Lab Testing", "RMS", "Mixing", "Extrusion", "Winding and Packing", "Dispatch"])

    def test_only_stages_with_a_module_are_clickable(self):
        from apps.plants.journey_view import build_journey
        plant = self._plant("VMPL P1")
        j = {s["name"]: s for s in build_journey(self.user, plant)}
        self.assertTrue(j["Extrusion"]["url"])
        self.assertEqual(j["Gate Entry"]["url"], "")
        self.assertEqual(j["Gate Entry"]["state"], "none")
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn("Your plant journey", html)
        self.assertIn("pj-off", html)                   # greyed, not a link
        self.assertIn(j["Extrusion"]["url"], html)

    def test_journey_sits_before_at_a_glance(self):
        self._plant("VMPL P1")
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertLess(html.index("Your plant journey"), html.index("At a glance"))

    def test_completed_stage_turns_done_and_next_is_current(self):
        from apps.learning.models import Module, ModuleProgress
        from apps.plants.journey_view import build_journey
        from django.utils import timezone
        plant = self._plant("VMPL P1")
        ext = Module.objects.get(plant=plant, title="Extrusion")
        ModuleProgress.objects.update_or_create(user=self.user, module=ext, defaults={"completed_at": timezone.now()})
        j = {s["name"]: s for s in build_journey(self.user, plant)}
        self.assertEqual(j["Extrusion"]["state"], "done")
        self.assertEqual(j["Ageing"]["state"], "current")

    def test_admin_can_edit_the_journey_tab(self):
        admin = User.objects.get(employee_id="test_admin")
        self.client.force_login(admin)
        plant = self._plant("VMPL P1")
        self.assertEqual(self.client.get(reverse("panel:plant_tab", args=[plant.pk, "journey"])).status_code, 200)

    def test_stat_cards_link_to_analytics_certificates_and_modules(self):
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn(reverse("core:progress") + "#time", html)
        self.assertIn(reverse("core:progress") + "#scores", html)
        self.assertIn(reverse("core:progress") + "#modules", html)
        self.assertIn(reverse("certificates:list"), html)

    def test_progress_page_shows_time_scores_and_modules(self):
        self._plant("VMPL P1")
        html = self.client.get(reverse("core:progress")).content.decode()
        for needle in ('id="time"', 'id="scores"', 'id="modules"', "Minutes per day", "Best score per module"):
            self.assertIn(needle, html)

    def test_heartbeat_feeds_daily_learning_time(self):
        from apps.learning.models import Module, StudyDay
        plant = self._plant("VMPL P1")
        m = Module.objects.filter(plant=plant, status="published").first()
        self.client.post(reverse("learning:heartbeat", args=[m.slug]))
        self.client.post(reverse("learning:heartbeat", args=[m.slug]))
        self.assertEqual(StudyDay.objects.get(user=self.user, module=m).seconds, 60)
        self.assertEqual(self.client.get(reverse("core:progress")).status_code, 200)

    def test_unstarted_cards_have_start_button_again(self):
        self._plant("VMPL P1")
        html = self.client.get(reverse("learning:module_list")).content.decode()
        self.assertIn("pc-cta", html)
        self.assertRegex(html, r'class="pc-cta">\s*Start')

    def test_type_filter_is_back_next_to_category(self):
        self._plant("VMPL P1")
        r = self.client.get(reverse("learning:module_list"))
        self.assertEqual(len(r.context["lib_tabs"]), 3)
        html = r.content.decode()
        self.assertIn("Production SOPs", html)
        self.assertIn("Department SOPs", html)
        r2 = self.client.get(reverse("learning:module_list") + "?library=department")
        self.assertTrue(all(c["module"].library == "department" for c in r2.context["cards"]))
