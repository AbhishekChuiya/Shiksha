"""Build one quiz attempt so that nothing repeats the way it did last time.

* Question order is shuffled on every attempt and is never the same as the previous attempt's.
* If the quiz uses only N of its questions per attempt, questions the learner has not seen
  recently are preferred, so the whole bank gets rotated through.
* Answer options are shuffled too (except questions flagged "keep option order").
"""
import random

from .models import Attempt


def _shuffled_unlike(items, previous, tries=12):
    """Shuffle `items`; retry so the result differs from `previous` (and starts differently)."""
    items = list(items)
    if len(items) < 2:
        return items
    for _ in range(tries):
        random.shuffle(items)
        if previous is None or (items != previous and items[0] != previous[0]):
            return items
    # last resort for tiny sets: rotate so it still differs
    if previous is not None and items == previous:
        items = items[1:] + items[:1]
    return items


def build_attempt(quiz, user):
    """Return (question_ids, choice_orders) for a fresh attempt."""
    questions = list(quiz.questions.prefetch_related("choices"))
    previous = list(Attempt.objects.filter(quiz=quiz, user=user).order_by("-started_at")[:6])
    last = previous[0] if previous else None

    recency = {}                        # question id -> how many attempts ago it appeared (0 = last attempt)
    for age, a in enumerate(previous):
        for qid in a.question_ids:
            recency.setdefault(qid, age)

    n = min(quiz.questions_per_attempt or len(questions), len(questions))
    if n < len(questions):
        pool = sorted(questions, key=lambda q: (-recency.get(q.id, 99), random.random()))
        chosen = pool[:n]               # unseen / least recently seen first
    else:
        chosen = questions

    if quiz.shuffle_questions:
        ids = _shuffled_unlike([q.id for q in chosen], last.question_ids if last else None)
    else:
        ids = [q.id for q in sorted(chosen, key=lambda q: (q.order, q.id))]

    by_id = {q.id: q for q in chosen}
    choice_orders = {}
    for qid in ids:
        q = by_id[qid]
        base = [c.id for c in sorted(q.choices.all(), key=lambda c: (c.order, c.id))]
        if quiz.shuffle_choices and not q.keep_choice_order and len(base) > 1:
            prev_order = (last.choice_orders or {}).get(str(qid)) if last else None
            base = _shuffled_unlike(base, prev_order)
        choice_orders[str(qid)] = base
    return ids, choice_orders


def ordered_choices(attempt, question):
    """The question's choices in the order this attempt displays them."""
    order = (attempt.choice_orders or {}).get(str(question.id))
    choices = list(question.choices.all())
    if not order:
        return sorted(choices, key=lambda c: (c.order, c.id))
    pos = {cid: i for i, cid in enumerate(order)}
    return sorted(choices, key=lambda c: (pos.get(c.id, 10_000), c.order, c.id))
