import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.knowledge.models import KBCategory, KBItem

CATS = [("Safety & compliance", "सुरक्षा और अनुपालन", "shield", "red"), ("Machine manuals", "मशीन मैनुअल", "settings", "blue"),
        ("Forms & formats", "फ़ॉर्म और प्रारूप", "file", "green"), ("Quality standards", "गुणवत्ता मानक", "award", "amber")]
DEMO = [("Emergency evacuation plan", "आपातकालीन निकासी योजना", 0, "Where to go and what to do when the alarm sounds."),
        ("Extrusion press operator manual", "एक्सट्रूज़न प्रेस ऑपरेटर मैनुअल", 1, "Controls, start-up and shut-down."),
        ("Shift handover format", "शिफ्ट हैंडओवर प्रारूप", 2, "Fill in at the end of every shift.")]


def tiny_pdf(title):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 22); c.drawString(60, 760, title)
    c.setFont("Helvetica", 12); c.drawString(60, 730, "[DEMO] Replace this file with the approved document.")
    c.save()
    return buf.getvalue()


class Command(BaseCommand):
    help = "Create demo knowledge-base categories and sample documents (safe to run again)."

    def handle(self, *args, **opts):
        cats = []
        for i, (n, h, icon, color) in enumerate(CATS):
            c, _ = KBCategory.objects.get_or_create(name=n, defaults={"name_hi": h, "icon": icon, "color": color, "order": i})
            cats.append(c)
        for title, hi, ci, desc in DEMO:
            if not KBItem.objects.filter(title=title).exists():
                it = KBItem(category=cats[ci], title=title, title_hi=hi, description=desc)
                it.file.save(title.lower().replace(" ", "_") + ".pdf", ContentFile(tiny_pdf(title)), save=False)
                it.save()
        if not KBItem.objects.filter(url__icontains="youtu").exists():
            KBItem.objects.create(category=cats[0], title="Fire safety basics (video)", title_hi="अग्नि सुरक्षा की मूल बातें (वीडियो)", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.stdout.write("Knowledge base demo ready.")
