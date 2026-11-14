from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ApprovalScope, User


class ApprovalScopeInline(admin.TabularInline):
    model = ApprovalScope
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "employee_id", "role", "designation",
                    "is_active"]
    list_filter = ["role", "is_active", "plants"]
    search_fields = ["email", "first_name", "last_name", "employee_id"]
    filter_horizontal = ["plants", "groups", "user_permissions"]
    inlines = [ApprovalScopeInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("first_name", "last_name", "employee_id", "designation",
                                "preferred_language")}),
        ("Shiksha access", {"fields": ("role", "plants", "default_plant", "department")}),
        ("Django permissions", {"classes": ("collapse",),
                                "fields": ("is_active", "is_staff", "is_superuser",
                                           "groups", "user_permissions")}),
        ("Dates", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "employee_id", "role",
                           "password1", "password2")}),
    )
