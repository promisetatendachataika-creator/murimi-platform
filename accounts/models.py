import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .choices import ROLE_CHOICES

PHONE_DIGITS = re.compile(r"\D")


USERNAME_RE = re.compile(r"^[a-z][a-z0-9_.]{2,29}$")
RESERVED_USERNAMES = {"admin", "administrator", "murimi", "staff", "support", "help", "root", "api"}


def normalize_username(raw):
    """Usernames are stored lower-case: 3–30 letters, digits, _ or ., starting with a letter."""
    name = (raw or "").strip().lower().lstrip("@")
    if not USERNAME_RE.match(name):
        raise ValidationError("Use 3–30 letters, numbers, _ or ., starting with a letter (e.g. tendai_moyo).")
    if name in RESERVED_USERNAMES:
        raise ValidationError("That username is reserved. Please choose another.")
    return name


def looks_like_username(identifier):
    """A log-in box entry with any letter in it is a username; otherwise it's a phone number."""
    return any(ch.isalpha() for ch in (identifier or ""))


def normalize_phone(raw):
    """
    Turn whatever people type into one standard form, e.g. "+263771234567".

    Accepts "+263 77 123 4567", "0771234567" (assumed Zimbabwean),
    "263771234567" and "00447700900123".
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValidationError("Enter your WhatsApp number.")
    has_plus = raw.startswith("+")
    digits = PHONE_DIGITS.sub("", raw)
    if not has_plus:
        if digits.startswith("00"):
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 10:
            digits = "263" + digits[1:]
    if not (9 <= len(digits) <= 15):
        raise ValidationError("Enter a full number with the country code, e.g. +263 77 123 4567.")
    return "+" + digits


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        user = self.model(phone=normalize_phone(phone), **extra)
        if extra.get("email"):
            user.email = self.normalize_email(extra["email"])
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("full_name", "Murimi admin")
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """A person with a Murimi account. They log in with their WhatsApp number."""

    phone = models.CharField("WhatsApp number", max_length=20, unique=True)
    username = models.CharField(max_length=30, unique=True, null=True, blank=True,
                                help_text="Optional second way to log in. 3–30 letters, numbers, _ or .")
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True,
                            help_text="Blank for Murimi staff accounts.")
    whatsapp_consent = models.BooleanField(default=False)
    phone_verified_at = models.DateTimeField(
        "WhatsApp number confirmed", null=True, blank=True,
        help_text="Set when the person types in the code we sent to their WhatsApp. Cleared if the number changes.")

    # Dashboard progress: {"0": true, ...} and saved example projects/jobs {"p3": true, ...}
    steps = models.JSONField(default=dict, blank=True)
    saved = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can log in to this admin site.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def clean(self):
        super().clean()
        try:
            self.phone = normalize_phone(self.phone)
        except ValidationError as e:
            raise ValidationError({"phone": e.messages})
        if User.objects.filter(phone=self.phone).exclude(pk=self.pk).exists():
            raise ValidationError({"phone": "There's already an account with this number."})
        if self.username:
            try:
                self.username = normalize_username(self.username)
            except ValidationError as e:
                raise ValidationError({"username": e.messages})
            if User.objects.filter(username=self.username).exclude(pk=self.pk).exists():
                raise ValidationError({"username": "That username is taken."})
        else:
            self.username = None

    def save(self, *args, **kwargs):
        # Store every number in one form (e.g. +263771234567) so log in always matches,
        # whether the account came from the website or the staff admin.
        try:
            self.phone = normalize_phone(self.phone)
        except ValidationError:
            pass  # clean() reports bad numbers on forms; never block other saves
        self.username = (self.username or "").strip().lower() or None
        if self.pk and self.phone_verified_at:
            old_phone = User.objects.filter(pk=self.pk).values_list("phone", flat=True).first()
            if old_phone and old_phone != self.phone:
                self.phone_verified_at = None  # a new number has to be confirmed again
                if kwargs.get("update_fields") is not None:
                    kwargs["update_fields"] = set(kwargs["update_fields"]) | {"phone_verified_at"}
        super().save(*args, **kwargs)

    @property
    def phone_verified(self):
        return self.phone_verified_at is not None


class Profile(models.Model):
    """The role-specific answers from the sign-up form."""

    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Waiting for checks"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Not approved"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    province = models.CharField(max_length=40, blank=True)
    area = models.CharField("District or town", max_length=80, blank=True)
    size_ha = models.DecimalField("Size (hectares)", max_digits=9, decimal_places=2, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    verification_status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message_to_user = models.TextField(
        blank=True,
        help_text="Shown to the person in their own space, e.g. why they weren't approved or what to do next.")
    status_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    staff_notes = models.TextField(blank=True, help_text="Only Murimi staff can see this.")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user}"

    def save(self, *args, **kwargs):
        # Remember when the check status changes, so the person can see the date.
        if self.pk:
            old = Profile.objects.filter(pk=self.pk).values_list("verification_status", flat=True).first()
            if old != self.verification_status:
                self.status_changed_at = timezone.now()
        super().save(*args, **kwargs)

    def as_dict(self):
        data = dict(self.details or {})
        if self.province:
            data["province"] = self.province
        if self.area:
            data["area"] = self.area
        if self.size_ha is not None:
            data["size"] = f"{self.size_ha.normalize():f}"
        return data

    def status_dict(self):
        return {
            "status": self.verification_status,
            "label": self.get_verification_status_display(),
            "message": self.message_to_user,
            "changed_at": self.status_changed_at.isoformat() if self.status_changed_at else None,
        }


class PhoneCode(models.Model):
    """
    A 6-digit code sent to someone's WhatsApp, to confirm their number or reset
    their password. Only a fingerprint (hash) of the code is stored, never the code.
    """

    PURPOSE_VERIFY = "verify"
    PURPOSE_RESET = "reset"
    PURPOSE_CHOICES = [(PURPOSE_VERIFY, "Confirm WhatsApp number"), (PURPOSE_RESET, "Reset password")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="phone_codes")
    phone = models.CharField("Sent to", max_length=20)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=128, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField("Wrong tries", default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_purpose_display()} code for {self.phone}"
