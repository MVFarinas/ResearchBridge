"""URL configuration: only the Django admin until the reader API (Phase 4).

Any future public view must read papers through :mod:`rb_backend.corpus.access`
(the licence-gated access layer), never through the models directly.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
