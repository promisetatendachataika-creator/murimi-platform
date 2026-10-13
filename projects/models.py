"""
Farm projects that investors can back.

Staff create and update projects in the admin. Investors see the visible ones
in their space and can say they're interested; staff then follow up.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from accounts.choices import CROPS, PROVINCES, ROLE_FARMER, ROLE_INVESTOR

MILESTONES = ["Land preparation", "Planting", "Spraying and weeding", "Harvest"]


class Project(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_OPEN = "open"
    STATUS_FUNDED = "funded"
    STATUS_GROWING = "growing"
    STATUS_HARVESTED = "harvested"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft (hidden from investors)"),
        (STATUS_OPEN, "Open for investors"),
        (STATUS_FUNDED, "Fully funded"),
        (STATUS_GROWING, "Growing"),
        (STATUS_HARVESTED, "Harvested"),
        (STATUS_CLOSED, "Closed (hidden)"),
    ]
    VISIBLE = [STATUS_OPEN, STATUS_FUNDED, STATUS_GROWING, STATUS_HARVESTED]

    title = models.CharField(max_length=120, help_text="e.g. 1-Hectare Sugar Beans")
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="farm_projects", limit_choices_to={"role": ROLE_FARMER},
        help_text="The farmer who will grow it. They see this project in their own space.")
    crop = models.CharField(max_length=40, choices=[(c, c) for c in CROPS])
    province = models.CharField(max_length=40, choices=[(p, p) for p in PROVINCES])
    area = models.CharField("District or town", max_length=80)
    size_ha = models.DecimalField("Size (hectares)", max_digits=8, decimal_places=2)
    summary = models.TextField(help_text="Two or three plain sentences investors will read: the land, the water, the plan, the buyer.")

    share_price_usd = models.PositiveIntegerField("Price per share (US$)", help_text="The smallest amount one investor can put in.")
    target_usd = models.PositiveIntegerField("Amount needed (US$)", help_text="Total needed for inputs and labour this season.")
    season_days = models.PositiveIntegerField("Season length (days)", null=True, blank=True)
    expected_harvest = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    milestone = models.PositiveSmallIntegerField(
        "Milestones done", default=0, validators=[MinValueValidator(0), MaxValueValidator(len(MILESTONES))],
        help_text="0 = not started, 1 = land prepared, 2 = planted, 3 = sprayed and weeded, 4 = harvested.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.area})"

    def as_dict(self, user=None):
        return {
            "id": self.pk,
            "title": self.title,
            "crop": self.crop,
            "place": f"{self.area}, {self.province}",
            "size_ha": f"{self.size_ha.normalize():f}",
            "summary": self.summary,
            "share_price_usd": self.share_price_usd,
            "target_usd": self.target_usd,
            "season_days": self.season_days,
            "expected_harvest": self.expected_harvest.isoformat() if self.expected_harvest else None,
            "status": self.status,
            "status_label": dict(self.STATUS_CHOICES)[self.status].split(" (")[0],
            "milestone": self.milestone,
            "milestones": MILESTONES,
            "interested": bool(user and self.interests.filter(investor=user).exists()),
        }


class Interest(models.Model):
    """An investor said "I'm interested" in a project. Staff follow up on WhatsApp."""

    investor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interests",
                                 limit_choices_to={"role": ROLE_INVESTOR})
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="interests")
    created_at = models.DateTimeField(auto_now_add=True)
    followed_up = models.BooleanField(default=False, help_text="Tick once someone has contacted this investor.")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["investor", "project"], name="one_interest_per_project")]

    def __str__(self):
        return f"{self.investor} → {self.project}"
