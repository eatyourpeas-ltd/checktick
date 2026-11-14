from django.urls import path

from . import views

app_name = "appraisal"


urlpatterns = [
    path("", views.caseload, name="caseload"),
    path("relationships/new/", views.relationship_create, name="relationship_create"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("adopt-instrument/", views.adopt_instrument, name="adopt_instrument"),
    path(
        "relationships/<int:pk>/report/",
        views.report_view,
        name="report_view",
    ),
    path(
        "relationships/<int:pk>/report/release/",
        views.report_release,
        name="report_release",
    ),
    path(
        "relationships/<int:pk>/exceptions/",
        views.exception_reviews,
        name="exception_reviews",
    ),
    path(
        "relationships/<int:pk>/exceptions/raise/",
        views.exception_review_raise,
        name="exception_review_raise",
    ),
    path(
        "relationships/<int:pk>/exceptions/<int:review_id>/decide/",
        views.exception_review_decide,
        name="exception_review_decide",
    ),
    path(
        "relationships/<int:pk>/exceptions/<int:review_id>/linkage/",
        views.exception_review_linkage,
        name="exception_review_linkage",
    ),
]
