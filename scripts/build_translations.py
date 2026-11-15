"""Write locale/{hi,gu}/LC_MESSAGES/django.po + .mo from scripts/translations_hi.py and translations_gu.py.

Run:  python scripts/build_translations.py
(English is the source language, so only Hindi and Gujarati need catalogs.)
"""
from pathlib import Path

import polib

from translations_gu import GU, GU_PLURALS, MONTHS_GU
from translations_hi import HI, HI_PLURALS, MONTHS_HI

BASE = Path(__file__).resolve().parent.parent / "locale"


def build():
    for lang, singles, plurals, months in (("hi", HI, HI_PLURALS, MONTHS_HI), ("gu", GU, GU_PLURALS, MONTHS_GU)):
        po = polib.POFile()
        po.metadata = {"Content-Type": "text/plain; charset=UTF-8", "Language": lang,
                       "Plural-Forms": "nplurals=2; plural=(n != 1);"}
        for msgid, msgstr in singles.items():
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
        for msgid, msgstr in months.items():
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
        for msgid, (plural, forms) in plurals.items():
            po.append(polib.POEntry(msgid=msgid, msgid_plural=plural, msgstr_plural={0: forms[0], 1: forms[1]}))
        d = BASE / lang / "LC_MESSAGES"
        d.mkdir(parents=True, exist_ok=True)
        po.save(str(d / "django.po"))
        po.save_as_mofile(str(d / "django.mo"))
        print(f"{lang}: {len(po)} entries")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    build()
