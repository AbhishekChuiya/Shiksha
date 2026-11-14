"""A tiny reusable "list editor": add / remove / reorder rows, upload files, Hindi fields.

One Editor describes one child table (steps, videos, gallery photos, quiz options …).
The page renders it with templates/panel/_editor.html; saving is `editor.parse(...)` then `editor.apply(...)`.
Rows are matched by id, so editing never loses data; rows removed from the page are deleted.
"""
import os
from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.core.images import ImageRejected, optimize_image

FILE_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".mov"}


@dataclass
class F:
    name: str
    label: str
    kind: str = "text"          # text textarea number date select image file radio check
    fk: bool = False            # select that stores a foreign key (value = pk)
    required: bool = False
    hindi: bool = False         # shown inside the collapsible "हिन्दी" group
    choices: list = None        # [(value, label)] for select
    help: str = ""
    placeholder: str = ""
    rows: int = 3
    width: str = ""             # "half" for two-per-line layout


class Editor:
    def __init__(self, key, model, fields, scope, *, title="", noun="item", order_field="order", number_field=None,
                 empty_hint="", add_label=None, max_file_mb=60, pre_save=None, info="", filter=None, ordering=None):
        self.key, self.model, self.fields, self.scope = key, model, fields, scope
        self.filter, self.ordering = filter, ordering
        self.title, self.noun, self.order_field, self.number_field = title, noun, order_field, number_field
        self.empty_hint, self.max_file_mb, self.pre_save, self.info = empty_hint, max_file_mb, pre_save, info
        self.add_label = add_label or f"Add {noun}"

    # ---------------------------------------------------------------- reading
    def _qs(self):
        order = self.ordering or ([self.number_field or self.order_field] if (self.number_field or self.order_field) else [])
        return self.model.objects.filter(**(self.filter if self.filter is not None else self.scope)).order_by(*order, "id")

    def _row_from_obj(self, obj):
        vals, files = {}, {}
        for f in self.fields:
            v = getattr(obj, f.name + "_id", "") if f.fk else getattr(obj, f.name, "")
            if f.kind in ("image", "file"):
                vals[f.name] = ""
                if v:
                    files[f.name] = {"url": v.url, "name": os.path.basename(v.name), "image": f.kind == "image"}
            elif f.kind in ("radio", "check"):
                vals[f.name] = "1" if v else ""
            elif isinstance(v, date):
                vals[f.name] = v.isoformat()
            else:
                vals[f.name] = "" if v is None else str(v)
        return {"uid": f"r{obj.pk}", "id": str(obj.pk), "vals": vals, "files": files, "errors": {}, "error": ""}

    def blank_row(self):
        vals = {f.name: ("" if f.kind != "select" or not f.required or not f.choices else str(f.choices[0][0])) for f in self.fields}
        return {"uid": "__UID__", "id": "", "vals": vals, "files": {}, "errors": {}, "error": ""}

    def rows_from_db(self):
        return [self._row_from_obj(o) for o in self._qs()]

    # ---------------------------------------------------------------- parsing
    def parse(self, post, files):
        """Return (rows, ok). Rows carry per-field errors when not ok."""
        existing = {str(o.pk): o for o in self._qs()}
        uids = [u for u in (post.get(f"{self.key}-order") or "").split(",") if u]
        rows, ok = [], True
        for uid in uids:
            p = f"{self.key}-{uid}-"
            rid = post.get(p + "id") or ""
            obj = existing.get(rid)
            row = {"uid": uid, "id": rid if obj else "", "vals": {}, "files": {}, "errors": {}, "error": "", "uploads": {}, "clears": {}}
            for f in self.fields:
                if f.kind in ("image", "file"):
                    row["vals"][f.name] = ""
                    up = files.get(p + f.name)
                    if up:
                        row["uploads"][f.name] = up
                    row["clears"][f.name] = post.get(p + f.name + "-clear") == "1"
                    cur = getattr(obj, f.name, None) if obj else None
                    if cur and not row["clears"][f.name]:
                        row["files"][f.name] = {"url": cur.url, "name": os.path.basename(cur.name), "image": f.kind == "image"}
                elif f.kind == "radio":
                    row["vals"][f.name] = "1" if post.get(f"{self.key}-{f.name}") == uid else ""
                elif f.kind == "check":
                    row["vals"][f.name] = "1" if post.get(p + f.name) == "1" else ""
                else:
                    row["vals"][f.name] = (post.get(p + f.name) or "").strip()
            blank = (not row["id"] and not row["uploads"]
                     and not any(v for k, v in row["vals"].items() if self._kind(k) not in ("radio", "check", "select")))
            if blank:
                continue
            self._validate(row, obj)
            if row["errors"]:
                ok = False
            rows.append(row)
        return rows, ok

    def _kind(self, name):
        return next(f.kind for f in self.fields if f.name == name)

    def _validate(self, row, obj):
        for f in self.fields:
            v = row["vals"].get(f.name, "")
            if f.kind in ("image", "file"):
                up = row["uploads"].get(f.name)
                if up:
                    try:
                        if f.kind == "image":
                            row["uploads"][f.name] = optimize_image(up)
                        else:
                            if os.path.splitext(up.name)[1].lower() not in FILE_EXT:
                                raise ImageRejected("This file type is not allowed (use PDF, Office, image or MP4).")
                            if up.size > self.max_file_mb * 1024 * 1024:
                                raise ImageRejected(f"File is larger than {self.max_file_mb} MB.")
                    except ImageRejected as exc:
                        row["errors"][f.name] = str(exc)
                        row["uploads"].pop(f.name, None)
                elif f.required and f.name not in row["files"]:
                    row["errors"][f.name] = "Please choose a file."
                continue
            if f.required and not v and f.kind not in ("radio", "check"):
                row["errors"][f.name] = "Required."
            elif v and f.kind == "number":
                if not v.isdigit():
                    row["errors"][f.name] = "Enter a whole number."
            elif v and f.kind == "date":
                try:
                    date.fromisoformat(v)
                except ValueError:
                    row["errors"][f.name] = "Enter a valid date."
            elif v and f.kind == "select" and f.choices and v not in {str(c[0]) for c in f.choices}:
                row["errors"][f.name] = "Choose one of the options."

    # ---------------------------------------------------------------- saving
    @transaction.atomic
    def apply(self, rows):
        existing = {str(o.pk): o for o in self._qs()}
        kept, objs = set(), []
        for i, row in enumerate(rows):
            obj = existing.get(row["id"]) or self.model(**self.scope)
            for f in self.fields:
                v = row["vals"].get(f.name, "")
                if f.kind in ("image", "file"):
                    old = getattr(obj, f.name, None)
                    up = row["uploads"].get(f.name)
                    if up:
                        if old:
                            old.delete(save=False)
                        setattr(obj, f.name, up)
                    elif row["clears"].get(f.name) and old:
                        old.delete(save=False)
                        setattr(obj, f.name, "")
                elif f.kind in ("radio", "check"):
                    setattr(obj, f.name, v == "1")
                elif f.fk:
                    setattr(obj, f.name + "_id", int(v) if v else None)
                elif f.kind == "number":
                    setattr(obj, f.name, int(v) if v else None)
                elif f.kind == "date":
                    setattr(obj, f.name, date.fromisoformat(v) if v else None)
                else:
                    setattr(obj, f.name, v)
            if self.number_field:
                setattr(obj, self.number_field, 200_000 + i)   # parking value avoids unique clashes
            elif self.order_field:
                setattr(obj, self.order_field, i)
            if self.pre_save:
                self.pre_save(obj, row)
            obj.save()
            kept.add(str(obj.pk))
            objs.append(obj)
        for pk, obj in existing.items():
            if pk not in kept:
                for f in self.fields:
                    if f.kind in ("image", "file") and getattr(obj, f.name, None):
                        getattr(obj, f.name).delete(save=False)
                obj.delete()
        if self.number_field:
            for i, obj in enumerate(objs):
                setattr(obj, self.number_field, i + 1)
                obj.save(update_fields=[self.number_field])
        return objs

    # ---------------------------------------------------------------- template context
    def context(self, rows=None):
        return {"editor": self, "key": self.key, "title": self.title, "fields": self.fields, "noun": self.noun,
                "rows": self.rows_from_db() if rows is None else rows, "blank": self.blank_row(),
                "empty_hint": self.empty_hint, "add_label": self.add_label, "info": self.info,
                "has_hindi": any(f.hindi for f in self.fields)}
