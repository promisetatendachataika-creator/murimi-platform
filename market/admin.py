from django.contrib import admin
from django.db.models import Count

from .models import HaulJob, JobInterest, PriceReport


@admin.register(PriceReport)
class PriceReportAdmin(admin.ModelAdmin):
    list_display = ("date", "crop", "unit", "market", "price_usd", "price_zig", "note")
    list_filter = ("crop", "market", "date")
    search_fields = ("crop", "unit", "note")
    date_hierarchy = "date"
    fields = ("date", "crop", "market", "unit", "price_usd", "price_zig", "note")

    def save_model(self, request, obj, form, change):
        if not obj.reported_by_id:
            obj.reported_by = request.user
        super().save_model(request, obj, form, change)


class JobInterestInline(admin.TabularInline):
    model = JobInterest
    extra = 0
    fields = ("driver", "phone", "trucks", "created_at")
    readonly_fields = ("driver", "phone", "trucks", "created_at")

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="WhatsApp")
    def phone(self, obj):
        return obj.driver.phone

    @admin.display(description="Trucks")
    def trucks(self, obj):
        p = getattr(obj.driver, "profile", None)
        d = (p.details if p else {}) or {}
        return f"{d.get('count', '?')} × {', '.join(d.get('trucks') or [])}" + (" · refrigerated" if d.get("cold") == "Yes" else "")


@admin.register(HaulJob)
class HaulJobAdmin(admin.ModelAdmin):
    list_display = ("load", "pickup_area", "dropoff", "truck_size", "pickup_date", "pay_usd", "status", "driver", "interested")
    list_filter = ("status", "truck_size", "pickup_province", "needs_cold")
    search_fields = ("load", "pickup_area", "dropoff", "driver__full_name")
    autocomplete_fields = ("driver",)
    inlines = [JobInterestInline]
    fieldsets = (
        (None, {"fields": ("status", "load", "truck_size", "needs_cold")}),
        ("Route", {"fields": ("pickup_area", "pickup_province", "dropoff", "distance_km", "pickup_date")}),
        ("Pay and driver", {"fields": ("pay_usd", "driver"),
                            "description": "To give the job to a driver: pick them below and set Status to 'Assigned to a driver'."}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(n_interest=Count("interests"))

    @admin.display(description="Interested", ordering="n_interest")
    def interested(self, obj):
        return obj.n_interest
