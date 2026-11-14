import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import User
from apps.learning.models import Module

TMP = tempfile.mkdtemp(prefix="shiksha-media-")


def make_image(fmt="PNG", size=(600, 400), color=(200, 20, 40), name="me.png"):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


@override_settings(MEDIA_ROOT=TMP)
class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.get(employee_id="test_user")
        self.client.force_login(self.user)

    def test_account_page_and_menu_links(self):
        r = self.client.get(reverse("accounts:account"))
        self.assertContains(r, "My account")
        self.assertContains(r, "Profile photo")
        self.assertContains(r, "Change password")
        self.assertContains(self.client.get(reverse("core:dashboard")), reverse("accounts:account"))

    def test_old_settings_url_redirects(self):
        self.assertRedirects(self.client.get("/accounts/password/change/"), reverse("accounts:account"),
                             fetch_redirect_response=False)

    def test_photo_upload_is_square_small_jpeg_and_shown_in_topbar(self):
        self.client.post(reverse("accounts:photo_update"), {"photo": make_image(size=(900, 500))})
        self.user.refresh_from_db()
        self.assertTrue(self.user.photo)
        with Image.open(self.user.photo.path) as im:
            self.assertEqual(im.size, (320, 320))
            self.assertEqual(im.format, "JPEG")
        self.assertContains(self.client.get(reverse("core:dashboard")), f'src="{self.user.photo.url}"')

    def test_png_with_transparency_and_webp_accepted(self):
        for fmt in ("WEBP", "PNG"):
            self.client.post(reverse("accounts:photo_update"), {"photo": make_image(fmt, name=f"a.{fmt.lower()}")})
            self.user.refresh_from_db()
            self.assertTrue(self.user.photo, fmt)

    def test_non_image_and_fake_extension_rejected(self):
        bad = SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png")
        r = self.client.post(reverse("accounts:photo_update"), {"photo": bad}, follow=True)
        self.user.refresh_from_db()
        self.assertFalse(self.user.photo)
        self.assertContains(r, "JPG, PNG or WEBP")

    def test_gif_rejected(self):
        self.client.post(reverse("accounts:photo_update"), {"photo": make_image("GIF", name="a.gif")})
        self.user.refresh_from_db()
        self.assertFalse(self.user.photo)

    def test_oversized_file_rejected(self):
        big = SimpleUploadedFile("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 10), content_type="image/png")
        r = self.client.post(reverse("accounts:photo_update"), {"photo": big}, follow=True)
        self.user.refresh_from_db()
        self.assertFalse(self.user.photo)
        self.assertContains(r, "too large")

    def test_replacing_and_removing_photo_deletes_old_file(self):
        import os
        self.client.post(reverse("accounts:photo_update"), {"photo": make_image()})
        self.user.refresh_from_db(); first = self.user.photo.path
        self.client.post(reverse("accounts:photo_update"), {"photo": make_image(color=(0, 90, 200))})
        self.user.refresh_from_db(); second = self.user.photo.path
        self.assertNotEqual(first, second); self.assertFalse(os.path.exists(first)); self.assertTrue(os.path.exists(second))
        self.client.post(reverse("accounts:photo_update"), {"action": "remove"})
        self.user.refresh_from_db()
        self.assertFalse(self.user.photo); self.assertFalse(os.path.exists(second))

    def test_photo_endpoint_requires_login_and_post(self):
        self.client.logout()
        self.assertEqual(self.client.post(reverse("accounts:photo_update"), {}).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:photo_update")).status_code, 405)

    def test_name_update(self):
        self.client.post(reverse("accounts:profile_update"), {"first_name": "Asha", "last_name": "Mehta"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Asha Mehta")

    def test_password_change_works_and_keeps_user_signed_in(self):
        r = self.client.post(reverse("accounts:account"), {"old_password": "Test@12345",
                             "new_password1": "Brand-New-Pass-77", "new_password2": "Brand-New-Pass-77"})
        self.assertRedirects(r, reverse("accounts:account"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)  # still signed in
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand-New-Pass-77"))

    def test_wrong_old_password_rejected(self):
        self.client.post(reverse("accounts:account"), {"old_password": "nope", "new_password1": "Brand-New-Pass-77", "new_password2": "Brand-New-Pass-77"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Test@12345"))

    def test_account_page_in_hindi(self):
        self.client.cookies["django_language"] = "hi"
        html = self.client.get(reverse("accounts:account")).content.decode()
        for needle in ("मेरा खाता", "प्रोफ़ाइल फ़ोटो", "फ़ोटो चुनें", "खाते का विवरण"):
            self.assertIn(needle, html)


class ModuleGridTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        cls.user = User.objects.get(employee_id="test_user")
        cls.base = Module.objects.get(slug="vmpl_melt_cast")
        # grow the catalogue to 60 production modules to exercise paging
        for i in range(50):
            Module.objects.create(slug=f"bulk_{i}", plant=cls.base.plant, department=cls.base.department, title=f"Bulk module {i:02d}",
                                  summary="x", category="Bulk", order=100 + i)

    def setUp(self):
        self.client.force_login(self.user)

    def test_rows_view_has_view_all_links_and_tile(self):
        r = self.client.get(reverse("learning:module_list"))
        self.assertContains(r, "view-all-tile")
        prod = next(s for s in r.context["sections"] if s["dept"].name == "Production")
        self.assertTrue(prod["view_all"].startswith("?"))
        self.assertIn("view=grid", prod["view_all"]); self.assertIn(f"dept={self.base.department_id}", prod["view_all"])
        self.assertContains(r, 'class="mod-card extra"')  # cards beyond the 8th are hidden on phones

    def test_grid_view_paginates_and_shows_every_module(self):
        url = reverse("learning:module_list") + f"?dept={self.base.department_id}&view=grid"
        r = self.client.get(url)
        self.assertContains(r, "grid-all")
        self.assertEqual(r.context["page_obj"].paginator.count, 58)
        self.assertEqual(len(r.context["cards"]), 24)
        self.assertTrue(r.context["next_url"] and not r.context["prev_url"])
        r3 = self.client.get(url + "&page=3")
        self.assertEqual(len(r3.context["cards"]), 10)
        self.assertTrue(r3.context["prev_url"] and not r3.context["next_url"])
        self.assertContains(r3, "Page 3 of 3")

    def test_grid_search_is_server_side_across_all_pages(self):
        r = self.client.get(reverse("learning:module_list") + "?view=grid&q=Bulk module 49")
        self.assertEqual([c["module"].title for c in r.context["cards"]], ["Bulk module 49"])
        r = self.client.get(reverse("learning:module_list") + "?view=grid&q=zzzz-none")
        self.assertContains(r, "No modules match")

    def test_filters_keep_view_and_search_in_links(self):
        r = self.client.get(reverse("learning:module_list") + "?view=grid&q=melt")
        qc = r.context["dept_chips"][1][1]
        self.assertIn("view=grid", qc); self.assertIn("q=melt", qc)

    def test_bad_params_do_not_crash(self):
        for qs in ("?dept=abc", "?dept=99999&view=grid", "?view=grid&page=zzz", "?view=grid&page=-4", "?category=<script>"):
            self.assertEqual(self.client.get(reverse("learning:module_list") + qs).status_code, 200, qs)

    def test_grid_in_hindi_keeps_hindi_names(self):
        self.client.cookies["django_language"] = "hi"
        html = self.client.get(reverse("learning:module_list") + f"?dept={self.base.department_id}&view=grid").content.decode()
        self.assertIn("प्रोडक्शन", html); self.assertIn("मेल्ट और कास्ट", html)


class SidebarTests(TestCase):
    def test_sidebar_footer_css_uses_dynamic_viewport(self):
        css = open("static/css/shiksha.css", encoding="utf-8").read()
        self.assertIn("height: 100dvh", css)
        self.assertIn("safe-area-inset-bottom", css)


class AccountPageFocusTest(TestCase):
    def test_password_field_does_not_autofocus(self):
        call_command("seed_demo", stdout=open("/dev/null", "w"))
        self.client.force_login(User.objects.get(employee_id="test_user"))
        html = self.client.get(reverse("accounts:account")).content.decode()
        self.assertNotIn("autofocus", html)
