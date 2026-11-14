"""Write locale/hi/LC_MESSAGES/django.po + .mo from scripts/translations_hi.py.

Run:  python scripts/build_translations.py
(English is the source language, so only Hindi needs a catalog.)
"""
from pathlib import Path

import polib

from translations_hi import HI, HI_PLURALS

BASE = Path(__file__).resolve().parent.parent / "locale"


def build():
    po = polib.POFile()
    po.metadata = {"Content-Type": "text/plain; charset=UTF-8", "Language": "hi",
                   "Plural-Forms": "nplurals=2; plural=(n != 1);"}
    for msgid, msgstr in HI.items():
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    for msgid, (plural, forms) in HI_PLURALS.items():
        po.append(polib.POEntry(msgid=msgid, msgid_plural=plural, msgstr_plural={0: forms[0], 1: forms[1]}))
    d = BASE / "hi" / "LC_MESSAGES"
    d.mkdir(parents=True, exist_ok=True)
    po.save(str(d / "django.po"))
    po.save_as_mofile(str(d / "django.mo"))
    print(f"hi: {len(po)} entries")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    build()
