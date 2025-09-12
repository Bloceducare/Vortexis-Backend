from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationViewSet,
    NotificationPreferenceView,
    AdminNotificationViewSet,
    EmailNotificationViewSet,
    NotificationTemplateViewSet,
    CreateSingleNotificationView,
    CreateBulkNotificationView,
)

# Create routers
router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'admin/notifications', AdminNotificationViewSet, basename='admin-notifications')
router.register(r'admin/email-notifications', EmailNotificationViewSet, basename='admin-email-notifications')
router.register(r'admin/templates', NotificationTemplateViewSet, basename='admin-notification-templates')

urlpatterns = [
    path('', include(router.urls)),
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
    path('admin/create-single/', CreateSingleNotificationView.as_view(), name='create-single-notification'),
    path('admin/create-bulk/', CreateBulkNotificationView.as_view(), name='create-bulk-notification'),
]
