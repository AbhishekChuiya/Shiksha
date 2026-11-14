"""Collect every translatable UI string from templates and Python code (no gettext tools needed).

Used by build_translations.py and by tests/test_i18n.py (which fails if a string has no Hindi).
Returns a dict {msgid: msgid_plural_or_None}.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STR = r'''(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')'''

def _unq(a, b):
    return (a if a is not None else b).replace('\\"', '"').replace("\\'", "'")

def _vars(body):
    """{{ x }} / {{ x.y }} -> %(x)s ; returns text."""
    out = re.sub(r"\{\{\s*([\w.]+)\s*(?:\|[^}]*)?\}\}", lambda m: "%(" + m.group(1).split(".")[-1] + ")s", body)
    return re.sub(r"%(?!\()", "%%", out)          # a literal % is written %% in a Django msgid

def from_templates():
    out = {}
    for p in (ROOT / "templates").rglob("*.*"):
        if p.suffix not in (".html", ".txt"):
            continue
        s = p.read_text(encoding="utf-8")
        for m in re.finditer(r"\{%\s*(?:translate|trans)\s+" + STR + r"[^%]*%\}", s):
            out[_unq(*m.groups())] = None
        for m in re.finditer(r"_\(" + STR + r"\)", s):          # {{ x|default:_("..") }} style
            out[_unq(*m.groups())] = None
        for m in re.finditer(r"\{%\s*blocktranslate([^%]*)%\}(.*?)\{%\s*endblocktranslate\s*%\}", s, re.S):
            body = m.group(2)
            if "{% plural %}" in body:
                a, b = body.split("{% plural %}")
                out[_vars(a.strip())] = _vars(b.strip())
            else:
                out[_vars(body.strip())] = None
    return out

def from_python():
    out = {}
    for p in list((ROOT / "apps").rglob("*.py")) + [ROOT / "config" / "settings.py"]:
        if "migrations" in p.parts or "management" in p.parts:
            continue
        s = p.read_text(encoding="utf-8")
        for m in re.finditer(r"(?<![\w.])(?:_|gettext|gettext_lazy)\(\s*" + STR, s):
            out[_unq(*m.groups())] = None
    return out

def all_strings():
    d = {}
    d.update(from_python()); d.update(from_templates())
    # strings passed through {% trans variable %} / dynamic keys
    for extra in ("Good morning", "Good afternoon", "Good evening"):
        d.setdefault(extra, None)
    return {k: v for k, v in d.items() if k.strip()}

if __name__ == "__main__":
    s = all_strings()
    print(len(s), "strings")
