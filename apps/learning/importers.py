"""Bulk import of SOP steps and quiz questions from CSV rows (used by the admin panel and the manage.py commands)."""
import re

from django.db import transaction
from django.utils.text import slugify

from apps.quizzes.models import Choice, Question, Quiz

from apps.plants.models import Department, Plant, Process

from .models import Module, ModuleSOP, SOPStep


class ImportError_(ValueError):
    """Message is safe to show to the admin."""


@transaction.atomic
def import_steps(module, rows, replace=True, sop=None):
    rows = [r for r in rows if (r.get("text") or "").strip()]
    if not rows:
        raise ImportError_("No steps found. The file needs a header row with: step, text (and optionally text_hi).")
    existing = module.steps.filter(sop=sop)
    start = 0
    if replace:
        existing.delete()
    else:
        start = existing.count()
    for i, r in enumerate(rows, start=1):
        SOPStep.objects.create(module=module, sop=sop, number=start + i, text=r["text"].strip(), text_hi=(r.get("text_hi") or "").strip(), text_gu=(r.get("text_gu") or "").strip())
    return len(rows)


@transaction.atomic
def import_quiz(module, rows, pass_percent=None, replace=True):
    quiz, _ = Quiz.objects.get_or_create(module=module)
    if pass_percent is not None:
        quiz.pass_percent = pass_percent
        quiz.save()
    rows = [r for r in rows if (r.get("question") or "").strip()]
    if not rows:
        raise ImportError_("No questions found. The file needs a header row with: question, option_a, option_b, option_c, option_d, correct.")
    if replace:
        quiz.questions.all().delete()
    base = quiz.questions.count()
    for i, r in enumerate(rows):
        letters = [k for k in "abcdef" if (r.get(f"option_{k}") or "").strip()]
        correct = (r.get("correct") or "").strip().lower()
        if len(letters) < 2:
            raise ImportError_(f"Row {r.get('_row', i + 2)}: a question needs at least two options.")
        if correct not in letters:
            raise ImportError_(f"Row {r.get('_row', i + 2)}: 'correct' must be one of {', '.join(x.upper() for x in letters)}.")
        q = Question.objects.create(quiz=quiz, order=base + i, text=r["question"].strip(), text_hi=(r.get("question_hi") or "").strip(), text_gu=(r.get("question_gu") or "").strip(),
                                    kind=(r.get("kind") or "Diagnostic").strip(), explanation=(r.get("explanation") or "").strip(),
                                    explanation_hi=(r.get("explanation_hi") or "").strip(), explanation_gu=(r.get("explanation_gu") or "").strip())
        for j, k in enumerate(letters):
            Choice.objects.create(question=q, order=j, text=r[f"option_{k}"].strip(), text_hi=(r.get(f"option_{k}_hi") or "").strip(), text_gu=(r.get(f"option_{k}_gu") or "").strip(), is_correct=(k == correct))
    return len(rows)


# ----------------------------------------------------------------- whole-file imports (one file, many modules)
def _plant(name):
    name = (name or "").strip()
    if not name:
        return None
    return Plant.objects.filter(name__iexact=name).first() or Plant.objects.filter(code__iexact=name).first()


def find_module(ident, plant=None):
    """Find a module by its slug or its exact title. Returns (module, error)."""
    ident = (ident or "").strip()
    if not ident:
        return None, "the 'module' column is empty"
    qs = Module.objects.all()
    hit = qs.filter(slug__iexact=ident)
    if not hit:
        hit = qs.filter(title__iexact=ident)
        if plant:
            hit = hit.filter(plant=plant) or hit
    if len(hit) == 1:
        return hit[0], None
    if len(hit) > 1:
        return None, f"“{ident}” matches {len(hit)} modules — use the module's slug instead"
    return None, f"no module called “{ident}” — create it first (Import → Modules) or check the spelling"


def _resolve_sop(module, ident):
    """The SOP a row belongs to: matched by document number or title inside the module; created if it is new."""
    ident = (ident or "").strip()
    if not ident:
        return None
    hit = module.sops.filter(code__iexact=ident).first() or module.sops.filter(title__iexact=ident).first()
    return hit or ModuleSOP.objects.create(module=module, title=ident, order=module.sops.count())


