from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'hackathons/(?P<hackathon_id>[^/.]+)/projects', ProjectViewSet, basename='hackathon-project')

urlpatterns = [
    path('', include(router.urls)),
] 