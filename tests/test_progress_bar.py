import re

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.learning.models import Module


class ProgressBarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        cls.user = User.objects.get(employee_id="test_user2")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")

    def setUp(self):
        self.client.force_login(self.user)
        self.client.post(reverse("learning:ack_safety", args=[self.melt.slug]))

    def page(self, step=None):
        qs = "?tab=sops" + (f"&step={step}" if step else "")
        return self.client.get(reverse("learning:module_detail", args=[self.melt.slug]) + qs)

    def mark(self, n):
        self.client.post(reverse("learning:toggle_step", args=[self.melt.slug, n]))

    def test_bar_replaces_the_number_grid(self):
        html = self.page().content.decode()
        for needle in ("sop-progress", "sop-fill", "sop-mark", "Jump to step", "data-jump-input"):
            self.assertIn(needle, html)
        self.assertNotIn('class="dots"', html)
        self.assertNotIn('class="card rail"', html)

    def test_fill_width_follows_completed_steps_and_marker_follows_position(self):
        self.assertIn('class="sop-fill" style="width:0%"', self.page().content.decode())
        for n in range(1, 8):          # 7 of 31 done
            self.mark(n)
        html = self.page().content.decode()
        self.assertIn('style="width:23%"', html)                         # round(100*7/31)
        self.assertIn("7 of 31 done", html)
        self.assertIn("Step 8 of 31", html)                              # resumes at the first unfinished step
        mark = float(re.search(r'class="sop-mark" style="left:([\d.]+)%"', html).group(1))
        self.assertAlmostEqual(mark, round(100 * 7.5 / 31, 1), places=1)

    def test_bar_turns_green_when_everything_is_done(self):
        for n in range(1, 32):
            self.mark(n)
        self.assertIn("sop-progress complete", self.page().content.decode())
        self.assertIn("100%", self.page().content.decode())

    def test_jump_list_has_every_step_with_preview_and_status(self):
        for n in (1, 2, 3):
            self.mark(n)
        r = self.page(10)
        dots = r.context["step_dots"]
        self.assertEqual(len(dots), 31)
        self.assertEqual([d["number"] for d in dots if d["current"]], [10])
        self.assertEqual([d["number"] for d in dots if d["done"]], [1, 2, 3])
        self.assertTrue(all(d["preview"] for d in dots))
        html = r.content.decode()
        self.assertEqual(html.count('class="dd-item jump-item'), 31)
        self.assertIn('href="?tab=sops&step=31"', html)
        self.assertIn("data-soft", html)

    def test_jump_target_urls_work_and_bad_values_are_safe(self):
        self.assertIn("Step 20 of 31", self.page(20).content.decode())
        for bad in ("999", "0", "-3", "abc", ""):
            self.assertEqual(self.client.get(reverse("learning:module_detail", args=[self.melt.slug]) + f"?tab=sops&step={bad}").status_code, 200, bad)

    def test_progress_bar_in_hindi(self):
        self.client.cookies["django_language"] = "hi"
        html = self.page().content.decode()
        for needle in ("चरण पर जाएँ", "चरण 1 / 31", "0 / 31 पूरे", "जाएँ"):
            self.assertIn(needle, html)
        self.assertNotIn("Jump to step", html)

    def test_locked_steps_show_no_bar(self):
        other = User.objects.get(employee_id="test_user")
        self.client.force_login(other)
        self.assertNotIn("sop-progress", self.page().content.decode())
