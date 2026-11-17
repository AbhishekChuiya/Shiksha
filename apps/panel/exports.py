"""Excel exports of everything the application holds. Columns match the import files, so a downloaded file
can be edited in Excel and uploaded again (plants, modules, SOP steps and quiz questions)."""
import datetime
import io

from apps.accounts.models import User
from apps.knowledge.models import KBItem
from apps.learning.models import (Module, ModuleEscalation, ModuleRecord, ModuleRole, ModuleSOP, SafetyGuideline, SOPStep)
from apps.plants.models import Department, Plant, Process
from apps.quizzes.models import Question

LANGS = ("", "_hi", "_gu")


def _join(values, sep=", "):
    return sep.join(v for v in values if v)


def _sop_ref(sop):
    return (sop.code or sop.title) if sop else ""


def plants():
    head = ["name", "code", "company", "location", "tagline", "about", "departments", "location_hi", "tagline_hi", "about_hi", "departments_hi",
            "location_gu", "tagline_gu", "about_gu", "departments_gu", "is_active"]
    rows = []
    for p in Plant.objects.prefetch_related("departments").order_by("order", "name"):
        depts = list(p.departments.all())
        rows.append([p.name, p.code, p.company, p.location, p.tagline, p.about, _join(d.name for d in depts),
                     p.location_hi, p.tagline_hi, p.about_hi, _join(d.name_hi for d in depts),
                     p.location_gu, p.tagline_gu, p.about_gu, _join(d.name_gu for d in depts), "yes" if p.is_active else "no"])
    return head, rows


def structure():
    head = ["plant", "department", "department_hi", "department_gu", "process", "process_hi", "process_gu"]
    rows = []
    for d in Department.objects.select_related("plant").prefetch_related("processes").order_by("plant__order", "order", "name"):
        procs = list(d.processes.all()) or [None]
        for pr in procs:
            rows.append([d.plant.name, d.name, d.name_hi, d.name_gu, pr.name if pr else "", pr.name_hi if pr else "", pr.name_gu if pr else ""])
    return head, rows


def modules():
    head = ["title", "department", "plant", "category", "summary", "overview", "purpose", "objectives", "est_minutes", "library", "status", "slug", "instructor", "required", "due_date"]
    for lang in ("_hi", "_gu"):
        head += [f"{f}{lang}" for f in ("title", "category", "summary", "overview", "purpose", "objectives")]
    rows = []
    for m in Module.objects.select_related("plant", "department").order_by("plant__order", "department__order", "order", "title"):
        row = [m.title, m.department.name, m.plant.name, m.category, m.summary, m.overview, m.purpose, "|".join(x.strip() for x in m.objectives.splitlines() if x.strip()),
               m.est_minutes, m.library, m.status, m.slug, m.instructor, "yes" if m.is_mandatory else "no", m.due_date.isoformat() if m.due_date else ""]
        for lang in ("_hi", "_gu"):
            row += [getattr(m, f"{f}{lang}") if f != "objectives" else "|".join(x.strip() for x in getattr(m, f"objectives{lang}").splitlines() if x.strip())
                    for f in ("title", "category", "summary", "overview", "purpose", "objectives")]
        rows.append(row)
    return head, rows


def sops():
    head = ["module", "sop", "document_number", "revision", "document_date", "languages", "safety_statement", "title_hi", "safety_statement_hi", "title_gu", "safety_statement_gu", "order"]
    rows = [[s.module.slug, s.title, s.code, s.revision, s.doc_date.isoformat() if s.doc_date else "", s.languages, s.intro, s.title_hi, s.intro_hi, s.title_gu, s.intro_gu, s.order]
            for s in ModuleSOP.objects.select_related("module").order_by("module__plant__order", "module__order", "order", "id")]
    return head, rows


def steps():
    head = ["module", "sop", "text", "text_hi", "text_gu"]
    rows = [[st.module.slug, _sop_ref(st.sop), st.text, st.text_hi, st.text_gu]
            for st in SOPStep.objects.select_related("module", "sop").order_by("module__plant__order", "module__order", "module_id", "sop__order", "sop_id", "number")]
    return head, rows


def rules():
    head = ["applies_to", "module", "sop", "plant", "group", "text", "text_hi", "text_gu"]
    rows = []
    for g in SafetyGuideline.objects.select_related("module", "sop", "plant").order_by("plant_id", "module_id", "sop_id", "section", "order", "id"):
        applies = "SOP" if g.sop_id else ("Module" if g.module_id else ("Plant" if g.plant_id else "Everywhere"))
        rows.append([applies, g.module.slug if g.module_id else "", _sop_ref(g.sop), g.plant.name if g.plant_id else "", g.get_section_display(), g.text, g.text_hi, g.text_gu])
    return head, rows


def process_info():
    """Who does what, escalation and records, one table with a 'kind' column."""
    head = ["module", "kind", "text", "responsible_or_action", "accountable_or_code", "text_hi", "responsible_or_action_hi", "accountable_or_code_hi",
            "text_gu", "responsible_or_action_gu", "accountable_or_code_gu"]
    rows = []
    for r in ModuleRole.objects.select_related("module").order_by("module_id", "order", "id"):
        rows.append([r.module.slug, "Who does what", r.activity, r.responsible, r.accountable, r.activity_hi, r.responsible_hi, r.accountable_hi, r.activity_gu, r.responsible_gu, r.accountable_gu])
    for e in ModuleEscalation.objects.select_related("module").order_by("module_id", "order", "id"):
        rows.append([e.module.slug, "Escalation", e.situation, e.action, "", e.situation_hi, e.action_hi, "", e.situation_gu, e.action_gu, ""])
    for r in ModuleRecord.objects.select_related("module").order_by("module_id", "order", "id"):
        rows.append([r.module.slug, "Record", r.name, "", r.code, r.name_hi, "", "", r.name_gu, "", ""])
    return head, rows


