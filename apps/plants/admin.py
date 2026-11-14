from django.contrib import admin

from .models import Department, Plant, PlantPhoto, Process


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0


class PhotoInline(admin.TabularInline):
    model = PlantPhoto
    extra = 0


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "company", "location", "order", "is_active"]
    list_editable = ["order", "is_active"]
    prepopulated_fields = {"code": ["name"]}
    inlines = [DepartmentInline, PhotoInline]


class ProcessInline(admin.TabularInline):
    model = Process
    extra = 0


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "plant", "order"]
    list_filter = ["plant"]
    inlines = [ProcessInline]


@admin.register(Process)
class ProcessAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "order"]
    list_filter = ["department__plant", "department"]
    search_fields = ["name"]
