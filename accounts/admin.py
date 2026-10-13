"""
The staff admin at /admin/. This is where the Murimi team sees every sign-up,
filters by role and province, and marks people as verified.
"""
from django import forms
from django.contrib import admin, messages
from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm

from documents.admin import DocumentInline

from .models import PhoneCode, Profile, User


class UserCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("phone", "username", "full_name", "role")


class UserChangeForm(BaseUserChangeForm):
    # Steps only staff can award (the person can't tick these themselves).
    staff_visit = forms.BooleanField(required=False, label="Field officer visit done",
                                     help_text="Farmers and landowners. Tick only after the visit has really happened.")
    staff_call = forms.BooleanField(required=False, label="Call with the Murimi team done",
                                    help_text="Investors. Tick only after the call.")

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        steps = (self.instance.steps or {}) if self.instance and self.instance.pk else {}
        self.fields["staff_visit"].initial = bool(steps.get("visit"))
        self.fields["staff_call"].initial = bool(steps.get("call"))

    def save(self, commit=True):
        user = super().save(commit=False)
        steps = dict(user.steps or {})
        steps["visit"] = self.cleaned_data.get("staff_visit", False)
        steps["call"] = self.cleaned_data.get("staff_call", False)
        user.steps = {k: v for k, v in steps.items() if k in ("visit", "call") and v}
        if commit:
            user.save()
        return user


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ("verification_status", "message_to_user", "province", "area", "size_ha", "details", "staff_notes")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    inlines = [ProfileInline, DocumentInline]
    ordering = ("-date_joined",)
    list_display = ("full_name", "phone", "whatsapp_ok", "username", "role", "province", "status", "date_joined")
    list_filter = ("role", "profile__verification_status", ("phone_verified_at", admin.EmptyFieldListFilter), "profile__province", "is_staff")
    search_fields = ("full_name", "phone", "username", "email", "profile__area")
    readonly_fields = ("date_joined", "last_login", "view_as", "phone_verified_at")
    fieldsets = (
        (None, {"fields": ("phone", "phone_verified_at", "username", "password", "view_as")}),
        ("Person", {"fields": ("full_name", "email", "role", "whatsapp_consent")}),
        ("Steps only staff can tick", {"fields": ("staff_visit", "staff_call")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
                    "classes": ("collapse",)}),
        ("Dates", {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "username", "full_name", "role", "password1", "password2")}),
    )
    actions = ["mark_verified", "mark_pending"]

    # ---- "View as this person" (superusers only) --------------------------
    # Lets the owner see and change someone's space exactly as they would,
    # without ever knowing their password. Every use is written to the
    # admin history. Staff and superuser accounts can't be viewed this way.
    @admin.display(description="See their space")
    def view_as(self, obj):
        if not obj.pk or obj.is_staff or not obj.role:
            return "—"
        url = reverse("admin:accounts_user_view_as", args=[obj.pk])
        return format_html('<a class="button" href="{}">View the site as {}</a>', url, obj.full_name)

    def get_urls(self):
        extra = [path("<int:pk>/view-as/", self.admin_site.admin_view(self.view_as_page),
                      name="accounts_user_view_as")]
        return extra + super().get_urls()

    def view_as_page(self, request, pk):
        if not request.user.is_superuser:
            raise PermissionDenied
        person = get_object_or_404(User, pk=pk)
        if person.is_staff or not person.role:
            messages.error(request, "Staff accounts can't be viewed this way.")
            return redirect("admin:accounts_user_change", pk)
        if request.method == "POST":
            self.log_change(request, person, f"Viewed the site as this person (by {request.user.phone}).")
            login(request, person, backend="django.contrib.auth.backends.ModelBackend")
            return redirect("/#spot")
        context = {**self.admin_site.each_context(request), "person": person, "opts": self.model._meta,
                   "title": f"View the site as {person.full_name}?"}
        return TemplateResponse(request, "admin/accounts/view_as_confirm.html", context)

    @admin.display(description="Province", ordering="profile__province")
    def province(self, obj):
        return getattr(getattr(obj, "profile", None), "province", "")

    @admin.display(description="WhatsApp confirmed", boolean=True, ordering="phone_verified_at")
    def whatsapp_ok(self, obj):
        return obj.phone_verified_at is not None

    @admin.display(description="Checks", ordering="profile__verification_status")
    def status(self, obj):
        p = getattr(obj, "profile", None)
        return p.get_verification_status_display() if p else "—"

    def _set_status(self, queryset, status):
        n = 0
        for profile in Profile.objects.filter(user__in=queryset):
            profile.verification_status = status
            profile.save()  # save() records the date the status changed
            n += 1
        return n

    @admin.action(description="Mark selected people as verified")
    def mark_verified(self, request, queryset):
        n = self._set_status(queryset, Profile.STATUS_VERIFIED)
        self.message_user(request, f"{n} marked as verified.")

    @admin.action(description="Mark selected people as waiting for checks")
    def mark_pending(self, request, queryset):
        n = self._set_status(queryset, Profile.STATUS_PENDING)
        self.message_user(request, f"{n} marked as waiting.")


admin.site.site_header = "Murimi Intelligent Hub · Staff"
admin.site.site_title = "Murimi staff"
admin.site.index_title = "Sign-ups and accounts"


@admin.register(PhoneCode)
class PhoneCodeAdmin(admin.ModelAdmin):
    """A read-only log of codes sent. The codes themselves are never stored."""
    list_display = ("created_at", "user", "phone", "purpose", "attempts", "used_at", "expires_at")
    list_filter = ("purpose",)
    search_fields = ("phone", "user__full_name", "user__username")
    readonly_fields = [f.name for f in PhoneCode._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
