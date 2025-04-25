from django.urls import path
from .views import CreateTeamView, GetTeamsView, GetTeamView, UpdateTeamView, AddMemberView, RemoveMemberView, DeleteTeamView

urlpatterns = [
    path('create', CreateTeamView.as_view(), name='create_team'),
    path('get', GetTeamsView.as_view(), name='get_teams'),
    path('get/<int:team_id>', GetTeamView.as_view(), name='get_team'),
    path('update/<int:team_id>', UpdateTeamView.as_view(), name='update_team'),
    path('add-member/<int:team_id>', AddMemberView.as_view(), name='add_member'),
    path('remove-member/<int:team_id>', RemoveMemberView.as_view(), name='remove_member'),
    path('delete/<int:team_id>', DeleteTeamView.as_view(), name='delete_team'),
]