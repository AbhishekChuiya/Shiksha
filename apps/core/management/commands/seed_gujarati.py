"""Fill Gujarati (*_gu) fields for the demo content. Safe to run any time:

* only fields that are still EMPTY are filled — nothing your team typed is ever overwritten;
* content that does not match a known demo item is left alone.

    python manage.py seed_gujarati
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.knowledge.models import KBCategory, KBItem
from apps.learning.models import Module, SafetyGuideline, SOPStep
from apps.plants.models import Department, Plant, Process
from apps.quizzes.models import Question

# English module title -> (Gujarati title, Gujarati summary)
MODULES = {
    "Melt & Cast": ("મેલ્ટ અને કાસ્ટ (ગાળવું અને ઢાળવું)", "ગાળવું અને ઢાળવું એ પ્રોડક્શનની શરૂઆત છે. ઇન્ગોટ અને એલ્યુમિનિયમ સ્ક્રેપને ગાળીને બિલેટ બનાવવામાં આવે છે."),
    "Homogenizing": ("હોમોજેનાઇઝિંગ", "એક્સ્ટ્રુઝન પહેલાં એલ્યુમિનિયમ કાસ્ટિંગ લૉગને ગરમ અને ઠંડા કરવાની પ્રક્રિયા."),
    "Extrusion": ("એક્સ્ટ્રુઝન", "VMPL માં એલ્યુમિનિયમ પ્રોફાઇલ એક્સ્ટ્રુઝન પ્રક્રિયા — એલ્યુમિનિયમ ઉત્પાદનના પાયાના તબક્કાઓમાંનો એક."),
    "Ageing": ("એજિંગ", "એલ્યુમિનિયમ પ્રોફાઇલ એજિંગ ફર્નેસ પ્રક્રિયા, જે એક્સ્ટ્રુઝન પછી તરત આવે છે."),
    "Anodizing": ("એનોડાઇઝિંગ", "ઇન-હાઉસ એનોડાઇઝિંગ સુવિધામાં એલ્યુમિનિયમ પ્રોફાઇલની સપાટી ફિનિશિંગ."),
    "Machining — Long Frame": ("મશીનિંગ — લાંબી ફ્રેમ", "લાંબી ફ્રેમ પ્રોફાઇલની ઑટો મશીનિંગ."),
    "Machining — Short Frame": ("મશીનિંગ — ટૂંકી ફ્રેમ", "ટૂંકી ફ્રેમ પ્રોફાઇલની ઑટો મશીનિંગ."),
    "Incoming Inspection": ("ઇનકમિંગ ઇન્સ્પેક્શન", "પ્રોડક્શનમાં મોકલતા પહેલાં આવનાર કાચા માલનું નિરીક્ષણ."),
    "Customer Complaint": ("ગ્રાહક ફરિયાદ", "ગ્રાહક ફરિયાદોનું નિરાકરણ અને સમાપન."),
    "Material Handling": ("મટીરિયલ હેન્ડલિંગ", "પ્લાન્ટની અંદર સામગ્રીનું સુરક્ષિત સંચાલન અને હેરફેર."),
    "Preventive Maintenance": ("પ્રિવેન્ટિવ મેન્ટેનન્સ", "મશીનો સુરક્ષિત ચાલે તે માટે આયોજિત તપાસ અને સર્વિસિંગ."),
    "Hydraulic System Maintenance": ("હાઇડ્રોલિક સિસ્ટમ મેન્ટેનન્સ", "હાઇડ્રોલિક સિસ્ટમનું નિરીક્ષણ, ઓઇલ ભરવું અને સમસ્યા નિવારણ."),
    "Electrical Panel Safety": ("ઇલેક્ટ્રિકલ પેનલ સુરક્ષા", "લૉક-આઉટ / ટૅગ-આઉટ સાથે ઇલેક્ટ્રિકલ પેનલ પાસે સુરક્ષિત કાર્ય."),
}
DEPARTMENTS = {"Production": "પ્રોડક્શન", "QC": "ક્યુસી (ગુણવત્તા નિયંત્રણ)", "Maintenance": "મેન્ટેનન્સ", "Quality": "ગુણવત્તા"}

GUIDELINES = {
    "Report EVERY near-miss incident immediately to your supervisor — do not underestimate it.": "દરેક નજીકની ચૂકની જાણ તરત જ તમારા સુપરવાઇઝરને કરો — તેને હળવાશથી ન લો.",
    "Fill all record sheets and logbooks completely and accurately — no blank entries.": "બધી રેકોર્ડ શીટ અને લૉગબુક સંપૂર્ણ અને સાચી ભરો — કોઈ એન્ટ્રી ખાલી ન રાખો.",
    "Never deviate from Standard Operating Window (SOW) parameters without approval from your HOD.": "તમારા એચઓડીની મંજૂરી વિના સ્ટાન્ડર્ડ ઑપરેટિંગ વિન્ડો (SOW) ના પરિમાણોથી ક્યારેય વિચલિત ન થાઓ.",
    "Ensure no spillage or leakage of liquids. Store all liquids in secondary containments.": "કોઈ પ્રવાહી ઢોળાય કે લીક ન થાય તેની ખાતરી કરો. બધા પ્રવાહી સેકન્ડરી કન્ટેઇનમેન્ટમાં રાખો.",
    "Segregate waste at source — dispose of acid waste, scrap, and process waste through the environmental department procedure.": "કચરો સ્રોત પર જ અલગ કરો — એસિડ કચરો, સ્ક્રેપ અને પ્રક્રિયાનો કચરો પર્યાવરણ વિભાગની પદ્ધતિથી નિકાલ કરો.",
    "Switch off all lights, equipment, and energy systems when not required.": "જરૂર ન હોય ત્યારે બધી લાઇટ, સાધનો અને ઊર્જા પ્રણાલીઓ બંધ કરો.",
    "[DEMO] Wear all PPE required for your work area before entering the shop floor.": "[ડેમો] શૉપ ફ્લોરમાં પ્રવેશતા પહેલાં તમારા કાર્ય વિસ્તાર માટે જરૂરી બધા પીપીઈ પહેરો.",
    "[DEMO] Follow LOTO (lock-out / tag-out) before any cleaning, maintenance or repair.": "[ડેમો] કોઈપણ સફાઈ, જાળવણી કે સમારકામ પહેલાં LOTO (લૉક-આઉટ / ટૅગ-આઉટ) નું પાલન કરો.",
    "[DEMO] Do not operate any equipment you have not been trained and authorised for.": "[ડેમો] જે સાધનની તાલીમ અને અધિકાર તમને મળ્યા નથી તે ચલાવશો નહીં.",
    "Safety helmet": "સેફ્ટી હેલ્મેટ", "Safety shoes": "સેફ્ટી શૂઝ", "Hand gloves": "હાથના મોજા", "Safety goggles": "સેફ્ટી ચશ્માં", "Apron": "એપ્રન",
    "Burns from hot billets and die components.": "ગરમ બિલેટ અને ડાઇના ભાગોથી દાઝવાનું જોખમ.",
    "High-pressure hydraulic hazards (oil leaks, pump pressure).": "ઊંચા દબાણના હાઇડ્રોલિક જોખમો (ઓઇલ લીક, પંપનું દબાણ).",
    "Crush / pinch hazards near moving parts.": "ફરતા ભાગો પાસે કચડાવા/ભીંસાવાનું જોખમ.",
    "Ear protection near pumps and compressor.": "પંપ અને કોમ્પ્રેસર પાસે કાનની સુરક્ષા પહેરો.",
    "Do complete all pre-operation checks before starting the press.": "પ્રેસ શરૂ કરતા પહેલાં બધી પૂર્વ-તપાસ પૂર્ણ કરો.",
    "Do keep walkways clear and report any oil leak at once.": "રસ્તા ખુલ્લા રાખો અને ઓઇલ લીકની તરત જાણ કરો.",
    "Don't operate the press if you hear abnormal sounds.": "અસામાન્ય અવાજ સંભળાય તો પ્રેસ ચલાવશો નહીં.",
    "Don't leave the container heater unchecked at the end of the shift.": "શિફ્ટના અંતે કન્ટેઇનર હીટરને તપાસ્યા વિના ન છોડો.",
}
QUESTIONS = {
    "Before starting heating on a cold furnace, what should be checked first after cleaning and repair?": (
        "ઠંડી ફર્નેસ પર હીટિંગ શરૂ કરતા પહેલાં, સફાઈ અને સમારકામ પછી સૌથી પહેલા શું તપાસવું જોઈએ?",
        {"Only the gas pressure setting": "ફક્ત ગૅસ પ્રેશર સેટિંગ", "The furnace interior and readiness for operation": "ફર્નેસનો અંદરનો ભાગ અને સંચાલન માટે તેની તૈયારી",
         "The billet casting machine speed": "બિલેટ કાસ્ટિંગ મશીનની ગતિ", "The cooling water temperature": "કૂલિંગ વૉટરનું તાપમાન"}),
    "What must be ensured when the casting operation is complete?": (
        "કાસ્ટિંગ કામગીરી પૂર્ણ થાય ત્યારે શું સુનિશ્ચિત કરવું જોઈએ?",
        {"The furnace is switched off immediately": "ફર્નેસ તરત બંધ કરી દેવામાં આવી હોય",
         "Cast billets are properly cooled and ready for the next process": "ઢાળેલા બિલેટ બરાબર ઠંડા થયા હોય અને આગલી પ્રક્રિયા માટે તૈયાર હોય",
         "The scrap bin is emptied": "સ્ક્રેપ બિન ખાલી કરવામાં આવી હોય", "The shift log is signed": "શિફ્ટ લૉગ પર સહી થઈ ગઈ હોય"}),
}
KB_CATEGORIES = {"Safety & compliance": "સુરક્ષા અને અનુપાલન", "Machine manuals": "મશીન મેન્યુઅલ", "Forms & formats": "ફોર્મ અને ફોર્મેટ", "Quality standards": "ગુણવત્તા ધોરણો"}
KB_ITEMS = {"Emergency evacuation plan": "કટોકટી ખાલી કરવાની યોજના", "Extrusion press operator manual": "એક્સ્ટ્રુઝન પ્રેસ ઑપરેટર મેન્યુઅલ",
            "Shift handover format": "શિફ્ટ હૅન્ડઓવર ફોર્મેટ", "Fire safety basics (video)": "અગ્નિ સુરક્ષાની મૂળભૂત બાબતો (વિડિઓ)"}
ABOUT_GU = (
    "વિશાખા મેટલ્સ પ્રાઇવેટ લિમિટેડ (VMPL), વિશાખા ગ્રુપનો એક ભાગ, સોલાર ફોટોવોલ્ટેઇક (PV) મોડ્યુલના ઘટકો માટે એલ્યુમિનિયમ ફ્રેમના ભારતના અગ્રણી ઉત્પાદકોમાંનું એક છે. "
    "કંપની સોલાર ઉદ્યોગને સમર્પિત, સંપૂર્ણ સંકલિત એલ્યુમિનિયમ ફ્રેમ ઉત્પાદન સુવિધા ચલાવે છે, જે એલ્યુમિનિયમ એક્સ્ટ્રુઝનથી લઈને ફેબ્રિકેશન અને ઇન-હાઉસ એનોડાઇઝિંગ સુવિધા સાથે ફિનિશિંગ સુધીની સંપૂર્ણ ક્ષમતાઓ આપે છે. "
    "મુન્દ્રા, ગુજરાતમાં આવેલી આ સુવિધા હાલમાં 3.5 GW ની કુલ ઊર્જા ક્ષમતા સાથે સોલાર મોડ્યુલ સ્થાપનોને ટેકો આપે છે, અને નજીકના ભવિષ્યમાં પ્રોડક્શન ક્ષમતા વધીને 10 GW થવાની અપેક્ષા છે.\n\n"
    "6063 અને 6005 એલ્યુમિનિયમ મિશ્રધાતુઓમાંથી બનેલી આ ફ્રેમ ઉત્તમ ટકાઉપણું, કાટ સામે પ્રતિકાર, પરિમાણીય સ્થિરતા અને લાંબું આયુષ્ય આપે છે, જેથી સોલાર મોડ્યુલનું વિશ્વસનીય રક્ષણ અને માળખાકીય મજબૂતી જળવાઈ રહે છે.\n\n"
    "VMPL ની સંકલિત ઉત્પાદન ક્ષમતાઓ પરિમાણીય ચોકસાઈ, સપાટીની ફિનિશ, યાંત્રિક મજબૂતી, કાટ પ્રતિકાર અને પ્રોફાઇલની ગુણવત્તા જેવા મહત્વપૂર્ણ પરિમાણો પર સતત નિયંત્રણ શક્ય બનાવે છે."
)
OBJECTIVES = ("Understand cold furnace start-up checks\nFollow the casting sequence safely\nEnsure cast billets are ready for the next process",
              "ઠંડી ફર્નેસ શરૂ કરવાની તપાસ સમજો\nકાસ્ટિંગનો ક્રમ સુરક્ષિત રીતે અનુસરો\nખાતરી કરો કે ઢાળેલા બિલેટ આગલી પ્રક્રિયા માટે તૈયાર છે")
KB_DESCRIPTIONS = {
    "Where to go and what to do when the alarm sounds.": "એલાર્મ વાગે ત્યારે ક્યાં જવું અને શું કરવું.",
    "Controls, start-up and shut-down.": "કંટ્રોલ, શરૂ કરવું અને બંધ કરવું.",
    "Fill in at the end of every shift.": "દરેક શિફ્ટના અંતે ભરો.",
}
PLANT = {"about_gu": ABOUT_GU, "location_gu": "મુન્દ્રા, ગુજરાત", "tagline_gu": "એલ્યુમિનિયમ એક્સ્ટ્રુઝનથી લઈને ફેબ્રિકેશન અને ઇન-હાઉસ એનોડાઇઝિંગ સુવિધા સુધીની સંપૂર્ણ ક્ષમતાઓ."}


def fill(obj, field, value):
    """Set obj.<field> only when it is empty. Returns 1 if changed."""
    if value and not getattr(obj, field):
        setattr(obj, field, value)
        return 1
    return 0


class Command(BaseCommand):
    help = "Fill empty Gujarati fields for the demo content (never overwrites existing Gujarati)."

    def handle(self, *args, **opts):
        n = 0
        for plant in Plant.objects.filter(Q(code="vmpl-p1") | Q(about__startswith="Vishakha Metals Private Limited")):
            for f, v in PLANT.items():
                n += fill(plant, f, v)
            plant.save()
        for d in Department.objects.all():
            if fill(d, "name_gu", DEPARTMENTS.get(d.name)):
                d.save(); n += 1
        for m in Module.objects.all():
            hit = MODULES.get(m.title)
            if not hit:
                continue
            changed = fill(m, "title_gu", hit[0]) + fill(m, "summary_gu", hit[1]) + fill(m, "category_gu", hit[0])
            if m.overview == m.summary:
                changed += fill(m, "overview_gu", hit[1])
            if m.slug == "vmpl_melt_cast" and m.objectives == OBJECTIVES[0]:
                changed += fill(m, "objectives_gu", OBJECTIVES[1])
            if changed:
                m.save(); n += changed
            for pr in Process.objects.filter(name=m.category, name_gu=""):
                pr.name_gu = hit[0]; pr.save(update_fields=["name_gu"]); n += 1
            for step in m.steps.filter(text_gu=""):
                if step.text.startswith("[DEMO]"):
                    step.text_gu = f"[ડેમો] {hit[0]} — પગલું {step.number}. તેને મંજૂર એસઓપી લખાણથી બદલો."
                    step.save(update_fields=["text_gu"]); n += 1
        for g in SafetyGuideline.objects.filter(text_gu=""):
            if GUIDELINES.get(g.text):
                g.text_gu = GUIDELINES[g.text]; g.save(update_fields=["text_gu"]); n += 1
        for q in Question.objects.filter(text_gu=""):
            hit = QUESTIONS.get(q.text)
            if hit:
                q.text_gu = hit[0]; q.save(update_fields=["text_gu"]); n += 1
                for c in q.choices.filter(text_gu=""):
                    if hit[1].get(c.text):
                        c.text_gu = hit[1][c.text]; c.save(update_fields=["text_gu"]); n += 1
        for c in KBCategory.objects.filter(name_gu=""):
            if KB_CATEGORIES.get(c.name):
                c.name_gu = KB_CATEGORIES[c.name]; c.save(update_fields=["name_gu"]); n += 1
        for i in KBItem.objects.all():
            changed = fill(i, "title_gu", KB_ITEMS.get(i.title)) + fill(i, "description_gu", KB_DESCRIPTIONS.get(i.description))
            if changed:
                i.save(); n += changed
        self.stdout.write(self.style.SUCCESS(f"Gujarati content filled ({n} fields). Existing Gujarati was left untouched."))
