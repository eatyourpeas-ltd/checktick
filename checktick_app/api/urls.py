from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view

from . import views


router = DefaultRouter()
router.register(r"surveys", views.SurveyViewSet, basename="survey")
router.register(r"datasets", views.DataSetViewSet, basename="dataset")
router.register(
    r"question-group-templates",
    views.PublishedQuestionGroupViewSet,
    basename="question-group-template",
)

urlpatterns = [
    path("health", views.healthcheck, name="healthcheck"),
    # OpenAPI schema (JSON)
    path(
        "schema",
        get_schema_view(
            title="CheckTick API",
            description="OpenAPI schema for the CheckTick API",
            version="1.0.0",
            permission_classes=[AllowAny],
        ),
        name="openapi-schema",
    ),
    # Embedded Swagger UI (CSP exempt)
    path("docs", views.swagger_ui, name="swagger-ui"),
    # Embedded ReDoc UI (CSP exempt)
    path("redoc", views.redoc_ui, name="redoc-ui"),
    path("", include(router.urls)),
]
