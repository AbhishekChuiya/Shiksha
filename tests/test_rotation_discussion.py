import io
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.learning.models import DiscussionPost, Module
from apps.quizzes.models import Attempt, Choice, Question, Quiz
from apps.quizzes.rotation import build_attempt, ordered_choices


def make_quiz(module, n_questions=8, n_choices=4, **quiz_kw):
    quiz, _ = Quiz.objects.get_or_create(module=module)
    quiz.questions.all().delete()
    for k, v in {"requires_all_steps": False, "questions_per_attempt": None, **quiz_kw}.items():
        setattr(quiz, k, v)
    quiz.save()
    for i in range(n_questions):
        q = Question.objects.create(quiz=quiz, order=i, text=f"Question {i + 1}")
        for j in range(n_choices):
            Choice.objects.create(question=q, order=j, text=f"Q{i + 1} option {j + 1}", is_correct=(j == 0))
    return quiz


class RotationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.user = User.objects.get(employee_id="test_user")
        cls.module = Module.objects.get(slug="vmpl_melt_cast")

    def attempt(self, quiz):
        ids, orders = build_attempt(quiz, self.user)
        return Attempt.objects.create(quiz=quiz, user=self.user, question_ids=ids, choice_orders=orders)

    def test_question_order_changes_every_time_and_never_repeats_the_first_question(self):
        quiz = make_quiz(self.module, 8)
        prev = None
        for _ in range(15):
            a = self.attempt(quiz)
            self.assertEqual(sorted(a.question_ids), sorted(quiz.questions.values_list("id", flat=True)))
            if prev:
                self.assertNotEqual(a.question_ids, prev.question_ids)
                self.assertNotEqual(a.question_ids[0], prev.question_ids[0], "question no.1 must change next time")
            prev = a

    def test_two_question_quiz_still_alternates(self):
        quiz = make_quiz(self.module, 2)
        firsts = [self.attempt(quiz).question_ids[0] for _ in range(8)]
        self.assertTrue(all(a != b for a, b in zip(firsts, firsts[1:])), firsts)

    def test_answer_options_rotate_per_question(self):
        quiz = make_quiz(self.module, 5)
        a1, a2 = self.attempt(quiz), self.attempt(quiz)
        for qid in a1.question_ids:
            self.assertNotEqual(a1.choice_orders[str(qid)], a2.choice_orders[str(qid)])
            self.assertEqual(sorted(a1.choice_orders[str(qid)]), sorted(a2.choice_orders[str(qid)]))

    def test_keep_choice_order_and_shuffle_switches(self):
        quiz = make_quiz(self.module, 3)
        q = quiz.questions.first()
        q.keep_choice_order = True
        q.save()
        stored = [c.id for c in q.choices.order_by("order")]
        for _ in range(6):
            self.assertEqual(self.attempt(quiz).choice_orders[str(q.id)], stored)
        quiz.shuffle_questions = quiz.shuffle_choices = False
        quiz.save()
        a = self.attempt(quiz)
        self.assertEqual(a.question_ids, list(quiz.questions.order_by("order").values_list("id", flat=True)))
        for qq in quiz.questions.all():
            self.assertEqual(a.choice_orders[str(qq.id)], [c.id for c in qq.choices.order_by("order")])

    def test_subset_quiz_rotates_through_the_whole_bank(self):
        quiz = make_quiz(self.module, 9, questions_per_attempt=3)
        seen, previous = set(), set()
        for i in range(3):
            ids = set(self.attempt(quiz).question_ids)
            self.assertEqual(len(ids), 3)
            self.assertFalse(ids & previous if i < 3 else False, "unseen questions are preferred over repeats")
            seen |= ids
            previous |= ids
        self.assertEqual(len(seen), 9)          # three attempts covered every question exactly once
        again = set(self.attempt(quiz).question_ids)   # bank exhausted -> least-recently-seen come back first
        self.assertEqual(again & set(Attempt.objects.order_by("started_at").first().question_ids), again)

    def test_view_shows_choices_in_the_attempts_order_and_grades_correctly(self):
        quiz = make_quiz(self.module, 3)
        self.client.force_login(self.user)
        orders = []
        for _ in range(2):
            self.client.post(reverse("quizzes:start", args=[self.module.slug]))
            att = Attempt.objects.filter(user=self.user).first()
            orders.append(att.choice_orders)
            for _q in att.question_ids:
                r = self.client.get(reverse("quizzes:take", args=[att.pk]))
                q = r.context["question"]
                shown = [c.pk for c in r.context["choices"]]
                self.assertEqual(shown, att.choice_orders[str(q.pk)])           # exactly what was planned
                right = next(c for c in r.context["choices"] if c.is_correct)    # pick by content, not position
                self.client.post(reverse("quizzes:take", args=[att.pk]), {"choice": right.pk})
            self.client.get(reverse("quizzes:take", args=[att.pk]))
            att.refresh_from_db()
            self.assertTrue(att.passed and att.score_percent == 100)
        self.assertNotEqual(orders[0], orders[1])

    def test_ordered_choices_helper_handles_missing_order(self):
        quiz = make_quiz(self.module, 1)
        a = Attempt.objects.create(quiz=quiz, user=self.user, question_ids=[quiz.questions.first().id])
        q = quiz.questions.first()
        self.assertEqual([c.order for c in ordered_choices(a, q)], [0, 1, 2, 3])


class DiscussionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", stdout=io.StringIO())
        cls.admin = User.objects.get(employee_id="test_admin")
        cls.u1 = User.objects.get(employee_id="test_user")
        cls.u2 = User.objects.get(employee_id="test_user2")
        cls.melt = Module.objects.get(slug="vmpl_melt_cast")
        cls.other = Module.objects.get(slug="vmpl_extrusion")

    def post(self, body, **extra):
        return self.client.post(reverse("discussion:post"), {"body": body, **extra})

    def test_global_post_visible_to_everyone_and_nav_link(self):
        self.client.force_login(self.u1)
        r = self.post("How do I check the furnace lining?")
        self.assertRedirects(r, reverse("discussion:feed"), fetch_redirect_response=False)
        self.client.force_login(self.u2)
        html = self.client.get(reverse("discussion:feed")).content.decode()
        self.assertIn("How do I check the furnace lining?", html)
        self.assertIn(reverse("discussion:feed"), self.client.get(reverse("core:dashboard")).content.decode())

    def test_module_tagged_posts_show_in_their_module_tab_and_in_global_feed(self):
        self.client.force_login(self.u1)
        self.post("Melt question", module=self.melt.slug)
        self.post("Extrusion question", module=self.other.slug)
        self.post("General question")
        tab = self.client.get(reverse("learning:module_detail", args=[self.melt.slug]) + "?tab=discussion").content.decode()
        self.assertIn("Melt question", tab)
        self.assertNotIn("Extrusion question", tab)
        self.assertNotIn("General question", tab)
        feed = self.client.get(reverse("discussion:feed")).content.decode()
        for t in ("Melt question", "Extrusion question", "General question"):
            self.assertIn(t, feed)
        only = self.client.get(reverse("discussion:feed") + f"?module={self.other.slug}").content.decode()
        self.assertIn("Extrusion question", only)
        self.assertNotIn("Melt question", only)

    def test_replies_nest_under_their_post(self):
        self.client.force_login(self.u1)
        self.post("Top post")
        top = DiscussionPost.objects.get(body="Top post")
        self.client.force_login(self.u2)
        self.post("A reply", parent=top.pk)
        reply = DiscussionPost.objects.get(body="A reply")
        self.assertEqual(reply.parent, top)
        r = self.client.get(reverse("discussion:feed"))
        post = next(p for p in r.context["posts"] if p.pk == top.pk)
        self.assertEqual([x.pk for x in post.reply_list], [reply.pk])
        self.assertNotIn(reply.pk, [p.pk for p in r.context["posts"]])          # replies are not top-level
        self.post("Reply to a reply", parent=reply.pk)                            # only one level deep
        self.assertFalse(DiscussionPost.objects.filter(body="Reply to a reply").exists())

    def test_hidden_posts_invisible_to_learners_but_visible_to_admin(self):
        self.client.force_login(self.u1)
        self.post("Bad post")
        p = DiscussionPost.objects.get(body="Bad post")
        self.client.force_login(self.admin)
        self.client.post(reverse("discussion:moderate", args=[p.pk]), {"action": "hide"})
        p.refresh_from_db()
        self.assertTrue(p.is_hidden)
        self.assertTrue(AuditLog.objects.filter(action="discussion.hide", object_id=str(p.pk)).exists())
        self.assertContains(self.client.get(reverse("discussion:feed")), "Bad post")
        self.assertContains(self.client.get(reverse("discussion:feed")), "Hidden by moderator")
        self.client.force_login(self.u2)
        self.assertNotContains(self.client.get(reverse("discussion:feed")), "Bad post")
        self.post("Reply to hidden", parent=p.pk)
        self.assertFalse(DiscussionPost.objects.filter(body="Reply to hidden").exists())

    def test_only_admins_moderate_and_pin_sorts_first(self):
        self.client.force_login(self.u1)
        self.post("Old"); self.post("Newer")
        old = DiscussionPost.objects.get(body="Old")
        self.assertEqual(self.client.post(reverse("discussion:moderate", args=[old.pk]), {"action": "pin"}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("discussion:moderate", args=[old.pk]), {"action": "pin"})
        posts = self.client.get(reverse("discussion:feed")).context["posts"]
        self.assertEqual([p.body for p in posts][:2], ["Old", "Newer"])

    def test_delete_permissions(self):
        self.client.force_login(self.u1)
        self.post("Mine")
        p = DiscussionPost.objects.get(body="Mine")
        self.client.force_login(self.u2)
        self.assertEqual(self.client.post(reverse("discussion:delete", args=[p.pk])).status_code, 403)
        self.client.force_login(self.u1)
        self.client.post(reverse("discussion:delete", args=[p.pk]))
        self.assertFalse(DiscussionPost.objects.filter(pk=p.pk).exists())
        self.post("By u1")
        q = DiscussionPost.objects.get(body="By u1")
        self.client.force_login(self.admin)
        self.client.post(reverse("discussion:delete", args=[q.pk]))
        self.assertFalse(DiscussionPost.objects.filter(pk=q.pk).exists())

    def test_deleting_a_post_deletes_its_replies(self):
        self.client.force_login(self.u1)
        self.post("Parent")
        top = DiscussionPost.objects.get(body="Parent")
        self.post("Child", parent=top.pk)
        self.client.post(reverse("discussion:delete", args=[top.pk]))
        self.assertEqual(DiscussionPost.objects.count(), 0)

    def test_empty_long_and_unsafe_input(self):
        self.client.force_login(self.u1)
        self.post("   ")
        self.assertEqual(DiscussionPost.objects.count(), 0)
        self.post("x" * 5000)
        self.assertEqual(len(DiscussionPost.objects.get().body), 4000)
        r = self.post("hello <script>alert(1)</script>", next="https://evil.example.com/")
        self.assertRedirects(r, reverse("discussion:feed"), fetch_redirect_response=False)
        html = self.client.get(reverse("discussion:feed")).content.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_unknown_or_draft_module_tag_is_ignored(self):
        self.client.force_login(self.u1)
        self.post("Tag me", module="does_not_exist")
        self.assertIsNone(DiscussionPost.objects.get(body="Tag me").module)

    def test_pagination(self):
        self.client.force_login(self.u1)
        for i in range(20):
            DiscussionPost.objects.create(author=self.u1, body=f"post {i}")
        r = self.client.get(reverse("discussion:feed"))
        self.assertEqual(len(r.context["posts"]), 15)
        self.assertEqual(len(self.client.get(reverse("discussion:feed") + "?page=2").context["posts"]), 5)

    def test_my_posts_filter_and_login_required(self):
        DiscussionPost.objects.create(author=self.u1, body="u1 post")
        DiscussionPost.objects.create(author=self.u2, body="u2 post")
        self.client.force_login(self.u1)
        html = self.client.get(reverse("discussion:feed") + "?mine=1").content.decode()
        self.assertIn("u1 post", html); self.assertNotIn("u2 post", html)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("discussion:feed")).status_code, 302)

    def test_page_renders_in_hindi(self):
        self.client.force_login(self.u1)
        self.client.cookies["django_language"] = "hi"
        html = self.client.get(reverse("discussion:feed")).content.decode()
        for needle in ("चर्चा", "सभी पोस्ट", "मेरी पोस्ट", "सबके साथ कोई प्रश्न"):
            self.assertIn(needle, html)
