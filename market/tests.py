import json
from datetime import date, timedelta

from django.core.cache import cache
from django.test import Client, TestCase

from accounts.models import Profile, User

from .models import HaulJob, JobInterest, PriceReport, latest_prices


class MarketTests(TestCase):
    def setUp(self):
        cache.clear()
        self.driver = User.objects.create_user("+263773333333", "long-haul-2026!", full_name="Farai Dube", role="driver")
        Profile.objects.create(user=self.driver, province="Harare", area="Chitungwiza",
                               details={"trucks": ["3 t", "8 t"], "count": 2, "cold": "No", "reach": "Nationwide"})
        self.farmer = User.objects.create_user("+263771111111", "farm-pass-2026!", full_name="Tendai", role="farmer")
        Profile.objects.create(user=self.farmer)
        base = dict(pickup_area="Goromonzi", pickup_province="Mashonaland East", dropoff="Mbare Musika")
        self.fits = HaulJob.objects.create(load="2.5 t potatoes", truck_size="3 t", status="open", **base)
        self.too_big = HaulJob.objects.create(load="28 t maize", truck_size="30 t", status="open", **base)
        self.cold = HaulJob.objects.create(load="Tomatoes", truck_size="3 t", needs_cold=True, status="open", **base)
        self.draft = HaulJob.objects.create(load="Hidden", truck_size="3 t", status="draft", **base)

    def client_for(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        c.get("/api/health/")
        return c

    def post(self, c, url, data):
        return c.post(url, data=json.dumps(data), content_type="application/json",
                      HTTP_X_CSRFTOKEN=c.cookies["csrftoken"].value)

    def test_latest_prices_with_change(self):
        PriceReport.objects.create(crop="Potatoes", unit="15 kg pocket", price_usd="6.00", date=date.today() - timedelta(days=1))
        PriceReport.objects.create(crop="Potatoes", unit="15 kg pocket", price_usd="6.50", date=date.today())
        PriceReport.objects.create(crop="Maize", unit="per tonne", price_usd="330", date=date.today())
        items = {p["crop"]: p for p in latest_prices()}
        self.assertEqual((items["Potatoes"]["price_usd"], items["Potatoes"]["previous_usd"]), ("6.50", "6.00"))
        self.assertIsNone(items["Maize"]["previous_usd"])
        self.assertEqual(len(self.client_for(self.farmer).get("/api/market/prices/").json()["prices"]), 2)

    def test_driver_sees_only_jobs_that_fit(self):
        d = self.client_for(self.driver).get("/api/market/jobs/").json()
        self.assertEqual([j["load"] for j in d["jobs"]], ["2.5 t potatoes"])  # not 30 t, not refrigerated, not draft
        self.assertEqual(d["other_open"], 2)

    def test_interest_and_assignment(self):
        c = self.client_for(self.driver)
        r = self.post(c, f"/api/market/jobs/{self.fits.pk}/interest/", {"interested": True}).json()
        self.assertTrue(r["jobs"][0]["interested"])
        self.assertTrue(r["checklist"][3]["done"])
        self.assertEqual(JobInterest.objects.count(), 1)
        HaulJob.objects.filter(pk=self.fits.pk).update(driver=self.driver, status="assigned")
        d = c.get("/api/market/jobs/").json()
        self.assertEqual([j["load"] for j in d["mine"]], ["2.5 t potatoes"])
        self.assertEqual(d["jobs"], [])  # no longer open

    def test_non_drivers_refused(self):
        f = self.client_for(self.farmer)
        self.assertEqual(f.get("/api/market/jobs/").status_code, 403)
        self.assertEqual(self.post(f, f"/api/market/jobs/{self.fits.pk}/interest/", {"interested": True}).status_code, 403)
        self.assertEqual(Client().get("/api/market/prices/").status_code, 401)

    def test_admin_pages_open(self):
        boss = User.objects.create_superuser("+263700000001", "Admin-pass-2026!")
        c = Client(HTTP_HOST="localhost"); c.force_login(boss)
        for url in ("/admin/market/pricereport/", "/admin/market/pricereport/add/", "/admin/market/hauljob/",
                    f"/admin/market/hauljob/{self.fits.pk}/change/"):
            self.assertEqual(c.get(url).status_code, 200, url)
