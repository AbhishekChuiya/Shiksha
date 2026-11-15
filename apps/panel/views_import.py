"""Import centre: modules, SOP steps and quiz questions from an Excel / CSV file, plus downloadable sample files."""
import csv
import io

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from apps.learning.importers import ImportError_, import_modules, import_quiz_bulk, import_steps_bulk
from apps.learning.models import Module
from apps.learning.tables import TableError, read_table
from apps.plants.models import Plant

from .decorators import admin_required
from .views import audit, render_panel

# (column, required?, what to write)
COLUMNS = {
    "modules": [
        ("title", True, "Module name, e.g. Melt & Cast"), ("department", True, "Production, QC or Maintenance (created if new)"),
        ("plant", False, "Plant name. Leave empty to use the plant you pick on this page"), ("category", False, "Filter chip, e.g. Extrusion"),
        ("summary", False, "One-line description shown on the card"), ("overview", False, "Longer description"),
        ("objectives", False, "Learning objectives separated by | (pipe)"), ("est_minutes", False, "Time in minutes (a whole number)"),
        ("library", False, "production or department"), ("status", False, "published, draft or archived (new modules start as draft)"),
        ("title_hi / summary_hi / overview_hi / objectives_hi / category_hi", False, "The same text in Hindi"), ("…_gu (title_gu, summary_gu …)", False, "The same text in Gujarati"), ("slug", False, "Leave empty — made automatically. Fill it only to update an existing module"),
    ],
    "steps": [
        ("module", True, "The module's name or slug (see Modules list)"), ("step", False, "Order number. Leave empty to keep the order of the rows"),
        ("text", True, "The instruction for this step"), ("text_hi", False, "The same instruction in Hindi"), ("text_gu", False, "The same instruction in Gujarati"),
    ],
    "quiz": [
        ("module", True, "The module's name or slug"), ("question", True, "The question"),
        ("option_a … option_d", True, "Answer choices (at least two; up to option_f)"), ("correct", True, "Letter of the right answer: A, B, C or D"),
        ("kind", False, "Diagnostic, Safety, Process… (a label)"), ("explanation", False, "Shown after the learner answers"),
        ("question_hi, option_a_hi …", False, "The same text in Hindi"), ("question_gu, option_a_gu …", False, "The same text in Gujarati"),
    ],
}
TITLES = {"modules": "Modules", "steps": "SOP steps", "quiz": "Quiz questions"}


@admin_required
def import_center(request):
    if request.method == "POST":
        kind = request.POST.get("kind")
        upload = request.FILES.get("file")
        replace = request.POST.get("mode") == "replace"
        if kind not in COLUMNS:
            raise Http404
        try:
            if not upload:
                raise ImportError_("Choose a file first.")
            rows = read_table(upload)
            if kind == "modules":
                plant = Plant.objects.filter(pk=request.POST.get("plant") or 0).first()
                created, updated = import_modules(rows, default_plant=plant)
                messages.success(request, f"Done — {created} module(s) added, {updated} updated. New modules start as Draft: review them, then publish.")
                n = created + updated
            elif kind == "steps":
                n, mods = import_steps_bulk(rows, replace=replace)
                messages.success(request, f"Done — {n} step(s) {'replaced' if replace else 'added'} across {mods} module(s).")
            else:
                n, mods = import_quiz_bulk(rows, replace=replace)
                messages.success(request, f"Done — {n} question(s) {'replaced' if replace else 'added'} across {mods} module(s).")
            audit(request, f"import.{kind}", None, count=n)
        except (ImportError_, TableError) as exc:
            messages.error(request, str(exc))
        return redirect("panel:import")
    cards = [{"kind": k, "title": TITLES[k], "cols": COLUMNS[k]} for k in ("modules", "steps", "quiz")]
    return render_panel(request, "panel/import.html", page_title="Import from Excel", cards=cards, plants=Plant.objects.all(), module_count=Module.objects.count())


def _sample(kind):
    mods = list(Module.objects.order_by("plant__order", "order")[:2])
    m1 = mods[0].slug if mods else "vmpl_melt_cast"
    m2 = mods[1].slug if len(mods) > 1 else m1
    plant = Plant.objects.order_by("order").first()
    pname = plant.name if plant else "VMPL P1"
    if kind == "modules":
        head = ["title", "department", "plant", "category", "summary", "overview", "objectives", "est_minutes", "library", "status", "title_hi", "summary_hi"]
        rows = [["Homogenizing", "Production", pname, "Homogenizing", "Heating and cooling billets before extrusion.", "Covers the furnace cycle and cooling.",
                 "Explain the cycle|Check temperatures|Record the log", 25, "production", "draft", "होमोजेनाइज़िंग", "एक्सट्रूज़न से पहले बिलेट को गर्म और ठंडा करना।"],
                ["Preventive Maintenance", "Maintenance", pname, "Preventive Maintenance", "Planned servicing of machines.", "", "", 15, "department", "draft", "", ""]]
    elif kind == "steps":
        head = ["module", "step", "text", "text_hi", "text_gu"]
        rows = [[m1, 1, "Inspect the furnace internally after cleaning.", "सफ़ाई के बाद फ़र्नेस का आंतरिक निरीक्षण करें।", "સફાઈ પછી ફર્નેસનું આંતરિક નિરીક્ષણ કરો."], [m1, 2, "Check the cooling water flow.", "", ""],
                [m2, 1, "Wear all PPE before entering the shop floor.", "", ""]]
    else:
        head = ["module", "question", "option_a", "option_b", "option_c", "option_d", "correct", "kind", "explanation", "question_hi", "option_a_hi", "option_b_hi", "option_c_hi", "option_d_hi"]
        rows = [[m1, "What should be checked first?", "Gas pressure", "Furnace interior", "Billet speed", "Water temperature", "B", "Diagnostic", "Always inspect before starting.",
                 "सबसे पहले क्या जाँचना चाहिए?", "गैस दाब", "फ़र्नेस का आंतरिक भाग", "बिलेट की गति", "पानी का तापमान"]]
    notes = [("Column", "Needed?", "What to write")] + [(c, "Yes" if req else "Optional", d) for c, req, d in COLUMNS[kind]]
    return head, rows, notes


@admin_required
def import_sample(request, kind, ext):
    if kind not in COLUMNS or ext not in ("xlsx", "csv"):
        raise Http404
    head, rows, notes = _sample(kind)
    fname = f"sample_{kind}.{ext}"
    if ext == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        w.writerows(rows)
        resp = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    else:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = TITLES[kind]
        ws.append(head)
        for r in rows:
            ws.append(r)
        for i, h in enumerate(head, start=1):
            c = ws.cell(row=1, column=i)
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="C8102E")
            ws.column_dimensions[get_column_letter(i)].width = max(14, min(46, max(len(str(x[i - 1])) for x in rows) // 2 + 12))
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
        how = wb.create_sheet("How to fill")
        for r in notes:
            how.append(r)
        for c in how[1]:
            c.font = Font(bold=True)
        how.column_dimensions["A"].width, how.column_dimensions["B"].width, how.column_dimensions["C"].width = 34, 12, 90
        how.append(()); how.append(("Delete the example rows, keep the first row (the column names), then upload this file.",))
        out = io.BytesIO()
        wb.save(out)
        resp = HttpResponse(out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    return resp
