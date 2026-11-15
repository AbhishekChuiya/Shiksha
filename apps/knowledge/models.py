import os

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.i18n import localized

ICONS = [("folder", "Folder"), ("file", "Document"), ("shield", "Safety"), ("gauge", "Quality"), ("settings", "Machines"),
         ("video", "Videos"), ("book", "Manuals"), ("award", "Standards"), ("leaf", "Environment"), ("flame", "Fire / hot work"), ("bulb", "Ideas")]
COLORS = [("red", "Red"), ("blue", "Blue"), ("green", "Green"), ("amber", "Amber"), ("violet", "Violet"), ("teal", "Teal")]

EXT_KIND = {".pdf": "pdf", ".doc": "doc", ".docx": "doc", ".txt": "doc", ".xls": "sheet", ".xlsx": "sheet", ".csv": "sheet",
            ".ppt": "slides", ".pptx": "slides", ".mp4": "video", ".webm": "video", ".mov": "video", ".m4v": "video",
            ".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image"}


def kind_from_name(name, url=""):
    if name:
        return EXT_KIND.get(os.path.splitext(name)[1].lower(), "doc")
    if url:
        return "video" if any(h in url for h in ("youtube.com", "youtu.be", "vimeo.com")) else "link"
    return "doc"


class KBCategory(models.Model):
    name = models.CharField(max_length=80)
    name_hi = models.CharField("name (Hindi)", max_length=80, blank=True)
    name_gu = models.CharField("name (Gujarati)", max_length=80, blank=True)
    icon = models.CharField(max_length=20, choices=ICONS, default="folder")
    color = models.CharField(max_length=10, choices=COLORS, default="red")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "knowledge category"
        verbose_name_plural = "knowledge categories"

    def __str__(self):
        return self.name

    display_name = property(lambda self: localized(self, "name"))


class KBItem(models.Model):
    class Kind(models.TextChoices):
        PDF = "pdf", "PDF"
        DOC = "doc", "Document"
        SHEET = "sheet", "Spreadsheet"
        SLIDES = "slides", "Presentation"
        VIDEO = "video", "Video"
        IMAGE = "image", "Image"
        LINK = "link", "Web link"

    category = models.ForeignKey(KBCategory, on_delete=models.PROTECT, related_name="items")
    title = models.CharField(max_length=200)
    title_hi = models.CharField("title (Hindi)", max_length=200, blank=True)
    title_gu = models.CharField("title (Gujarati)", max_length=200, blank=True)
    description = models.TextField(blank=True)
    description_hi = models.TextField("description (Hindi)", blank=True)
    description_gu = models.TextField("description (Gujarati)", blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, blank=True,
                            help_text="Leave blank — it is worked out from the uploaded file.")
    file = models.FileField(upload_to="knowledge/%Y/", blank=True)
    url = models.URLField(blank=True, help_text="A web link or YouTube/Vimeo address (used when there is no file).")
    plant = models.ForeignKey("plants.Plant", null=True, blank=True, on_delete=models.CASCADE, related_name="kb_items",
                              help_text="Leave empty to show at every plant.")
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__order", "order", "title"]

    def __str__(self):
        return self.title

    display_title = property(lambda self: localized(self, "title"))
    display_description = property(lambda self: localized(self, "description"))

    def save(self, *args, **kwargs):
        if not self.kind or (self.file and self.kind == "link"):
            self.kind = kind_from_name(self.file.name if self.file else "", self.url)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("knowledge:item", args=[self.pk])

    @property
    def embed_url(self):
        """Turn a YouTube/Vimeo watch link into its embeddable form."""
        u = self.url
        if "youtu.be/" in u:
            return "https://www.youtube.com/embed/" + u.split("youtu.be/")[1].split("?")[0]
        if "youtube.com/watch" in u and "v=" in u:
            return "https://www.youtube.com/embed/" + u.split("v=")[1].split("&")[0]
        if "vimeo.com/" in u:
            return "https://player.vimeo.com/video/" + u.rstrip("/").split("/")[-1]
        return ""
