"""Load demo plants, modules and users so the app can be explored end to end.

    python manage.py seed_demo

Only the texts visible in the current Shiksha screenshots are real; every
other step is marked [DEMO] and must be replaced with approved SOP content
(use `import_steps` / `import_quiz`).
"""
import io

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.learning.models import Module, SafetyGuideline, SOPStep
from apps.plants.models import Department, Plant, Process
from apps.quizzes.models import Choice, Question, Quiz

PLANTS = [
    ("vgpl-1", "VGPL 1"), ("vgpl-2", "VGPL 2"), ("vmpl-p1", "VMPL P1"),
    ("vmpl-p2", "VMPL P2"), ("vrpl", "VRPL"),
]

VMPL_ABOUT = """Vishakha Metals Private Limited (VMPL), a part of the Vishakha Group, is one of India's leading manufacturers of aluminium frames for components for solar photovoltaic (PV) modules. The company operates a fully integrated aluminium frame manufacturing facility dedicated to the solar industry, offering end-to-end capabilities from aluminium extrusion to fabrication and finishing with inhouse anodizing facility. Located at Mundra, Gujarat, the facility currently supports solar module installations with a total energy capacity of 3.5 GW, with the production capacity expected to increase to 10 GW in the near future.

Engineered using 6063 and 6005 aluminium alloys, these frames offer excellent durability, corrosion resistance, dimensional stability, and long service life, ensuring reliable protection and structural integrity of solar modules.

VMPL's integrated manufacturing capabilities enable consistent control over critical parameters such as dimensional accuracy, surface finish, mechanical strength, corrosion resistance, and profile quality."""

# (category, department, summary, step count)
DEPARTMENTS = ["Production", "QC", "Maintenance"]

VMPL_MODULES = [
    ("Melt & Cast", "Production", "Melting and casting is where production starts. Ingots and aluminium scrap used as raw material are melted and cast into billets.", 31),
    ("Homogenizing", "Production", "This SOP covers the homogenizing and cooling process for aluminium casting logs prior to extrusion.", 19),
    ("Extrusion", "Production", "This module covers the aluminium profile extrusion process at VMPL, one of the foundational stages in aluminium profile manufacturing.", 31),
    ("Ageing", "Production", "This module covers the aluminium profile ageing furnace process, which follows directly after extrusion.", 29),
    ("Anodizing", "Production", "Surface finishing of aluminium profiles in the in-house anodizing facility.", 23),
    ("Machining — Long Frame", "Production", "Auto machining of long frame profiles.", 11),
    ("Machining — Short Frame", "Production", "Auto machining of short frame profiles.", 11),
    ("Incoming Inspection", "QC", "Inspection of incoming raw material before it is released to production.", 8),
    ("Customer Complaint", "QC", "Handling and closing customer complaints.", 6),
    ("Material Handling", "Production", "Safe handling and movement of material inside the plant.", 8),
    ("Preventive Maintenance", "Maintenance", "Planned checks and servicing that keep machines running safely.", 10),
    ("Hydraulic System Maintenance", "Maintenance", "Inspecting, topping up and troubleshooting hydraulic systems.", 9),
    ("Electrical Panel Safety", "Maintenance", "Safe working around electrical panels, with lock-out / tag-out.", 8),
]

ENV_GUIDELINES = [
    "Report EVERY near-miss incident immediately to your supervisor — do not underestimate it.",
    "Fill all record sheets and logbooks completely and accurately — no blank entries.",
    "Never deviate from Standard Operating Window (SOW) parameters without approval from your HOD.",
    "Ensure no spillage or leakage of liquids. Store all liquids in secondary containments.",
    "Segregate waste at source — dispose of acid waste, scrap, and process waste through the environmental department procedure.",
    "Switch off all lights, equipment, and energy systems when not required.",
]
SAFETY_GUIDELINES = [
    "[DEMO] Wear all PPE required for your work area before entering the shop floor.",
    "[DEMO] Follow LOTO (lock-out / tag-out) before any cleaning, maintenance or repair.",
    "[DEMO] Do not operate any equipment you have not been trained and authorised for.",
]

