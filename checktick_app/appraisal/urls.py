from django.urls import path

from . import views

app_name = "appraisal"


urlpatterns = [
    path("", views.caseload, name="caseload"),
    path("relationships/new/", views.relationship_create, name="relationship_create"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("adopt-instrument/", views.adopt_instrument, name="adopt_instrument"),
]
