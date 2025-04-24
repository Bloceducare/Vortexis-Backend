from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateHackathonView, GetHackathonsView, GetHackathonView,
    UpdateHackathonView, DeleteHackathonView, RegisterForHackathonView,
    ProjectViewSet, ReviewViewSet, SubmissionViewSet, PrizeViewSet, 
    ThemeViewSet, RuleViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'prizes', PrizeViewSet, basename='prize')
router.register(r'themes', ThemeViewSet, basename='theme')
router.register(r'rules', RuleViewSet, basename='rule')

urlpatterns = [
    # Hackathon endpoints
    path('', GetHackathonsView.as_view(), name='get-hackathons'),
    path('create/', CreateHackathonView.as_view(), name='create-hackathon'),
    path('<int:hackathon_id>/', GetHackathonView.as_view(), name='get-hackathon'),
    path('<int:hackathon_id>/update/', UpdateHackathonView.as_view(), name='update-hackathon'),
    path('<int:hackathon_id>/delete/', DeleteHackathonView.as_view(), name='delete-hackathon'),
    path('<int:hackathon_id>/register/', RegisterForHackathonView.as_view(), name='register-hackathon'),
    
    # Nested endpoints for prizes, themes, and rules
    path('<int:hackathon_id>/', include(router.urls)),
]
