from django.contrib import admin
from django.utils.html import format_html

from .models import Document


def open_link(doc):
    if not doc.pk:
        return "—"
    return format_html('<a href="/api/documents/{}/file/" target="_blank" rel="noopener">Open {}</a>',
                       doc.pk, "photo" if doc.content_type.startswith("image/") else "PDF")


class DocumentInline(admin.TabularInline):
    """Shown at the bottom of each person's page in Users."""
    model = Document
    extra = 0
    fields = ("kind", "open_file", "uploaded_at", "status", "note_to_user")
    readonly_fields = ("kind", "open_file", "uploaded_at")
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False  # people upload their own documents from their space

    @admin.display(description="File")
    def open_file(self, obj):
        return open_link(obj)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("owner", "role", "kind", "open_file", "uploaded_at", "status")
    list_filter = ("status", "kind", "owner__role")
    search_fields = ("owner__full_name", "owner__phone", "owner__username")
    list_editable = ("status",)
    readonly_fields = ("owner", "kind", "open_file", "original_name", "content_type", "size_bytes", "uploaded_at")
    fields = ("owner", "kind", "open_file", "original_name", "uploaded_at", "status", "note_to_user")
    actions = ["accept", "needs_redoing"]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Role", ordering="owner__role")
    def role(self, obj):
        return obj.owner.get_role_display()

    @admin.display(description="File")
    def open_file(self, obj):
        return open_link(obj)

    @admin.action(description="Accept selected documents")
    def accept(self, request, queryset):
        n = queryset.update(status=Document.STATUS_ACCEPTED)
        self.message_user(request, f"{n} accepted.")

    @admin.action(description="Mark selected as needs redoing")
    def needs_redoing(self, request, queryset):
        n = queryset.update(status=Document.STATUS_REJECTED)
        self.message_user(request, f"{n} marked as needs redoing. Open each one to add a note saying why.")
