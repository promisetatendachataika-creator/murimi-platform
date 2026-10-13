from django.urls import path

from . import api

urlpatterns = [
    path("", api.project_list),
    path("<int:pk>/interest/", api.set_interest),
]
