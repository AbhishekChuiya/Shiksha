from django.db import models

from apps.core.i18n import localized


class Plant(models.Model):
    code = models.SlugField(max_length=20, unique=True, help_text="e.g. vmpl-p1")
    name = models.CharField(max_length=60, help_text="Short name, e.g. VMPL P1")
    company = models.CharField(max_length=160, blank=True,
                               help_text="e.g. Vishakha Metals Private Limited")
    tagline = models.CharField(max_length=200, blank=True)
    tagline_hi = models.CharField("tagline (Hindi)", max_length=200, blank=True)
    tagline_gu = models.CharField("tagline (Gujarati)", max_length=200, blank=True)
    location = models.CharField(max_length=120, blank=True)
    location_hi = models.CharField("location (Hindi)", max_length=120, blank=True)
    location_gu = models.CharField("location (Gujarati)", max_length=120, blank=True)
    about = models.TextField(blank=True)
    about_hi = models.TextField("about (Hindi)", blank=True)
    about_gu = models.TextField("about (Gujarati)", blank=True)
    banner = models.ImageField(upload_to="plants/banners/", blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    display_tagline = property(lambda self: localized(self, "tagline"))
    display_location = property(lambda self: localized(self, "location"))
    display_about = property(lambda self: localized(self, "about"))


class PlantPhoto(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="plants/photos/")
    caption = models.CharField(max_length=200, blank=True)
    caption_hi = models.CharField("caption (Hindi)", max_length=200, blank=True)
    caption_gu = models.CharField("caption (Gujarati)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    display_caption = property(lambda self: localized(self, "caption"))


class PlantVideo(models.Model):
    """A video about the plant (a YouTube/Vimeo/CDN link, or an uploaded file) shown on the Plant Overview page."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=160)
    title_hi = models.CharField("title (Hindi)", max_length=160, blank=True)
    title_gu = models.CharField("title (Gujarati)", max_length=160, blank=True)
    url = models.URLField(blank=True, help_text="YouTube / Vimeo / direct link. Used if no file is uploaded.")
    file = models.FileField(upload_to="plants/videos/", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    display_title = property(lambda self: localized(self, "title"))

    @property
    def embed_url(self):
        u = self.url
        if "youtu.be/" in u:
            return "https://www.youtube.com/embed/" + u.split("youtu.be/")[1].split("?")[0]
        if "youtube.com/watch" in u and "v=" in u:
            return "https://www.youtube.com/embed/" + u.split("v=")[1].split("&")[0]
        if "vimeo.com/" in u:
            return "https://player.vimeo.com/video/" + u.rstrip("/").split("/")[-1]
        return ""

    @property
    def source(self):
        return self.file.url if self.file else self.url


class PlantStage(models.Model):
    """One step of the plant journey shown on the learner dashboard (e.g. Gate Entry → Lab Testing → Extrusion …)."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=80)
    name_hi = models.CharField("name (Hindi)", max_length=80, blank=True)
    name_gu = models.CharField("name (Gujarati)", max_length=80, blank=True)
    module = models.ForeignKey("learning.Module", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
                               help_text="Leave empty to link by name automatically")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.plant.name}: {self.name}"

    display_name = property(lambda self: localized(self, "name"))


class Department(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=80)
    name_hi = models.CharField("name (Hindi)", max_length=80, blank=True)
    name_gu = models.CharField("name (Gujarati)", max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        unique_together = [("plant", "name")]

    def __str__(self):
        return f"{self.name} ({self.plant.name})"

    display_name = property(lambda self: localized(self, "name"))


class Process(models.Model):
    """A plant process such as Melt & Cast, Extrusion, Anodizing."""

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="processes")
    name = models.CharField(max_length=100)
    name_hi = models.CharField("name (Hindi)", max_length=100, blank=True)
    name_gu = models.CharField("name (Gujarati)", max_length=100, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        unique_together = [("department", "name")]
        verbose_name_plural = "processes"

    def __str__(self):
        return self.name

    display_name = property(lambda self: localized(self, "name"))

    @property
    def plant(self):
        return self.department.plant
