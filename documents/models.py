"""
Documents and photos people upload so Murimi can verify them:
IDs, title deeds / offer letters, farm photos, driver's licences and so on.

Files are stored OUTSIDE the public website (settings.PRIVATE_UPLOADS) and can
only be opened through documents.api.file_view, which checks that the viewer is
the owner or Murimi staff.
"""
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

# kind: (label, roles that need it, how many they can upload)
KINDS = {
    "national_id": ("National ID or passport", ["farmer", "landowner", "investor", "driver"], 2),
    "farm_photo": ("Photos of your farm", ["farmer"], 10),
    "title_deed": ("Title deed or offer letter", ["landowner"], 3),
    "land_photo": ("Photos of your land", ["landowner"], 10),
    "drivers_licence": ("Driver's licence", ["driver"], 2),
    "truck_registration": ("Truck registration book", ["driver"], 5),
    "truck_photo": ("Photos of your truck", ["driver"], 6),
}
KIND_CHOICES = [(k, v[0]) for k, v in KINDS.items()]


def kinds_for(role):
    return [k for k, (_, roles, _) in KINDS.items() if role in roles]


def upload_path(instance, filename):
    # Never trust the uploaded name: store under a random name in the owner's folder.
    ext = Path(filename).suffix.lower()[:6]
    return f"{instance.owner_id}/{uuid.uuid4().hex}{ext}"


class Document(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Waiting for review"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Needs redoing"),
    ]

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    file = models.FileField(upload_to=upload_path)
    original_name = models.CharField(max_length=200)
    content_type = models.CharField(max_length=60)
    size_bytes = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    note_to_user = models.CharField(max_length=300, blank=True,
                                    help_text="Shown to the person, e.g. 'Photo is blurry, please retake it in daylight.'")

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.owner}"

    def as_dict(self):
        return {
            "id": self.pk,
            "kind": self.kind,
            "name": self.original_name,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "uploaded_at": self.uploaded_at.isoformat(),
            "status": self.status,
            "status_label": self.get_status_display(),
            "note": self.note_to_user,
            "url": f"/api/documents/{self.pk}/file/",
        }


@receiver(post_delete, sender=Document)
def remove_file(sender, instance, **kwargs):
    # Deleting a document also deletes the file from disk.
    if instance.file:
        instance.file.delete(save=False)
