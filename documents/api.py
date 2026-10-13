from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.api import error, login_required_json
from accounts.checklist import checklist

from .models import KINDS, Document, kinds_for

MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Recognise real file types from their first bytes, not from the name.
SIGNATURES = [
    (b"%PDF", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
]


def sniff(head):
    for magic, ctype, ext in SIGNATURES:
        if head.startswith(magic):
            return ctype, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"msf1"):
        return "image/heic", ".heic"  # iPhone photos
    return None, None


def listing(user):
    return {
        "documents": [d.as_dict() for d in user.documents.all()],
        "needed": [{"kind": k, "label": KINDS[k][0], "max": KINDS[k][2]} for k in kinds_for(user.role)],
        "checklist": checklist(user),
    }


@require_http_methods(["GET", "POST"])
@login_required_json
def documents(request):
    user = request.user
    if request.method == "GET":
        return JsonResponse(listing(user))

    kind = request.POST.get("kind", "")
    upload = request.FILES.get("file")
    if kind not in kinds_for(user.role):
        return error("That kind of document isn't needed for your account.")
    if not upload:
        return error("Choose a file to upload.")
    if upload.size > MAX_BYTES:
        return error("That file is over 10 MB. Try a smaller photo or a scan with lower quality.")
    if user.documents.filter(kind=kind).count() >= KINDS[kind][2]:
        return error(f"You can upload up to {KINDS[kind][2]} of these. Delete one first.")
    original_name = (upload.name or "file")[:200]
    head = upload.read(16)
    upload.seek(0)
    ctype, ext = sniff(head)
    if not ctype:
        return error("Please upload a photo (JPG, PNG, WebP or iPhone HEIC) or a PDF.")
    upload.name = "upload" + ext  # stored name gets the right extension; the real name is kept separately
    doc = Document.objects.create(owner=user, kind=kind, file=upload, content_type=ctype,
                                  original_name=original_name, size_bytes=upload.size)
    data = listing(user)
    data["created"] = doc.as_dict()
    return JsonResponse(data, status=201)


@require_http_methods(["DELETE"])
@login_required_json
def delete_document(request, pk):
    try:
        doc = request.user.documents.get(pk=pk)
    except Document.DoesNotExist:
        return error("That document doesn't exist.", status=404)
    if doc.status == Document.STATUS_ACCEPTED:
        return error("Accepted documents can't be deleted. Message us on WhatsApp if something is wrong.", status=400)
    doc.delete()
    return JsonResponse(listing(request.user))


@require_GET
def file_view(request, pk):
    """Open a file. Only its owner and Murimi staff may see it."""
    if not request.user.is_authenticated:
        raise Http404
    try:
        doc = Document.objects.get(pk=pk)
    except Document.DoesNotExist:
        raise Http404
    if doc.owner_id != request.user.pk and not request.user.is_staff:
        raise Http404  # 404 rather than 403, so nobody can probe which files exist
    response = FileResponse(doc.file.open("rb"), content_type=doc.content_type)
    response["Content-Disposition"] = f'inline; filename="{doc.original_name.replace(chr(34), "")}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