def _raise_errors(errors):
    if errors:
        shown = "\n".join(errors[:10])
        more = f"\n…and {len(errors) - 10} more problem(s)." if len(errors) > 10 else ""
        raise ImportError_(f"Nothing was imported — please fix these and upload again:\n{shown}{more}")


def _unique_slug(plant, title):
    base = slugify(f"{plant.code}_{title}").replace("-", "_")[:70] or "module"
    slug, n = base, 2
    while Module.objects.filter(slug=slug).exists():
        slug, n = f"{base}_{n}", n + 1
    return slug


LIBRARY_WORDS = {"production": "production", "production sops": "production", "department": "department", "department sops": "department"}
STATUS_WORDS = {"published": "published", "publish": "published", "live": "published", "draft": "draft", "archived": "archived"}


@transaction.atomic
def import_modules(rows, default_plant=None):
    """Create new modules, or update existing ones (matched by slug, else plant + title). Returns (created, updated)."""
    created = updated = 0
    errors = []
    rows = [r for r in rows if (r.get("title") or r.get("slug") or "").strip()]
    if not rows:
        raise ImportError_("No modules found. The file needs a header row with at least: title, department.")
    for r in rows:
        n = r.get("_row", "?")
        plant = _plant(r.get("plant")) if (r.get("plant") or "").strip() else default_plant
        if plant is None:
            errors.append(f"Row {n}: unknown plant “{r.get('plant', '')}”" if r.get("plant") else f"Row {n}: choose a plant (or fill the 'plant' column)")
            continue
        slug = (r.get("slug") or "").strip().lower()
        title = (r.get("title") or "").strip()
        module = Module.objects.filter(slug=slug).first() if slug else Module.objects.filter(plant=plant, title__iexact=title).first()
        dept_name = (r.get("department") or "").strip()
        if module is None and not (title and dept_name):
            errors.append(f"Row {n}: a new module needs both 'title' and 'department'")
            continue
        status = STATUS_WORDS.get((r.get("status") or "").strip().lower())
        if (r.get("status") or "").strip() and not status:
            errors.append(f"Row {n}: status must be published, draft or archived")
            continue
        library = LIBRARY_WORDS.get((r.get("library") or "").strip().lower())
        if (r.get("library") or "").strip() and not library:
            errors.append(f"Row {n}: library must be “production” or “department”")
            continue
        mins = (r.get("est_minutes") or r.get("minutes") or "").strip()
        if mins and not mins.isdigit():
            errors.append(f"Row {n}: est_minutes must be a whole number")
            continue
        is_new = module is None
        if is_new:
            module = Module(plant=plant, slug=slug or _unique_slug(plant, title), status="draft", order=Module.objects.filter(plant=plant).count())
        if dept_name:
            module.department = Department.objects.get_or_create(plant=module.plant, name=dept_name, defaults={"order": module.plant.departments.count()})[0]
        for f in ("title", "title_hi", "title_gu", "purpose", "purpose_hi", "purpose_gu", "category", "category_hi", "category_gu", "summary", "summary_hi", "summary_gu", "overview", "overview_hi", "overview_gu", "instructor"):
            v = (r.get(f) or "").strip()
            if v:
                setattr(module, f, v)
        for f in ("objectives", "objectives_hi", "objectives_gu"):
            v = (r.get(f) or "").strip()
            if v:
                setattr(module, f, "\n".join(x.strip() for x in v.replace("|", "\n").splitlines() if x.strip()))
        if mins:
            module.est_minutes = int(mins)
        if status:
            module.status = status
        if library:
            module.library = library
        if module.category and module.department_id:
            module.process = Process.objects.get_or_create(department=module.department, name=module.category)[0]
        module.save()
        created += is_new
        updated += not is_new
    _raise_errors(errors)
    return created, updated


