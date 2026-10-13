"""
Real market prices and haulage jobs, entered by Murimi staff in the admin.

- PriceReport: one price seen at one market on one day (e.g. potatoes,
  15 kg pocket, Mbare Musika, US$ 6.50 on 14 Oct). Farmers see the latest one.
- HaulJob: a load that needs moving. Drivers whose trucks fit see open jobs and
  can say they're interested; staff then assign the job to one driver.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.choices import CROPS, PROVINCES, ROLE_DRIVER

MARKETS = ["Mbare Musika", "Bulawayo market", "Mutare market", "Gweru market", "Masvingo market",
           "Supermarket buyer", "Exporter", "Farm gate", "Other"]
TRUCK_SIZES = ["1 t", "3 t", "8 t", "15 t", "30 t"]


class PriceReport(models.Model):
    crop = models.CharField(max_length=40, choices=[(c, c) for c in CROPS])
    market = models.CharField(max_length=40, choices=[(m, m) for m in MARKETS], default="Mbare Musika")
    unit = models.CharField(max_length=40, help_text="How it's sold, e.g. 15 kg pocket, 8 kg crate, per tonne, 50 kg bag.")
    price_usd = models.DecimalField("Price (US$)", max_digits=10, decimal_places=2)
    price_zig = models.DecimalField("Price (ZiG)", max_digits=12, decimal_places=2, null=True, blank=True)
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=200, blank=True, help_text="Optional, e.g. 'Good quality only' or 'Prices falling'.")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.crop}, {self.unit} at {self.market}: US${self.price_usd} ({self.date})"


def latest_prices():
    """The newest report for each crop + market + unit, with the change since the one before."""
    seen, out = {}, []
    for r in PriceReport.objects.all():  # newest first
        key = (r.crop, r.market, r.unit.strip().lower())
        if key in seen:
            if seen[key]["previous_usd"] is None:
                seen[key]["previous_usd"] = str(r.price_usd)
            continue
        item = {"crop": r.crop, "market": r.market, "unit": r.unit, "price_usd": str(r.price_usd),
                "price_zig": str(r.price_zig) if r.price_zig is not None else None,
                "date": r.date.isoformat(), "note": r.note, "previous_usd": None}
        seen[key] = item
        out.append(item)
    return out


class HaulJob(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_ASSIGNED = "assigned"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft (hidden)"),
        (STATUS_OPEN, "Open for drivers"),
        (STATUS_ASSIGNED, "Assigned to a driver"),
        (STATUS_DONE, "Delivered"),
        (STATUS_CANCELLED, "Cancelled (hidden)"),
    ]

    load = models.CharField(max_length=120, help_text="What is being moved, e.g. 2.5 t potatoes in pockets.")
    pickup_area = models.CharField("Pick up from (town or farm)", max_length=80)
    pickup_province = models.CharField(max_length=40, choices=[(p, p) for p in PROVINCES])
    dropoff = models.CharField("Deliver to", max_length=120, help_text="e.g. Mbare Musika, Harare")
    truck_size = models.CharField("Truck size needed", max_length=8, choices=[(t, t) for t in TRUCK_SIZES])
    needs_cold = models.BooleanField("Needs a refrigerated truck", default=False)
    distance_km = models.PositiveIntegerField("Distance (km)", null=True, blank=True)
    pickup_date = models.DateField(null=True, blank=True)
    pay_usd = models.PositiveIntegerField("Pay offered (US$)", null=True, blank=True,
                                          help_text="Leave empty if drivers should quote.")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="haul_jobs", limit_choices_to={"role": ROLE_DRIVER},
                               help_text="Set when the job is given to a driver. They see it under 'Your jobs'.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pickup_date", "-created_at"]

    def __str__(self):
        return f"{self.load}: {self.pickup_area} → {self.dropoff}"

    def as_dict(self, user=None):
        return {
            "id": self.pk,
            "route": f"{self.pickup_area} → {self.dropoff}",
            "load": self.load,
            "province": self.pickup_province,
            "truck_size": self.truck_size,
            "needs_cold": self.needs_cold,
            "distance_km": self.distance_km,
            "pickup_date": self.pickup_date.isoformat() if self.pickup_date else None,
            "pay_usd": self.pay_usd,
            "status": self.status,
            "status_label": dict(self.STATUS_CHOICES)[self.status].split(" (")[0],
            "interested": bool(user and self.interests.filter(driver=user).exists()),
            "mine": bool(user and self.driver_id == user.pk),
        }


class JobInterest(models.Model):
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_interests",
                               limit_choices_to={"role": ROLE_DRIVER})
    job = models.ForeignKey(HaulJob, on_delete=models.CASCADE, related_name="interests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["driver", "job"], name="one_interest_per_job")]

    def __str__(self):
        return f"{self.driver} → {self.job}"
