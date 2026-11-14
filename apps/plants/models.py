from django.db import models

from apps.core.i18n import localized


class Plant(models.Model):
    code = models.SlugField(max_length=20, unique=True, help_text="e.g. vmpl-p1")
    name = models.CharField(max_length=60, help_text="Short name, e.g. VMPL P1")
    company = models.CharField(max_length=160, blank=True,
                               help_text="e.g. Vishakha Metals Private Limited")
    tagline = models.CharField(max_length=200, blank=True)
    tagline_hi = models.CharField("tagline (Hindi)", max_length=200, blank=True)
    location = models.CharField(max_length=120, blank=True)
    location_hi = models.CharField("location (Hindi)", max_length=120, blank=True)
    about = models.TextField(blank=True)
    about_hi = models.TextField("about (Hindi)", blank=True)
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
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    display_caption = property(lambda self: localized(self, "caption"))


class Department(models.Model):
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=80)
    name_hi = models.CharField("name (Hindi)", max_length=80, blank=True)
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
