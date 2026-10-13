import json

from django.core.cache import cache
from django.test import Client, TestCase

from .models import User, normalize_phone

FARMER = {
    "role": "farmer",
    "full_name": "Tendai Moyo",
    "phone": "077 123 4567",
    "username": "Tendai_Moyo",
    "email": "",
    "password": "maize-season-2026",
    "consent": True,
    "profile": {"province": "Mashonaland East", "area": "Goromonzi", "size": "2.5",
                "crops": ["Maize", "Tomatoes"], "needs": ["Funding for inputs"]},
}


class AccountFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.c = Client(enforce_csrf_checks=True)
        self.c.get("/api/health/")  # sets the CSRF cookie, like the website does

    def call(self, method, url, data=None):
        token = self.c.cookies["csrftoken"].value
        return getattr(self.c, method)(url, data=json.dumps(data or {}), content_type="application/json",
                                       HTTP_X_CSRFTOKEN=token)

    def test_phone_normalising(self):
        self.assertEqual(normalize_phone("077 123 4567"), "+263771234567")
        self.assertEqual(normalize_phone("+44 7700 900123"), "+447700900123")
        self.assertEqual(normalize_phone("00447700900123"), "+447700900123")

    def test_register_login_logout_and_dashboard(self):
        r = self.call("post", "/api/auth/register/", FARMER)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["profile"]["size"], "2.5")
        self.assertEqual(self.c.get("/api/me/").status_code, 200)

        # Nobody can tick their own steps any more.
        r = self.call("post", "/api/me/steps/", {"step": 1, "done": True})
        self.assertEqual(r.status_code, 403)
        ticks = [i["done"] for i in self.c.get("/api/me/").json()["checklist"]]
        self.assertEqual(ticks, [False, False, False, False])

        self.call("post", "/api/auth/logout/")
        self.assertEqual(self.c.get("/api/me/").status_code, 401)

        r = self.call("post", "/api/auth/login/", {"phone": "+263771234567", "password": "wrong-password"})
        self.assertEqual(r.status_code, 400)
        r = self.call("post", "/api/auth/login/", {"phone": "0771234567", "password": FARMER["password"]})
        self.assertEqual(r.status_code, 200)

    def test_login_with_username_or_number(self):
        self.call("post", "/api/auth/register/", FARMER)
        self.assertEqual(User.objects.get().username, "tendai_moyo")  # stored lower-case
        self.call("post", "/api/auth/logout/")
        for who in ("tendai_moyo", "TENDAI_MOYO", "@tendai_moyo", "0771234567"):
            r = self.call("post", "/api/auth/login/", {"login": who, "password": FARMER["password"]})
            self.assertEqual(r.status_code, 200, who)
            self.call("post", "/api/auth/logout/")
        r = self.call("post", "/api/auth/login/", {"login": "tendai_moyo", "password": "wrong-password"})
        self.assertEqual(r.status_code, 400)

    def test_username_rules(self):
        self.assertEqual(self.call("post", "/api/auth/register/", dict(FARMER, username="")).json()["errors"]["username"][:6], "Choose")
        for bad in ("ab", "9lives", "has space", "admin"):
            r = self.call("post", "/api/auth/register/", dict(FARMER, username=bad))
            self.assertIn("username", r.json()["errors"], bad)
        self.call("post", "/api/auth/register/", FARMER)
        self.call("post", "/api/auth/logout/")
        twin = dict(FARMER, phone="0779999999")
        self.assertIn("taken", self.call("post", "/api/auth/register/", twin).json()["errors"]["username"])

    def test_existing_account_without_username_can_add_one(self):
        u = User.objects.create_user("+263772222222", "old-account-2026!", full_name="Old Timer", role="farmer")
        from .models import Profile
        Profile.objects.create(user=u, province="Harare", area="Harare", size_ha=1, details={"crops": ["Maize"], "needs": ["Transport"]})
        self.c.force_login(u)
        self.c.get("/api/health/")
        upd = {"full_name": "Old Timer", "phone": "+263772222222", "username": "", "consent": True,
               "profile": {"province": "Harare", "area": "Harare", "size": "1", "crops": ["Maize"], "needs": ["Transport"]}}
        self.assertEqual(self.call("patch", "/api/me/", upd).status_code, 200)  # blank is fine for old accounts
        r = self.call("patch", "/api/me/", dict(upd, username="old_timer"))
        self.assertEqual(r.json()["user"]["username"], "old_timer")

    def test_duplicate_phone_and_bad_answers(self):
        self.call("post", "/api/auth/register/", FARMER)
        self.call("post", "/api/auth/logout/")
        bad = dict(FARMER, profile=dict(FARMER["profile"], province="Atlantis", crops=[]))
        r = self.call("post", "/api/auth/register/", bad)
        self.assertEqual(r.status_code, 400)
        errs = r.json()["errors"]
        self.assertIn("phone", errs)
        self.assertIn("province", errs)
        self.assertIn("crops", errs)

    def test_weak_password_rejected(self):
        r = self.call("post", "/api/auth/register/", dict(FARMER, password="12345678"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.json()["errors"])

    def test_csrf_required(self):
        r = self.c.post("/api/auth/register/", data=json.dumps(FARMER), content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_login_attempts_are_limited(self):
        self.call("post", "/api/auth/register/", FARMER)
        self.call("post", "/api/auth/logout/")
        codes = [self.call("post", "/api/auth/login/", {"phone": "0771234567", "password": "nope-nope"}).status_code
                 for _ in range(6)]
        self.assertEqual(codes[-1], 429)

    def test_driver_marking_a_job_ticks_the_step(self):
        drv = {"role": "driver", "full_name": "Farai Dube", "phone": "0773333333", "username": "farai_d",
               "password": "long-haul-2026", "consent": True,
               "profile": {"area": "Chitungwiza", "province": "Harare", "trucks": ["3 t"], "count": "1",
                           "cold": "No", "reach": "Local"}}
        self.assertEqual(self.call("post", "/api/auth/register/", drv).status_code, 201, )
        from market.models import HaulJob
        job = HaulJob.objects.create(load="2 t maize", pickup_area="Goromonzi", pickup_province="Mashonaland East",
                                     dropoff="Mbare Musika", truck_size="3 t", status="open")
        r = self.call("post", f"/api/market/jobs/{job.pk}/interest/", {"interested": True})
        self.assertEqual(r.json()["checklist"][3]["done"], True)
        self.assertEqual(self.call("post", "/api/me/saved/", {"id": "evil", "saved": True}).status_code, 400)

    def test_staff_ticks_and_verification_tick_steps(self):
        from .models import Profile
        self.call("post", "/api/auth/register/", FARMER)
        u = User.objects.get()
        u.steps = {"visit": True}
        u.save()
        p = Profile.objects.get(); p.verification_status = "verified"; p.save()
        ticks = [i["done"] for i in self.c.get("/api/me/").json()["checklist"]]
        self.assertEqual(ticks, [False, False, True, True])  # visit (staff) + verified (auto)

    def test_verification_status_reaches_the_person(self):
        from .models import Profile
        self.call("post", "/api/auth/register/", FARMER)
        v = self.c.get("/api/me/").json()["verification"]
        self.assertEqual(v["status"], "pending")
        p = Profile.objects.get()
        p.verification_status = "verified"
        p.message_to_user = "Welcome aboard!"
        p.save()
        v = self.c.get("/api/me/").json()["verification"]
        self.assertEqual((v["status"], v["label"], v["message"]), ("verified", "Verified", "Welcome aboard!"))
        self.assertIsNotNone(v["changed_at"])
        # Editing only the name keeps them verified...
        self.assertEqual(self.call("patch", "/api/me/", dict(FARMER, full_name="Tendai T. Moyo")).json()["verification"]["status"], "verified")
        # ...but changing the farm itself sends them back for checks.
        moved = dict(FARMER, profile=dict(FARMER["profile"], size="4"))
        self.assertEqual(self.call("patch", "/api/me/", moved).json()["verification"]["status"], "pending")

    def test_edit_details_and_change_password(self):
        self.call("post", "/api/auth/register/", FARMER)
        upd = dict(FARMER, full_name="Tendai M. Moyo", password="new-password-for-tendai")
        r = self.call("patch", "/api/me/", upd)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["user"]["full_name"], "Tendai M. Moyo")
        self.assertEqual(self.c.get("/api/me/").status_code, 200)  # still logged in
        self.assertTrue(User.objects.get().check_password("new-password-for-tendai"))


class AdminFixTests(TestCase):
    def setUp(self):
        cache.clear()
        self.boss = User.objects.create_superuser("+263700000001", "Admin-pass-2026!")
        self.c = Client(HTTP_HOST="localhost")
        self.c.force_login(self.boss)

    def test_admin_added_user_can_log_in_and_number_is_tidied(self):
        r = self.c.post("/admin/accounts/user/add/", {
            "phone": "0718989114", "username": "promise_t", "full_name": "Promise Test", "role": "investor",
            "password1": "invest-at-home-26", "password2": "invest-at-home-26", "_save": "Save",
            "profile-TOTAL_FORMS": "0", "profile-INITIAL_FORMS": "0", "profile-MIN_NUM_FORMS": "0", "profile-MAX_NUM_FORMS": "1",
            "documents-TOTAL_FORMS": "0", "documents-INITIAL_FORMS": "0", "documents-MIN_NUM_FORMS": "0", "documents-MAX_NUM_FORMS": "1000"})
        self.assertEqual(r.status_code, 302, r.content[:2000])
        self.assertEqual(User.objects.get(full_name="Promise Test").phone, "+263718989114")
        site = Client(enforce_csrf_checks=True)
        site.get("/api/health/")
        r = site.post("/api/auth/login/", data=json.dumps({"login": "071 898 9114", "password": "invest-at-home-26"}),
                      content_type="application/json", HTTP_X_CSRFTOKEN=site.cookies["csrftoken"].value)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Client(HTTP_HOST="localhost").login(username="Promise_T", password="invest-at-home-26"))  # admin log-in too

    def test_view_as_logs_in_as_the_person(self):
        farmer = User.objects.create_user("+263771111111", "farm-pass-2026!", full_name="Tendai Moyo", role="farmer")
        page = self.c.get(f"/admin/accounts/user/{farmer.pk}/view-as/")
        self.assertContains(page, "View the site as Tendai Moyo")
        r = self.c.post(f"/admin/accounts/user/{farmer.pk}/view-as/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/api/me/").json()["user"]["full_name"], "Tendai Moyo")

    def test_view_as_refused_for_staff_and_non_superusers(self):
        r = self.c.post(f"/admin/accounts/user/{self.boss.pk}/view-as/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/api/me/").json()["user"]["role"], "")  # still the boss
        helper = User.objects.create_user("+263700000002", "Helper-pass-2026!", full_name="Helper", is_staff=True)
        farmer = User.objects.create_user("+263771111112", "farm-pass-2026!", full_name="F", role="farmer")
        h = Client(HTTP_HOST="localhost"); h.force_login(helper)
        self.assertEqual(h.post(f"/admin/accounts/user/{farmer.pk}/view-as/").status_code, 403)
