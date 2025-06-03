from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HackathonCreateView, HackathonListView, HackathonRetrieveView,
    RegisterForHackathonView, InviteJudgeView, ProjectViewSet,
    SubmissionViewSet, ReviewViewSet, PrizeViewSet, ThemeViewSet, RuleViewSet,
    SubmitProjectView
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'prizes', PrizeViewSet, basename='prize')
router.register(r'themes', ThemeViewSet, basename='theme')
router.register(r'rules', RuleViewSet, basename='rule')

urlpatterns = [
    path('', HackathonListView.as_view(), name='hackathon_list'),
    path('create/', HackathonCreateView.as_view(), name='hackathon_create'),
    path('<int:hackathon_id>/', HackathonRetrieveView.as_view(), name='hackathon_retrieve'),
    path('<int:hackathon_id>/register/', RegisterForHackathonView.as_view(), name='hackathon_register'),
    path('<int:hackathon_id>/invite-judge/', InviteJudgeView.as_view(), name='hackathon_invite_judge'),
    path('projects/<int:project_id>/submit/', SubmitProjectView.as_view(), name='project_submit'),
    path('<int:hackathon_id>/', include(router.urls)),
]