@transaction.atomic
def import_steps_bulk(rows, replace=False):
    """Steps for many modules from one file. Columns: module, step (optional order), text, text_hi."""
    rows = [r for r in rows if (r.get("text") or "").strip() or (r.get("module") or "").strip()]
    if not rows:
        raise ImportError_("No steps found. The file needs a header row with: module, step, text (and optionally text_hi).")
    errors, groups = [], {}
    for r in rows:
        n = r.get("_row", "?")
        module, err = find_module(r.get("module"))
        if err:
            errors.append(f"Row {n}: {err}")
        elif not (r.get("text") or "").strip():
            errors.append(f"Row {n}: the step text is empty")
        else:
            sop = _resolve_sop(module, r.get("sop"))
            groups.setdefault((module.pk, sop.pk if sop else None), (module, sop, []))[2].append(r)
    _raise_errors(errors)
    total = 0
    for module, sop, items in groups.values():
        items.sort(key=lambda x: (int(x["step"]) if (x.get("step") or "").isdigit() else 10**6, x.get("_row", 0)))
        total += import_steps(module, items, replace=replace, sop=sop)
    return total, len(groups)


@transaction.atomic
def import_quiz_bulk(rows, replace=False):
    """Quiz questions for many modules from one file (same columns as the per-module import plus 'module')."""
    rows = [r for r in rows if (r.get("question") or "").strip() or (r.get("module") or "").strip()]
    if not rows:
        raise ImportError_("No questions found. The file needs a header row with: module, question, option_a, option_b, option_c, option_d, correct.")
    errors, groups = [], {}
    for r in rows:
        module, err = find_module(r.get("module"))
        if err:
            errors.append(f"Row {r.get('_row', '?')}: {err}")
        else:
            groups.setdefault(module.pk, (module, []))[1].append(r)
    _raise_errors(errors)
    total = 0
    for module, items in groups.values():
        try:
            total += import_quiz(module, items, replace=replace)
        except ImportError_ as exc:
            errors.append(f"{module.title}: {exc}")
    _raise_errors(errors)
    return total, len(groups)


PLANT_TEXT_FIELDS = ("company", "location", "location_hi", "location_gu", "tagline", "tagline_hi", "tagline_gu", "about", "about_hi", "about_gu")


def _split_list(value):
    return [x.strip() for x in re.split(r"[,;|\n]", value or "") if x.strip()]


@transaction.atomic
def import_plants(rows):
    """Create plants (or update the ones with the same name) and their departments. Photos / banner / videos stay manual."""
    rows = [r for r in rows if (r.get("name") or "").strip()]
    if not rows:
        raise ImportError_("No plants found. The file needs a header row with at least: name.")
    created = updated = 0
    for r in rows:
        name = r["name"].strip()
        plant = Plant.objects.filter(name__iexact=name).first()
        is_new = plant is None
        if is_new:
            plant = Plant(name=name, order=Plant.objects.count())
        for f in PLANT_TEXT_FIELDS:
            v = (r.get(f) or "").strip()
            if v:
                setattr(plant, f, v)
        code = slugify(r.get("code") or "")[:20]
        if code:
            plant.code = code
        elif is_new:
            base = slugify(name)[:18] or "plant"
            plant.code, n = base, 2
            while Plant.objects.filter(code=plant.code).exists():
                plant.code, n = f"{base}-{n}", n + 1
        elif not plant.code:
            plant.code = slugify(name)[:20]
        if Plant.objects.filter(code=plant.code).exclude(pk=plant.pk).exists():
            raise ImportError_(f"Row {r.get('_row', '?')}: the code “{plant.code}” is already used by another plant.")
        plant.save()
        hi, gu = _split_list(r.get("departments_hi")), _split_list(r.get("departments_gu"))
        for i, dept in enumerate(_split_list(r.get("departments"))):
            d, _ = Department.objects.get_or_create(plant=plant, name=dept, defaults={"order": plant.departments.count()})
            if i < len(hi) and not d.name_hi:
                d.name_hi = hi[i]
            if i < len(gu) and not d.name_gu:
                d.name_gu = gu[i]
            d.save()
        created += is_new
        updated += not is_new
    return created, updated