COLOURED_GUIDELINES = [
    ("ppe", "Safety helmet", "सेफ्टी हेलमेट"), ("ppe", "Safety shoes", "सेफ्टी जूते"), ("ppe", "Hand gloves", "हाथ के दस्ताने"),
    ("ppe", "Safety goggles", "सेफ्टी चश्मा"), ("ppe", "Apron", "एप्रन"),
    ("hazards", "Burns from hot billets and die components.", "गर्म बिलेट और डाई के पुर्ज़ों से जलने का खतरा।"),
    ("hazards", "High-pressure hydraulic hazards (oil leaks, pump pressure).", "उच्च दाब हाइड्रॉलिक खतरे (तेल रिसाव, पंप दाब)।"),
    ("hazards", "Crush / pinch hazards near moving parts.", "चलते हुए पुर्ज़ों के पास कुचलने/दबने का खतरा।"),
    ("practices", "Ear protection near pumps and compressor.", "पंप और कंप्रेसर के पास कान की सुरक्षा पहनें।"),
    ("dos", "Do complete all pre-operation checks before starting the press.", "प्रेस चालू करने से पहले सभी जाँच पूरी करें।"),
    ("dos", "Do keep walkways clear and report any oil leak at once.", "रास्ते साफ रखें और तेल रिसाव की तुरंत सूचना दें।"),
    ("donts", "Don't operate the press if you hear abnormal sounds.", "असामान्य आवाज़ आने पर प्रेस न चलाएँ।"),
    ("donts", "Don't leave the container heater unchecked at the end of the shift.", "शिफ्ट के अंत में कंटेनर हीटर को बिना जाँचे न छोड़ें।"),
]


class Command(BaseCommand):
    help = "Seed demo plants, VMPL P1 modules, a quiz and the test accounts."

    @transaction.atomic
    def handle(self, *args, **opts):
        plants = {}
        for i, (code, name) in enumerate(PLANTS):
            plants[code], _ = Plant.objects.update_or_create(
                code=code, defaults={"name": name, "order": i})
        vmpl = plants["vmpl-p1"]
        vmpl.company = "Vishakha Metals Private Limited"
        vmpl.tagline = "Offering end-to-end capabilities from aluminium extrusion to fabrication and finishing with inhouse anodizing facility"
        vmpl.location = "Mundra, Gujarat"
        vmpl.about = VMPL_ABOUT
        vmpl.save()

        depts = {n: Department.objects.get_or_create(plant=vmpl, name=n, defaults={"order": i})[0]
                 for i, n in enumerate(DEPARTMENTS)}

        for i, t in enumerate(ENV_GUIDELINES):
            SafetyGuideline.objects.get_or_create(plant=vmpl, module=None, section="environment",
                                                  text=t, defaults={"order": i})
        for i, t in enumerate(SAFETY_GUIDELINES):
            SafetyGuideline.objects.get_or_create(plant=vmpl, module=None, section="safety",
                                                  text=t, defaults={"order": i})

        for i, (sec, t, hi) in enumerate(COLOURED_GUIDELINES):
            SafetyGuideline.objects.get_or_create(plant=vmpl, module=None, section=sec, text=t, defaults={"order": i, "text_hi": hi})
        call_command("seed_knowledge", stdout=io.StringIO())

        for order, (cat, dept, summary, n_steps) in enumerate(VMPL_MODULES):
            slug = "vmpl_" + cat.lower().replace(" — ", "_").replace(" & ", "_").replace(" ", "_")
            process, _ = Process.objects.get_or_create(department=depts[dept], name=cat)
            m, created = Module.objects.update_or_create(slug=slug, defaults=dict(
                plant=vmpl, department=depts[dept], process=process, category=cat,
                title=cat, summary=summary, overview=summary, est_minutes=max(10, n_steps),
                library=Module.Library.PRODUCTION if dept == "Production" else Module.Library.DEPARTMENT, order=order))
            if created or not m.steps.exists():
                for k in range(1, n_steps + 1):
                    SOPStep.objects.create(module=m, number=k,
                                           text=f"[DEMO] {cat} — step {k}. Replace with approved SOP text.")

        melt = Module.objects.get(slug="vmpl_melt_cast")
        melt.objectives = "Understand cold furnace start-up checks\nFollow the casting sequence safely\nEnsure cast billets are ready for the next process"
        melt.save()
        SOPStep.objects.filter(module=melt, number=1).update(
            text="For a cold furnace start-up, inspect the furnace internally after cleaning and repair "
                 "activities. Ensure the furnace is ready for operation before starting the heating process.")
        SOPStep.objects.filter(module=melt, number=31).update(
            text="Complete the casting operation and ensure the cast billets are properly cooled and "
                 "ready for the next process.")

        quiz, _ = Quiz.objects.get_or_create(module=melt, defaults={"pass_percent": 80})
        if not quiz.questions.exists():
            self._q(quiz, "Before starting heating on a cold furnace, what should be checked first after cleaning and repair?",
                    ["Only the gas pressure setting", "The furnace interior and readiness for operation",
                     "The billet casting machine speed", "The cooling water temperature"], 1)
            self._q(quiz, "What must be ensured when the casting operation is complete?",
                    ["The furnace is switched off immediately", "Cast billets are properly cooled and ready for the next process",
                     "The scrap bin is emptied", "The shift log is signed"], 1)

        call_command("seed_hindi", stdout=self.stdout)
        call_command("create_test_users", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Seeded demo plants, modules and quiz."))

    @staticmethod
    def _q(quiz, text, options, correct):
        q = Question.objects.create(quiz=quiz, text=text, order=quiz.questions.count())
        for i, o in enumerate(options):
            Choice.objects.create(question=q, text=o, is_correct=(i == correct), order=i)
