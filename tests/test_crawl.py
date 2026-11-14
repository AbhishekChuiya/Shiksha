"""Walk every page reachable by links (as learner and as admin) and fail on any 404/500 or dead link."""
import re
from urllib.parse import urlparse
from django.core.management import call_command
from django.test import TestCase
from apps.accounts.models import User

LINK = re.compile(r'(?:href|action)="(/[^"#]*)')


class CrawlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=open("/dev/null", "w"))

    def crawl(self, email, limit=400):
        self.client.force_login(User.objects.get(email=email))
        seen, queue, bad = set(), ["/"], []
        while queue and len(seen) < limit:
            url = queue.pop(0)
            if url in seen or url.startswith(("/static", "/media", "/accounts/logout", "/i18n", "/manage/logout")):
                continue
            seen.add(url)
            r = self.client.get(url, follow=True)
            if r.status_code == 405: continue  # POST-only form action
            if r.status_code >= 400:
                bad.append((url, r.status_code)); continue
            if "text/html" not in r["Content-Type"]:
                continue
            for m in LINK.findall(r.content.decode()):
                if m.endswith(("[object HTMLInputElement]",)) or "%5Bobject" in m:
                    bad.append((url, "bad link " + m))
                if urlparse(m).path not in seen and m not in seen:
                    queue.append(m)
        self.assertEqual(bad, [])
        return seen

    def test_learner_pages(self):
        self.assertGreater(len(self.crawl("test_user@vishakha.com")), 20)

    def test_admin_pages(self):
        self.assertGreater(len(self.crawl("test_admin@vishakha.com")), 30)
