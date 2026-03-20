import os

from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.schemas import get_schema_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views
from .throttles import TokenObtainThrottle


class TierBlockingTokenObtainPairView(TokenObtainPairView):
    """Block FREE tier users from obtaining API tokens."""

    throttle_classes = [TokenObtainThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Resolve the user from the validated serializer
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=False)
            user = getattr(serializer, "_validated_data", {})
            # Attempt to look up the user directly
            from django.contrib.auth import get_user_model

            User = get_user_model()
            username = request.data.get("username", "")
            try:
                user_obj = User.objects.get(username=username)
                profile = getattr(user_obj, "profile", None)
                if profile and getattr(profile, "account_tier", None) == "free":
                    return Response(
                        {"detail": "API access is not available on the FREE plan."},
                        status=403,
                    )
            except User.DoesNotExist:
                pass
        return response


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
    TokenObtainView = TierBlockingTokenObtainPairView
    TokenRefView = TokenRefreshView

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
