"""Demo of a full process module (VRPL · Extrusion): purpose, who-does-what, escalation, records and four SOPs.

    python manage.py seed_process_demo        (also runs as part of seed_demo; safe to run again)

All step texts are marked [DEMO]. Replace them in the admin panel (Modules → Extrusion → SOP steps).
"""
import datetime

from django.core.management.base import BaseCommand

from apps.learning.models import Module, ModuleEscalation, ModuleRecord, ModuleRole, ModuleSOP, SafetyGuideline, SOPStep
from apps.plants.models import Department, Plant, Process

OVERVIEW = ("This learning module provides a structured understanding of the Extrusion Line operation for manufacturing EVA/EPE encapsulant films. It covers the complete production cycle—"
            "from work order verification and machine preparation to process start-up, sheet formation, quality monitoring, and QC approval. The module emphasizes adherence to Standard "
            "Operating Procedures (SOPs), process parameters, safety requirements, and quality standards to ensure consistent production and operational excellence.")
OBJECTIVES = ("Verify production requirements and prepare the machine for operation.\nExecute the correct extrusion line start-up sequence.\n"
              "Monitor critical process parameters and product quality.\nPerform in-process quality checks and obtain QC approval.\n"
              "Operate the extrusion line safely while complying with SOPs and Good Manufacturing Practices (GMP).")
PURPOSE = "Maintain production of EVA/POE/EPE encapsulation sheets, adhere to process parameters, and manufacture precisely to customer specification."
ROLES = [("Set the parameters for the job as per Work Order", "Production Operator", "Production Supervisor"),
         ("Cleaning & preparation for extruder start-up", "Production Operator", "Production Supervisor"),
         ("Production as per Work Order", "Production Operator", "Production Supervisor"),
         ("Inspection of process", "Production Operator", "Production Supervisor"),
         ("Sampling of finished rolls", "Production Operator / QC Executive", "Production Supervisor / QC Head")]
ESCALATIONS = [("Process parameter outage", "Escalate immediately"), ("Non-conformance of process", "Escalate immediately")]
RECORDS = [("Process Parameter Sheet for Line 1&2", "VRPL/IMS/QC/F/08"), ("Process Parameter Sheet for Line 3&4", "VRPL/IMS/QC/F/09"),
           ("Process Parameter Sheet for Line 5", "VRPL/IMS/QC/F/09B"), ("Process Parameter Sheet for Line 6", "VRPL/IMS/QC/F/08B"),
           ("Process Parameter Sheet for Line 7", "VRPL/IMS/QC/F/34"), ("Process Parameter Sheet for Line 8", "VRPL/IMS/QC/F/34"),
           ("Daily Production Report", "VRPL/IMS/PRD/F/01"), ("Production NC Report", "VRPL/IMS/PRD/F/02")]
INTRO = ("The EPE Extrusion Line involves high temperatures, rotating equipment, and electrical systems. Adherence to safety procedures is mandatory to protect personnel, equipment, "
         "product quality, and ensure uninterrupted operations.\nNo production target is more important than safety. Every operator is responsible for following SOPs, identifying risks "
         "proactively, and maintaining a safe and compliant working environment.")
SOPS = [("EPE Extrusion Line Startup Procedure (SOP 4)", "VRPL-MANF-SOP-04", "02", datetime.date(2025, 8, 20), 37),
        ("Mixing Batch Transfer to Extrusion Line", "", "", None, 22),
        ("Inspection, Packing & Palletization of Finished Encapsulant Rolls", "", "", None, 27),
        ("Handling, Reprocessing & Disposal of Rejected Material (SOP 8)", "", "", None, 22)]
RULES = [
    ("ppe", ["Apron", "Safety shoes", "Hand gloves", "Safety goggles", "All mandatory PPE", "Safety helmet", "Protective clothing"]),
    ("prestart", ["Before starting the machine, ensure:", "Required PPE is worn.", "Machine guards and emergency stops are functional.",
                  "Water circulation, power supply, and utilities are available.", "No maintenance or LOTO activity is in progress.", "The work area is clean and free from obstructions."]),
    ("hazards", ["Exercise extreme caution around:", "Barrel & Die (High Temperature)", "Rollers & Winder (Entanglement Hazard)", "Rotary Cutter (Cut Hazard)",
                 "Melt Pump (Hot Polymer)", "Electrical Panel (Electric Shock)"]),
    ("practices", ["Ensure all flammable materials are safely stored.", "Operate the machine only as per the approved SOP.", "Maintain all process parameters within specified limits.",
                   "Keep hands away from moving rollers, cutters, and heated surfaces.", "Never bypass safety interlocks or remove guards during operation.",
                   "Report any abnormal sound, vibration, overheating, or process deviation immediately."]),
]


class Command(BaseCommand):
    help = "Create a demo process module (VRPL · Extrusion) with several SOPs, roles, escalation and records."

    def handle(self, *args, **opts):
        plant = Plant.objects.filter(name="VRPL").first() or Plant.objects.order_by("id").last()
        if plant is None:
            self.stdout.write("No plant yet — run seed_demo first."); return
        dept, _ = Department.objects.get_or_create(plant=plant, name="Production", defaults={"order": 0})
        proc, _ = Process.objects.get_or_create(department=dept, name="Extrusion")
        module, created = Module.objects.get_or_create(slug=f"{plant.code}_extrusion_epe".replace("-", "_"), defaults=dict(
            plant=plant, department=dept, process=proc, category="Extrusion", title="Extrusion", summary="EVA/EPE encapsulant film extrusion line — start-up, production and QC.",
            overview=OVERVIEW, objectives=OBJECTIVES, purpose=PURPOSE, est_minutes=71, instructor="Aman Katva", library=Module.Library.PRODUCTION, order=0, status="published"))
        if not created and module.sops.exists():
            self.stdout.write("Process demo already present."); return
        for i, (a, r, ac) in enumerate(ROLES):
            ModuleRole.objects.create(module=module, activity=a, responsible=r, accountable=ac, order=i)
        for i, (s, a) in enumerate(ESCALATIONS):
            ModuleEscalation.objects.create(module=module, situation=s, action=a, order=i)
        for i, (n, c) in enumerate(RECORDS):
            ModuleRecord.objects.create(module=module, name=n, code=c, order=i)
        for i, (title, code, rev, date, n_steps) in enumerate(SOPS):
            sop = ModuleSOP.objects.create(module=module, title=title, code=code, revision=rev, doc_date=date, languages="English + हिंदी" if code else "",
                                           intro=INTRO if i == 0 else "", order=i)
            for k in range(1, n_steps + 1):
                SOPStep.objects.create(module=module, sop=sop, number=k, text=f"[DEMO] {title} — step {k}. Replace with approved SOP text.")
            rules = RULES if i == 0 else RULES[:1][:0] + [("ppe", ["Safety shoes", "Hand gloves", "Safety goggles"])]
            for section, items in rules:
                for j, text in enumerate(items):
                    SafetyGuideline.objects.create(module=module, sop=sop, section=section, text=text, order=j)
        self.stdout.write(self.style.SUCCESS(f"Demo process module ready: {module.title} ({plant.name}) with {len(SOPS)} SOPs."))
