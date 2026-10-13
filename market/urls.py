from django.urls import path

from . import api

urlpatterns = [
    path("prices/", api.prices),
    path("jobs/", api.jobs),
    path("jobs/<int:pk>/interest/", api.job_interest),
]
