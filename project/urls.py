from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, HackathonProjectDetailView

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'hackathons/(?P<hackathon_id>[^/.]+)/projects', ProjectViewSet, basename='hackathon-project')

urlpatterns = [
    path('hackathons/<int:hackathon_id>/projects/<int:project_id>/', HackathonProjectDetailView.as_view(), name='hackathon-project-detail'),
    path('', include(router.urls)),
] 