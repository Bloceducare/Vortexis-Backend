from django.urls import path
from .views import CreateOrganizationView, AddModeratorView, ApproveOrganizationView, GetOrganizationsView, GetOrganizationView, UpdateOrganizationView

urlpatterns = [
    path('create', CreateOrganizationView.as_view(), name='create_organization'),
    path('get', GetOrganizationsView.as_view(), name='get_organizations'),
    path('get/<int:organization_id>', GetOrganizationView.as_view(), name='get_organization'),
    path('add-moderator/<int:organization_id>', AddModeratorView.as_view(), name='add_moderator'),
    path('approve/<int:organization_id>', ApproveOrganizationView.as_view(), name='approve_organization'),
    path('update/<int:organization_id>', UpdateOrganizationView.as_view(), name='update_organization'),
]