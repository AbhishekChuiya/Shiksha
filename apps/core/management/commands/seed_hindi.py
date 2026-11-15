"""Fill Hindi (*_hi) fields for the demo content. Safe to run any time:

* only fields that are still EMPTY are filled — nothing your team typed is ever overwritten;
* content that does not match a known demo item is left alone.

    python manage.py seed_hindi
"""
from django.core.management.base import BaseCommand

from apps.learning.models import Module, SafetyGuideline, SOPStep
from apps.plants.models import Department, Plant, Process
from apps.quizzes.models import Choice, Question

# English module title  ->  (Hindi title, Hindi summary)
MODULES = {
    "Melt & Cast": ("मेल्ट और कास्ट (पिघलाना और ढलाई)",
                    "पिघलाना और ढलाई वह जगह है जहाँ उत्पादन शुरू होता है। कच्चे माल के रूप में उपयोग होने वाले इनगॉट और एल्युमिनियम स्क्रैप को पिघलाकर बिलेट में ढाला जाता है।"),
    "Homogenizing": ("होमोजेनाइज़िंग",
                     "यह एसओपी एक्सट्रूज़न से पहले एल्युमिनियम कास्टिंग लॉग्स की होमोजेनाइज़िंग और कूलिंग प्रक्रिया को कवर करती है।"),
    "Extrusion": ("एक्सट्रूज़न",
                  "यह मॉड्यूल VMPL में एल्युमिनियम प्रोफ़ाइल एक्सट्रूज़न प्रक्रिया को कवर करता है, जो एल्युमिनियम प्रोफ़ाइल निर्माण के बुनियादी चरणों में से एक है।"),
    "Ageing": ("एजिंग",
               "यह मॉड्यूल एल्युमिनियम प्रोफ़ाइल एजिंग फ़र्नेस प्रक्रिया को कवर करता है, जो एक्सट्रूज़न के तुरंत बाद आती है।"),
    "Anodizing": ("एनोडाइज़िंग", "इन-हाउस एनोडाइज़िंग सुविधा में एल्युमिनियम प्रोफ़ाइल की सतह की फ़िनिशिंग।"),
    "Machining — Long Frame": ("मशीनिंग — लॉन्ग फ़्रेम", "लॉन्ग फ़्रेम प्रोफ़ाइल की ऑटो मशीनिंग।"),
    "Machining — Short Frame": ("मशीनिंग — शॉर्ट फ़्रेम", "शॉर्ट फ़्रेम प्रोफ़ाइल की ऑटो मशीनिंग।"),
    "Incoming Inspection": ("इनकमिंग इंस्पेक्शन", "उत्पादन में भेजने से पहले आने वाले कच्चे माल का निरीक्षण।"),
    "Customer Complaint": ("ग्राहक शिकायत", "ग्राहक शिकायतों का निपटान और समापन।"),
    "Preventive Maintenance": ("प्रिवेंटिव मेंटेनेंस", "मशीनों को सुरक्षित चलाने के लिए नियोजित जाँच और सर्विसिंग।"),
    "Hydraulic System Maintenance": ("हाइड्रोलिक सिस्टम मेंटेनेंस", "हाइड्रोलिक सिस्टम का निरीक्षण, ऑयल भरना और समस्या निवारण।"),
    "Electrical Panel Safety": ("इलेक्ट्रिकल पैनल सुरक्षा", "लॉक-आउट / टैग-आउट के साथ इलेक्ट्रिकल पैनल के पास सुरक्षित कार्य।"),
    "Material Handling": ("मटीरियल हैंडलिंग", "प्लांट के अंदर सामग्री का सुरक्षित संचालन और आवागमन।"),
}
CATEGORY_HI = {t: v[0] for t, v in MODULES.items()}

DEPARTMENTS = {"Production": "प्रोडक्शन", "QC": "क्यूसी (गुणवत्ता नियंत्रण)", "Maintenance": "मेंटेनेंस", "Quality": "गुणवत्ता"}