def quiz():
    qs = list(Question.objects.select_related("quiz__module").prefetch_related("choices").order_by("quiz__module__plant__order", "quiz__module__order", "quiz_id", "order", "id"))
    n = max([4] + [len(q.choices.all()) for q in qs])
    letters = "abcdefghij"[:min(n, 10)]
    head = ["module", "question", *[f"option_{c}" for c in letters], "correct", "kind", "explanation",
            "question_hi", *[f"option_{c}_hi" for c in letters], "explanation_hi", "question_gu", *[f"option_{c}_gu" for c in letters], "explanation_gu"]
    rows = []
    for q in qs:
        ch = sorted(q.choices.all(), key=lambda c: (c.order, c.id))[:len(letters)]
        pad = [None] * (len(letters) - len(ch))
        correct = next((letters[i].upper() for i, c in enumerate(ch) if c.is_correct), "")
        rows.append([q.quiz.module.slug, q.text, *[c.text for c in ch], *["" for _ in pad], correct, q.kind, q.explanation,
                     q.text_hi, *[c.text_hi for c in ch], *["" for _ in pad], q.explanation_hi,
                     q.text_gu, *[c.text_gu for c in ch], *["" for _ in pad], q.explanation_gu])
    return head, rows


def users():
    head = ["first_name", "last_name", "email", "employee_id", "designation", "role", "department", "plants", "default_plant", "is_active", "last_login"]
    rows = [[u.first_name, u.last_name, u.email, u.employee_id or "", u.designation, u.role, u.department.name if u.department_id else "", _join(p.name for p in u.plants.all()),
             u.default_plant.name if u.default_plant_id else "", "yes" if u.is_active else "no", u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else ""]
            for u in User.objects.select_related("department", "default_plant").prefetch_related("plants").order_by("email")]
    return head, rows


def knowledge():
    head = ["title", "category", "kind", "plant", "url", "file", "description", "title_hi", "description_hi", "title_gu", "description_gu", "is_active"]
    rows = [[k.title, k.category.name, k.kind, k.plant.name if k.plant_id else "", k.url, k.file.name if k.file else "", k.description, k.title_hi, k.description_hi,
             k.title_gu, k.description_gu, "yes" if k.is_active else "no"] for k in KBItem.objects.select_related("category", "plant").order_by("category__order", "order", "title")]
    return head, rows


DATASETS = {
    "plants": ("Plants", plants, "Plant list with company, location, tagline, about, departments — English, Hindi and Gujarati."),
    "modules": ("Modules", modules, "Every module with its texts in all three languages."),
    "steps": ("SOP steps", steps, "All SOP steps, with their SOP, in all three languages."),
    "quiz": ("Quiz questions", quiz, "All questions, options, correct answers and explanations."),
    "users": ("Users", users, "Everyone with an account: name, email, role, plants."),
    "knowledge": ("Knowledge base", knowledge, "Every document, video and link in the Knowledge Base."),
    "sops": ("SOPs in modules", sops, "SOP title, document number, revision, date, languages, safety statement."),
    "rules": ("Safety rules", rules, "PPE, pre-start checks, hazards and other rules, per SOP / module / plant."),
    "process": ("Process info", process_info, "Who does what, escalation and records of every module."),
}
EVERYTHING = [("Plants", plants), ("Departments & processes", structure), ("Modules", modules), ("SOPs", sops), ("SOP steps", steps), ("Safety rules", rules),
              ("Process info", process_info), ("Quiz questions", quiz), ("Users", users), ("Knowledge base", knowledge)]


def workbook(sheets):
    """sheets: [(title, head, rows)] -> bytes of an .xlsx file with a red header row."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    wb.remove(wb.active)
    for title, head, rows in sheets:
        ws = wb.create_sheet(title[:31])
        ws.append(head)
        for r in rows:
            ws.append(r)
            for c in ws[ws.max_row]:
                if isinstance(c.value, str) and c.value[:1] in ("=",):
                    c.data_type = "s"                      # text that starts with "=" must never become a formula
        for i, h in enumerate(head, start=1):
            c = ws.cell(row=1, column=i)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="C8102E")
            widest = max([len(str(h))] + [min(len(str(r[i - 1] if i - 1 < len(r) else "")), 60) for r in rows[:200]])
            ws.column_dimensions[get_column_letter(i)].width = max(12, min(48, widest + 3))
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
    info = wb.create_sheet("About this file", 0 if len(sheets) > 1 else len(sheets))
    for line in (("Project Shiksha — data export",), (f"Downloaded on {datetime.date.today():%d %b %Y}",), ("",),
                 ("The columns match the import files, so you can edit this file and upload it again under Import from Excel.",),
                 ("Passwords are never included.",)):
        info.append(line)
    info.column_dimensions["A"].width = 100
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
