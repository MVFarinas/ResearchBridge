"""URL configuration: the Django admin and the reader API.

Every public view reads papers through :mod:`rb_backend.corpus.access` (the
licence-gated access layer), never through the models directly; the access
check in the test suite enforces it.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("rb_backend.api.urls")),
]
