from django.contrib import admin
from django.db.models import Count

from .models import Interest, Project


class InterestInline(admin.TabularInline):
    model = Interest
    extra = 0
    fields = ("investor", "investor_phone", "created_at", "followed_up")
    readonly_fields = ("investor", "investor_phone", "created_at")
    can_delete = True

    @admin.display(description="WhatsApp")
    def investor_phone(self, obj):
        return obj.investor.phone


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "crop", "area", "status", "milestone", "share_price_usd", "interested")
    list_filter = ("status", "crop", "province")
    search_fields = ("title", "area", "farmer__full_name")
    autocomplete_fields = ("farmer",)
    inlines = [InterestInline]
    fieldsets = (
        (None, {"fields": ("title", "status", "farmer")}),
        ("Where and what", {"fields": ("crop", "province", "area", "size_ha", "summary")}),
        ("Money", {"fields": ("share_price_usd", "target_usd")}),
        ("Season", {"fields": ("milestone", "season_days", "expected_harvest")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n_interest=Count("interests"))

    @admin.display(description="Interested", ordering="n_interest")
    def interested(self, obj):
        return obj.n_interest


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ("project", "investor", "phone", "created_at", "followed_up")
    list_filter = ("followed_up", "project")
    list_editable = ("followed_up",)
    search_fields = ("investor__full_name", "investor__phone", "project__title")

    @admin.display(description="WhatsApp")
    def phone(self, obj):
        return obj.investor.phone