GUIDELINES = {
    "Report EVERY near-miss incident immediately to your supervisor — do not underestimate it.":
        "हर नियर-मिस घटना की सूचना तुरंत अपने सुपरवाइज़र को दें — इसे हल्के में न लें।",
    "Fill all record sheets and logbooks completely and accurately — no blank entries.":
        "सभी रिकॉर्ड शीट और लॉगबुक पूरी तरह और सही-सही भरें — कोई प्रविष्टि खाली न छोड़ें।",
    "Never deviate from Standard Operating Window (SOW) parameters without approval from your HOD.":
        "अपने एचओडी की स्वीकृति के बिना मानक संचालन विंडो (SOW) के मापदंडों से कभी विचलित न हों।",
    "Ensure no spillage or leakage of liquids. Store all liquids in secondary containments.":
        "सुनिश्चित करें कि किसी तरल का रिसाव या फैलाव न हो। सभी तरल पदार्थों को द्वितीयक कंटेनमेंट में रखें।",
    "Segregate waste at source — dispose of acid waste, scrap, and process waste through the environmental department procedure.":
        "कचरे को स्रोत पर ही अलग करें — एसिड कचरा, स्क्रैप और प्रक्रिया कचरे का निपटान पर्यावरण विभाग की प्रक्रिया से करें।",
    "Switch off all lights, equipment, and energy systems when not required.":
        "जब ज़रूरत न हो, तब सभी लाइट, उपकरण और ऊर्जा प्रणालियाँ बंद कर दें।",
    "[DEMO] Wear all PPE required for your work area before entering the shop floor.":
        "[डेमो] शॉप फ़्लोर में प्रवेश करने से पहले अपने कार्य क्षेत्र के लिए आवश्यक सभी पीपीई पहनें।",
    "[DEMO] Follow LOTO (lock-out / tag-out) before any cleaning, maintenance or repair.":
        "[डेमो] किसी भी सफ़ाई, रखरखाव या मरम्मत से पहले LOTO (लॉक-आउट / टैग-आउट) का पालन करें।",
    "[DEMO] Do not operate any equipment you have not been trained and authorised for.":
        "[डेमो] जिस उपकरण का आपको प्रशिक्षण और अधिकार नहीं मिला है, उसे न चलाएँ।",
}

STEP_1 = ("For a cold furnace start-up, inspect the furnace internally after cleaning and repair activities.",
          "कोल्ड फ़र्नेस स्टार्ट-अप के लिए, सफ़ाई और मरम्मत कार्यों के बाद फ़र्नेस का आंतरिक निरीक्षण करें। हीटिंग प्रक्रिया शुरू करने से पहले सुनिश्चित करें कि फ़र्नेस संचालन के लिए तैयार है।")
STEP_31 = ("Complete the casting operation and ensure the cast billets are properly cooled",
           "ढलाई का काम पूरा करें और सुनिश्चित करें कि ढाले गए बिलेट ठीक से ठंडे होकर अगली प्रक्रिया के लिए तैयार हैं।")

OBJECTIVES = ("Understand cold furnace start-up checks\nFollow the casting sequence safely\nEnsure cast billets are ready for the next process",
              "कोल्ड फ़र्नेस स्टार्ट-अप की जाँच समझें\nढलाई के क्रम का सुरक्षित रूप से पालन करें\nसुनिश्चित करें कि ढाले गए बिलेट अगली प्रक्रिया के लिए तैयार हैं")

QUESTIONS = {
    "Before starting heating on a cold furnace, what should be checked first after cleaning and repair?": (
        "ठंडे फ़र्नेस पर हीटिंग शुरू करने से पहले, सफ़ाई और मरम्मत के बाद सबसे पहले क्या जाँचना चाहिए?",
        {"Only the gas pressure setting": "केवल गैस प्रेशर सेटिंग",
         "The furnace interior and readiness for operation": "फ़र्नेस का आंतरिक भाग और संचालन के लिए उसकी तैयारी",
         "The billet casting machine speed": "बिलेट कास्टिंग मशीन की गति",
         "The cooling water temperature": "कूलिंग वॉटर का तापमान"}),
    "What must be ensured when the casting operation is complete?": (
        "ढलाई का कार्य पूरा होने पर क्या सुनिश्चित करना चाहिए?",
        {"The furnace is switched off immediately": "फ़र्नेस तुरंत बंद कर दी गई हो",
         "Cast billets are properly cooled and ready for the next process": "ढाले गए बिलेट ठीक से ठंडे हों और अगली प्रक्रिया के लिए तैयार हों",
         "The scrap bin is emptied": "स्क्रैप बिन खाली कर दिया गया हो",
         "The shift log is signed": "शिफ्ट लॉग पर हस्ताक्षर हो गए हों"}),
}

