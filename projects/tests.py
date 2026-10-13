import json

from django.core.cache import cache
from django.test import Client, TestCase

from accounts.models import Profile, User

from .models import Interest, Project


class ProjectTests(TestCase):
    def setUp(self):
        cache.clear()
        self.farmer = User.objects.create_user("+263771111111", "pw-farm-2026!", full_name="Tendai Moyo", role="farmer")
        self.investor = User.objects.create_user("+447700900123", "pw-invest-2026!", full_name="Rudo Chikwanha", role="investor")
        for u in (self.farmer, self.investor):
            Profile.objects.create(user=u)
        base = dict(crop="Potatoes", province="Manicaland", area="Nyanga", size_ha="0.5",
                    summary="Highland potatoes.", share_price_usd=500, target_usd=2400, farmer=self.farmer)
        self.open = Project.objects.create(title="Half-Hectare Potatoes", status="open", milestone=1, **base)
        self.draft = Project.objects.create(title="Secret draft", status="draft", **base)

    def client_for(self, user):
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        c.get("/api/health/")
        return c

    def post(self, c, url, data):
        return c.post(url, data=json.dumps(data), content_type="application/json",
                      HTTP_X_CSRFTOKEN=c.cookies["csrftoken"].value)

    def test_investors_see_only_visible_projects(self):
        r = self.client_for(self.investor).get("/api/projects/")
        titles = [p["title"] for p in r.json()["projects"]]
        self.assertEqual(titles, ["Half-Hectare Potatoes"])

    def test_interest_toggles_and_ticks_step(self):
        c = self.client_for(self.investor)
        r = self.post(c, f"/api/projects/{self.open.pk}/interest/", {"interested": True})
        self.assertTrue(r.json()["project"]["interested"])
        self.assertEqual(r.json()["checklist"][3]["done"], True)  # "Pick a project you like"
        self.assertEqual(Interest.objects.count(), 1)
        self.post(c, f"/api/projects/{self.open.pk}/interest/", {"interested": False})
        self.assertEqual(Interest.objects.count(), 0)

    def test_hidden_project_and_non_investor_are_refused(self):
        c = self.client_for(self.investor)
        self.assertEqual(self.post(c, f"/api/projects/{self.draft.pk}/interest/", {"interested": True}).status_code, 404)
        f = self.client_for(self.farmer)
        self.assertEqual(self.post(f, f"/api/projects/{self.open.pk}/interest/", {"interested": True}).status_code, 403)

    def test_farmer_sees_own_projects(self):
        mine = self.client_for(self.farmer).get("/api/me/").json()["my_projects"]
        self.assertEqual([p["title"] for p in mine], ["Half-Hectare Potatoes"])  # the draft stays hidden

    def test_logged_out_is_refused(self):
        self.assertEqual(Client().get("/api/projects/").status_code, 401)
