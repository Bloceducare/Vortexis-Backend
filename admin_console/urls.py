from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    HackathonViewSet,
    SubmissionViewSet,
    OrganizationViewSet,
    AnalyticsView,
    LogsView,
    generate_2fa_qr,
    PlatformSettingViewSet
)

# Create a router for viewsets
router = DefaultRouter()
router.register("users", UserViewSet, basename="console-users")
router.register("hackathons", HackathonViewSet, basename="console-hackathons")
router.register("submissions", SubmissionViewSet, basename="console-submissions")
router.register("organizations", OrganizationViewSet, basename="console-organizations")
router.register("settings", PlatformSettingViewSet, basename="console-settings")

# Add all router URLs
urlpatterns = [
    path("", include(router.urls)),
    path("analytics/", AnalyticsView.as_view(), name="admin-analytics"),
    path("logs/", LogsView.as_view(), name="admin-logs"),
    path("2fa/qr/", generate_2fa_qr, name="admin-2fa-qr"),
]