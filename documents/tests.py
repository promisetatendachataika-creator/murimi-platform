import json
import shutil
import tempfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from accounts.models import User

from .models import Document

PDF = b"%PDF-1.4\n%fake test pdf\n"
JPG = b"\xff\xd8\xff\xe0" + b"0" * 200
TMP = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TMP)
class DocumentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.land = User.objects.create_user("+263771111111", "land-pass-2026!", full_name="Kromise", role="landowner")
        self.other = User.objects.create_user("+263772222222", "farm-pass-2026!", full_name="Tendai", role="farmer")
        self.boss = User.objects.create_superuser("+263700000001", "Admin-pass-2026!")
        self.c = self.client_for(self.land)

    def client_for(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        c.get("/api/health/")
        return c

    def upload(self, c, kind, content, name="deed.pdf"):
        return c.post("/api/documents/", {"kind": kind, "file": SimpleUploadedFile(name, content)},
                      HTTP_X_CSRFTOKEN=c.cookies["csrftoken"].value)

    def test_upload_lists_and_ticks_step(self):
        r = self.upload(self.c, "title_deed", PDF, "My Offer Letter.pdf")
        self.assertEqual(r.status_code, 201, r.content)
        d = r.json()
        self.assertEqual(d["created"]["name"], "My Offer Letter.pdf")
        self.assertEqual(d["created"]["content_type"], "application/pdf")
        self.assertEqual(d["checklist"][1]["done"], True)  # "Upload your title deed or offer letter"
        self.assertIn("title_deed", [n["kind"] for n in d["needed"]])
        self.assertNotIn("drivers_licence", [n["kind"] for n in d["needed"]])

    def test_wrong_type_wrong_kind_and_too_big_are_refused(self):
        self.assertEqual(self.upload(self.c, "title_deed", b"MZ\x90\x00 not a pdf", "virus.pdf").status_code, 400)
        self.assertEqual(self.upload(self.c, "drivers_licence", PDF).status_code, 400)
        big = b"%PDF" + b"0" * (10 * 1024 * 1024 + 1)
        self.assertEqual(self.upload(self.c, "title_deed", big).status_code, 400)

    def test_only_owner_and_staff_can_open(self):
        doc_id = self.upload(self.c, "land_photo", JPG, "field.jpg").json()["created"]["id"]
        url = f"/api/documents/{doc_id}/file/"
        self.assertEqual(self.c.get(url).status_code, 200)
        self.assertEqual(self.client_for(self.other).get(url).status_code, 404)
        self.assertEqual(Client().get(url).status_code, 404)
        boss = Client(HTTP_HOST="localhost"); boss.force_login(self.boss)
        self.assertEqual(boss.get(url).status_code, 200)

    def test_delete_own_but_not_accepted(self):
        d1 = self.upload(self.c, "land_photo", JPG, "a.jpg").json()["created"]["id"]
        d2 = self.upload(self.c, "land_photo", JPG, "b.jpg").json()["created"]["id"]
        tok = self.c.cookies["csrftoken"].value
        self.assertEqual(self.c.delete(f"/api/documents/{d1}/", HTTP_X_CSRFTOKEN=tok).status_code, 200)
        Document.objects.filter(pk=d2).update(status="accepted")
        self.assertEqual(self.c.delete(f"/api/documents/{d2}/", HTTP_X_CSRFTOKEN=tok).status_code, 400)
        other = self.client_for(self.other)
        self.assertEqual(other.delete(f"/api/documents/{d2}/", HTTP_X_CSRFTOKEN=other.cookies["csrftoken"].value).status_code, 404)

    def test_rejected_document_removes_the_tick(self):
        doc_id = self.upload(self.c, "title_deed", PDF).json()["created"]["id"]
        Document.objects.filter(pk=doc_id).update(status="rejected")
        self.assertFalse(self.c.get("/api/me/").json()["checklist"][1]["done"])

    def test_admin_pages_open(self):
        self.upload(self.c, "title_deed", PDF)
        boss = Client(HTTP_HOST="localhost"); boss.force_login(self.boss)
        self.assertEqual(boss.get("/admin/documents/document/").status_code, 200)
        self.assertContains(boss.get(f"/admin/accounts/user/{self.land.pk}/change/"), "Open PDF")
