from django.urls import path

from . import api

urlpatterns = [
    path("", api.documents),
    path("<int:pk>/", api.delete_document),
    path("<int:pk>/file/", api.file_view),
]
