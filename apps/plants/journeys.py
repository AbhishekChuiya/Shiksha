"""The "plant journey": the processes a learner walks through in a plant, in the order material flows.

Admins can change each plant's list under Plants → Plant journey. The lists below are only the starting point for plants whose
name begins with VMPL, VGPL or VRPL."""
import re

STAGES = {
    "VMPL": ["Plant Introduction", "Gate Entry", "Lab Testing", "RMS", "Extrusion", "Ageing", "Shot Blasting", "Anodizing", "Machine Shop", "Packaging", "Dispatch"],
    "VGPL": ["Plant Induction", "Gate Entry", "Lab Testing", "RMS (Raw Material Store)", "Batch House", "Furnace", "Rolling", "Annealing", "Cutting", "Deep Process", "Packing", "Dispatch"],
    "VRPL": ["Plant Introduction", "Gate Entry", "Lab Testing", "RMS", "Mixing", "Extrusion", "Winding and Packing", "Dispatch"],
}

# Other words that mean the same stage, so "Plant Induction" finds a module called "Plant Introduction" (and so on).
ALIASES = {
    "plant introduction": ["plant introduction", "plant induction", "introduction", "induction"],
    "plant induction": ["plant induction", "plant introduction", "induction", "introduction"],
    "rms": ["rms", "raw material store", "raw material"],
    "rms raw material store": ["rms", "raw material store", "raw material"],
    "lab testing": ["lab testing", "laboratory", "lab"],
    "gate entry": ["gate entry", "gate"],
    "machine shop": ["machine shop", "machining"],
    "packaging": ["packaging", "packing"],
    "packing": ["packing", "packaging"],
    "winding and packing": ["winding and packing", "winding", "packing"],
    "shot blasting": ["shot blasting", "blasting"],
}

ICONS = [
    ("introduction", "graduation"), ("induction", "graduation"), ("gate", "door"), ("lab", "flask"), ("rms", "warehouse"), ("raw material", "warehouse"),
    ("batch", "scale"), ("furnace", "flame"), ("melt", "flame"), ("homogeniz", "flame"), ("rolling", "cylinder"), ("anneal", "thermometer"), ("ageing", "thermometer"),
    ("cutting", "scissors"), ("deep process", "layers"), ("packag", "package"), ("packing", "package"), ("winding", "package"), ("dispatch", "truck"),
    ("extrusion", "layers"), ("blasting", "bolt"), ("machin", "cog"), ("anodiz", "flask"), ("mixing", "blend"), ("maintenance", "wrench"), ("handling", "truck"),
    ("inspection", "check-circle"), ("complaint", "alert"),
]


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def icon_for(text):
    n = norm(text)
    for needle, name in ICONS:
        if needle in n:
            return name
    return "layers"


def _has_word(hay, needle):
    return f" {needle} " in f" {hay} "


def find_module(stage_name, modules):
    """The best module for a stage name: exact title, then a title containing the name (or an alias), then category / process."""
    n = norm(stage_name)
    needles = ALIASES.get(n, [n])
    for field in ("title", "category", "process"):
        for needle in needles:
            for m in modules:
                hay = norm(m.process.name if field == "process" and m.process_id else getattr(m, field, "") if field != "process" else "")
                if hay and (hay == needle or _has_word(hay, needle)):
                    return m
    return None
