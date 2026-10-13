"""Checks for WhatsApp codes: confirming a number and resetting a forgotten password."""
import io
import json
import urllib.error
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import PhoneCode, User
from .tests import FARMER


@override_settings(DEBUG=True, MURIMI_CODE_SENDER="console")
class PhoneCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.c = Client(enforce_csrf_checks=True)
        self.c.get("/api/health/")

    def call(self, url, data=None, method="post", client=None):
        c = client or self.c
        return getattr(c, method)(url, data=json.dumps(data or {}), content_type="application/json",
                                  HTTP_X_CSRFTOKEN=c.cookies["csrftoken"].value)

    def signup(self):
        with mock.patch("builtins.print"):
            r = self.call("/api/auth/register/", FARMER)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertFalse(r.json()["user"]["phone_verified"])
        return User.objects.get(username="tendai_moyo")

    def send(self, url="/api/me/phone/send-code/", data=None):
        with mock.patch("builtins.print") as printed:
            r = self.call(url, data)
        return r, printed

    def age_last_code(self, seconds=61):
        PhoneCode.objects.update(created_at=timezone.now() - timedelta(seconds=seconds))

    def test_confirm_number(self):
        self.signup()
        stranger = Client()
        self.assertEqual(stranger.post("/api/me/phone/send-code/").status_code, 401)  # must be logged in
        r, printed = self.send()
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        code = body["test_code"]
        self.assertTrue(body["test_mode"])
        self.assertEqual(body["to"], "+263 ••• ••4567")
        self.assertIn(code, printed.call_args[0][0])               # shown in the server window
        self.assertNotIn(code, PhoneCode.objects.get().code_hash)  # never stored as-is

        wrong = "000000" if code != "000000" else "111111"
        r = self.call("/api/me/phone/confirm/", {"code": wrong})
        self.assertEqual(r.status_code, 400)
        self.assertIn("4 tries left", r.json()["error"])

        r = self.call("/api/me/phone/confirm/", {"code": code[:3] + " " + code[3:]})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["user"]["phone_verified"])
        # A code only works once.
        self.assertEqual(self.call("/api/me/phone/confirm/", {"code": code}).status_code, 400)
        # Already confirmed: no new code is sent.
        r, _ = self.send()
        self.assertTrue(r.json()["already_confirmed"])

    def test_resend_wait_expiry_and_lockout(self):
        self.signup()
        r, _ = self.send()
        first = r.json()["test_code"]
        r, _ = self.send()
        self.assertEqual(r.status_code, 429)
        self.assertIn("retry_in", r.json())

        self.age_last_code()
        r, _ = self.send()
        second = r.json()["test_code"]
        if first != second:  # only the newest code works
            self.assertEqual(self.call("/api/me/phone/confirm/", {"code": first}).status_code, 400)

        for _ in range(5):
            self.call("/api/me/phone/confirm/", {"code": "999999" if second != "999999" else "888888"})
        r = self.call("/api/me/phone/confirm/", {"code": second})
        self.assertIn("Too many wrong tries", r.json()["error"])

        self.age_last_code()
        r, _ = self.send()
        code = r.json()["test_code"]
        PhoneCode.objects.filter(used_at__isnull=True).update(expires_at=timezone.now())
        r = self.call("/api/me/phone/confirm/", {"code": code})
        self.assertIn("expired", r.json()["error"])

    def test_hourly_limit(self):
        self.signup()
        for _ in range(5):
            self.age_last_code()
            r, _ = self.send()
            self.assertEqual(r.status_code, 200)
        self.age_last_code()
        r, _ = self.send()
        self.assertEqual(r.status_code, 429)
        self.assertIn("an hour", r.json()["error"])

    def test_new_number_must_be_confirmed_again(self):
        user = self.signup()
        user.phone_verified_at = timezone.now()
        user.save()
        data = dict(FARMER, phone="+263 77 999 0000", password="")
        r = self.call("/api/me/", data, method="patch")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["user"]["phone_verified"])

    def test_forgot_and_reset_password(self):
        self.signup()
        self.call("/api/auth/logout/")
        # Unknown accounts get the same answer, without a code.
        r, printed = self.send("/api/auth/password/forgot/", {"login": "nobody_here"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("test_code", r.json())
        printed.assert_not_called()

        r, _ = self.send("/api/auth/password/forgot/", {"login": "Tendai_Moyo"})
        body = r.json()
        self.assertNotIn("to", body)
        code = body["test_code"]

        r = self.call("/api/auth/password/reset/", {"login": "0771234567", "code": code, "password": "123"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.json()["errors"])

        r = self.call("/api/auth/password/reset/", {"login": "0771234567", "code": code,
                                                    "password": "new-harvest-2027"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["user"]["phone_verified"])  # the code proved they own the number
        self.assertEqual(self.c.get("/api/me/").status_code, 200)  # logged in

        self.call("/api/auth/logout/")
        bad = self.call("/api/auth/login/", {"login": "tendai_moyo", "password": FARMER["password"]})
        self.assertEqual(bad.status_code, 400)
        ok = self.call("/api/auth/login/", {"login": "tendai_moyo", "password": "new-harvest-2027"})
        self.assertEqual(ok.status_code, 200)
        # The reset code can't be used twice.
        r = self.call("/api/auth/password/reset/", {"login": "tendai_moyo", "code": code,
                                                    "password": "another-pass-2028"})
        self.assertEqual(r.status_code, 400)

    @override_settings(DEBUG=False)
    def test_codes_never_shown_on_the_live_site(self):
        self.signup()
        r, _ = self.send()
        self.assertNotIn("test_code", r.json())

    @override_settings(MURIMI_CODE_SENDER="whatsapp", WHATSAPP_TOKEN="tok", WHATSAPP_PHONE_NUMBER_ID="123",
                       WHATSAPP_TEMPLATE="murimi_code", WHATSAPP_TEMPLATE_LANG="en", WHATSAPP_API_VERSION="v21.0")
    def test_whatsapp_mode(self):
        self.signup()
        sent = {}

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def fake_urlopen(req, timeout):
            sent["url"] = req.full_url
            sent["auth"] = req.get_header("Authorization")
            sent["body"] = json.loads(req.data)
            return Resp(b'{"messages":[{"id":"x"}]}')

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            r = self.call("/api/me/phone/send-code/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotIn("test_code", r.json())
        self.assertEqual(sent["url"], "https://graph.facebook.com/v21.0/123/messages")
        self.assertEqual(sent["auth"], "Bearer tok")
        self.assertEqual(sent["body"]["to"], "263771234567")
        code = sent["body"]["template"]["components"][0]["parameters"][0]["text"]
        self.assertEqual(self.call("/api/me/phone/confirm/", {"code": code}).status_code, 200)

    @override_settings(MURIMI_CODE_SENDER="whatsapp", WHATSAPP_TOKEN="tok", WHATSAPP_PHONE_NUMBER_ID="123")
    def test_whatsapp_failure_is_explained(self):
        self.signup()
        err = urllib.error.HTTPError("u", 400, "bad", {}, io.BytesIO(b'{"error":"nope"}'))
        with mock.patch("urllib.request.urlopen", side_effect=err), self.assertLogs("murimi.codes", "ERROR"):
            r = self.call("/api/me/phone/send-code/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("couldn't send", r.json()["error"])
        self.assertEqual(PhoneCode.objects.count(), 0)  # a failed send doesn't count
