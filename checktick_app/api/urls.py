import os

from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views


# Custom token views without throttling for tests
class TestTokenObtainPairView(TokenObtainPairView):
    throttle_classes = []


class TestTokenRefreshView(TokenRefreshView):
    throttle_classes = []


# Use non-throttled views during tests
if os.environ.get("PYTEST_CURRENT_TEST"):
    TokenObtainView = TestTokenObtainPairView
    TokenRefView = TestTokenRefreshView
else:
    TokenObtainView = TokenObtainPairView
    TokenRefView = TokenRefreshView

router = DefaultRouter()
router.register(r"surveys", views.SurveyViewSet, basename="survey")
router.register(r"datasets", views.DataSetViewSet, basename="dataset")
router.register(r"users", views.UserViewSet, basename="user")
router.register(
    r"org-memberships", views.OrganizationMembershipViewSet, basename="org-membership"
)
router.register(
    r"survey-memberships", views.SurveyMembershipViewSet, basename="survey-membership"
)
router.register(r"scoped-users", views.ScopedUserViewSet, basename="scoped-user")
router.register(
    r"question-group-templates",
    views.PublishedQuestionGroupViewSet,
    basename="question-group-template",
)
router.register(r"recovery", views.RecoveryViewSet, basename="recovery")

urlpatterns = [
    path("health", views.healthcheck, name="healthcheck"),
    path("token", TokenObtainView.as_view(), name="token_obtain_pair"),
    path("token/refresh", TokenRefView.as_view(), name="token_refresh"),
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
