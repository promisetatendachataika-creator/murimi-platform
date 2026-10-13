from django.contrib import admin
from django.urls import include, path

from web.views import index

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/projects/", include("projects.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/market/", include("market.urls")),
    path("api/", include("accounts.urls")),
    path("", index),
]
