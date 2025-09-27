from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AllSkillsView, HackathonCreateView, HackathonListView, HackathonRetrieveView,
    HackathonRegistrationView, InviteJudgeView, AcceptJudgeInvitationView,
    SubmissionViewSet, ReviewViewSet, ThemeViewSet, SubmitProjectView, JudgeHackathonsView,
    HackathonJudgesView, HackathonParticipantsView, OrganizerHackathonsView,
    JoinTeamView, HackathonIndividualParticipantsView, AvailableTeamsView,
    UserRegisteredHackathonsView, JudgeAllReviewsView, HackathonProjectsView,
    SubmissionProjectDetailView

)

router = DefaultRouter()
router.register(r'submissions', SubmissionViewSet, basename='submission')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'themes', ThemeViewSet, basename='theme')

urlpatterns = [
    path('', HackathonListView.as_view(), name='hackathon_list'),
    path('create/', HackathonCreateView.as_view(), name='hackathon_create'),
    path('my-registrations/', UserRegisteredHackathonsView.as_view(), name='user_registered_hackathons'),
    path('judge/hackathons/', JudgeHackathonsView.as_view(), name='judge_hackathons'),
    path('judge/reviews/', JudgeAllReviewsView.as_view(), name='judge_all_reviews'),
    path('organizer/hackathons/', OrganizerHackathonsView.as_view(), name='organizer_hackathons'),
    path('<int:hackathon_id>/', HackathonRetrieveView.as_view(), name='hackathon_retrieve'),
    path('<int:hackathon_id>/judges/', HackathonJudgesView.as_view(), name='hackathon_judges'),
    path('<int:hackathon_id>/participants/', HackathonParticipantsView.as_view(), name='hackathon_participants'),
    path('<int:hackathon_id>/individual-participants/', HackathonIndividualParticipantsView.as_view(), name='hackathon_individual_participants'),
    path('<int:hackathon_id>/available-teams/', AvailableTeamsView.as_view(), name='hackathon_available_teams'),
    path('<int:hackathon_id>/register/', HackathonRegistrationView.as_view(), name='hackathon_register'),
    path('<int:hackathon_id>/join-team/', JoinTeamView.as_view(), name='hackathon_join_team'),
    path('<int:hackathon_id>/invite-judge/', InviteJudgeView.as_view(), name='hackathon_invite_judge'),
    path('accept-judge-invitation/', AcceptJudgeInvitationView.as_view(), name='accept_judge_invitation'),
    path('<int:hackathon_id>/submit-project/', SubmitProjectView.as_view(), name='project_submit'),
    path('<int:hackathon_id>/projects/', HackathonProjectsView.as_view(), name='hackathon_projects'),
    path('submissions/<int:submission_id>/project/', SubmissionProjectDetailView.as_view(), name='submission_project_detail'),
    path('skills/', AllSkillsView.as_view(), name='all_skills'),
    path('<int:hackathon_id>/', include(router.urls)),
]