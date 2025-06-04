from django.urls import path
from .views import (
    CreateOrganizationView, UpdateOrganizationView, DeleteOrganizationView,
    GetOrganizationView, GetOrganizationsView, GetUnapprovedOrganizationsView,
    ApproveOrganizationView, AddModeratorView, RemoveModeratorView
)

urlpatterns = [
    path('create/', CreateOrganizationView.as_view(), name='create_organization'),
    path('update/<int:organization_id>/', UpdateOrganizationView.as_view(), name='update_organization'),
    path('delete/<int:organization_id>/', DeleteOrganizationView.as_view(), name='delete_organization'),
    path('get/<int:organization_id>/', GetOrganizationView.as_view(), name='get_organization'),
    path('get-all/', GetOrganizationsView.as_view(), name='get_organizations'),
    path('get-unapproved/', GetUnapprovedOrganizationsView.as_view(), name='get_unapproved_organizations'),
    path('approve/<int:organization_id>/', ApproveOrganizationView.as_view(), name='approve_organization'),
    path('add-moderator/<int:organization_id>/', AddModeratorView.as_view(), name='add_moderator'),
    path('remove-moderator/<int:organization_id>/', RemoveModeratorView.as_view(), name='remove_moderator'),
]