VMPL = {
    "tagline_hi": "एल्युमिनियम एक्सट्रूज़न से लेकर फ़ैब्रिकेशन और इन-हाउस एनोडाइज़िंग सुविधा के साथ फ़िनिशिंग तक की संपूर्ण क्षमताएँ",
    "location_hi": "मुंद्रा, गुजरात",
    "about_hi": (
        "विशाखा मेटल्स प्राइवेट लिमिटेड (VMPL), विशाखा समूह का हिस्सा, सोलर फ़ोटोवोल्टिक (PV) मॉड्यूल के लिए एल्युमिनियम फ़्रेम के भारत के अग्रणी निर्माताओं में से एक है। "
        "कंपनी सोलर उद्योग को समर्पित एक पूर्णतः एकीकृत एल्युमिनियम फ़्रेम निर्माण सुविधा संचालित करती है, जो एल्युमिनियम एक्सट्रूज़न से लेकर फ़ैब्रिकेशन और इन-हाउस एनोडाइज़िंग सुविधा के साथ फ़िनिशिंग तक की संपूर्ण क्षमताएँ प्रदान करती है। "
        "मुंद्रा, गुजरात में स्थित यह सुविधा वर्तमान में 3.5 GW की कुल ऊर्जा क्षमता वाले सोलर मॉड्यूल इंस्टॉलेशन को सहयोग देती है, और निकट भविष्य में उत्पादन क्षमता 10 GW तक बढ़ने की उम्मीद है।\n\n"
        "6063 और 6005 एल्युमिनियम मिश्र धातुओं से बने ये फ़्रेम उत्कृष्ट टिकाऊपन, संक्षारण प्रतिरोध, आयामी स्थिरता और लंबी सेवा आयु प्रदान करते हैं, जिससे सोलर मॉड्यूल की विश्वसनीय सुरक्षा और संरचनात्मक मज़बूती सुनिश्चित होती है।\n\n"
        "VMPL की एकीकृत निर्माण क्षमताएँ आयामी सटीकता, सतह की फ़िनिश, यांत्रिक मज़बूती, संक्षारण प्रतिरोध और प्रोफ़ाइल की गुणवत्ता जैसे महत्वपूर्ण मापदंडों पर निरंतर नियंत्रण संभव बनाती हैं।"),
}


def fill(obj, field, value):
    """Set obj.<field> only when it is empty. Returns 1 if changed."""
    if value and not getattr(obj, field):
        setattr(obj, field, value)
        return 1
    return 0


class Command(BaseCommand):
    help = "Fill empty Hindi fields for the demo content (never overwrites existing Hindi)."

    def handle(self, *args, **opts):
        n = 0
        for plant in Plant.objects.filter(code="vmpl-p1"):
            for f, v in VMPL.items():
                n += fill(plant, f, v)
            plant.save()
        for d in Department.objects.all():
            if fill(d, "name_hi", DEPARTMENTS.get(d.name)):
                d.save(); n += 1
        for pr in Process.objects.all():
            if fill(pr, "name_hi", CATEGORY_HI.get(pr.name)):
                pr.save(); n += 1
        for m in Module.objects.all():
            hit = MODULES.get(m.title)
            if not hit:
                continue
            changed = fill(m, "title_hi", hit[0]) + fill(m, "summary_hi", hit[1]) + fill(m, "category_hi", CATEGORY_HI.get(m.category))
            if m.overview == m.summary:          # demo overview is the same text as the summary
                changed += fill(m, "overview_hi", hit[1])
            if m.slug == "vmpl_melt_cast" and m.objectives == OBJECTIVES[0]:
                changed += fill(m, "objectives_hi", OBJECTIVES[1])
            if changed:
                m.save(); n += changed
            for step in m.steps.filter(text_hi=""):
                hi = None
                if step.text.startswith("[DEMO]"):
                    hi = f"[डेमो] {hit[0]} — चरण {step.number}। इसे स्वीकृत एसओपी पाठ से बदलें।"
                elif step.text.startswith(STEP_1[0]):
                    hi = STEP_1[1]
                elif step.text.startswith(STEP_31[0]):
                    hi = STEP_31[1]
                if hi:
                    step.text_hi = hi; step.save(update_fields=["text_hi"]); n += 1
        for g in SafetyGuideline.objects.filter(text_hi=""):
            if GUIDELINES.get(g.text):
                g.text_hi = GUIDELINES[g.text]; g.save(update_fields=["text_hi"]); n += 1
        for q in Question.objects.filter(text_hi=""):
            hit = QUESTIONS.get(q.text)
            if hit:
                q.text_hi = hit[0]; q.save(update_fields=["text_hi"]); n += 1
                for c in q.choices.filter(text_hi=""):
                    if hit[1].get(c.text):
                        c.text_hi = hit[1][c.text]; c.save(update_fields=["text_hi"]); n += 1
        self.stdout.write(self.style.SUCCESS(f"Hindi content filled ({n} fields). Existing Hindi was left untouched."))
