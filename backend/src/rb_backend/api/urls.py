"""Routes of the reader API, mounted at ``/api/v1/``."""

from django.urls import path

from rb_backend.api import views

app_name = "api"

urlpatterns = [
    path("papers/<str:key>/", views.PaperDetailView.as_view(), name="paper-detail"),
    path(
        "papers/<str:key>/credibility/",
        views.PaperCredibilityView.as_view(),
        name="paper-credibility",
    ),
    path("search/", views.SearchView.as_view(), name="search"),
    path("lookup/", views.LookupView.as_view(), name="lookup"),
    path(
        "lookup/requests/<uuid:request_id>/",
        views.LookupRequestView.as_view(),
        name="lookup-request",
    ),
]
