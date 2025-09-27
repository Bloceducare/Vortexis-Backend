from rest_framework import permissions

class IsOrganizer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_organizer

class IsJudge(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_judge

class IsModerator(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_moderator

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsOrganizationOrganizer(permissions.BasePermission):
    """
    Permission to check if user is the organizer of the specific organization.
    Requires 'organization_id' to be available in view kwargs.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        organization_id = view.kwargs.get('organization_id')
        if not organization_id:
            return False

        from organization.models import Organization
        try:
            organization = Organization.objects.get(id=organization_id)
            return organization.organizer == request.user
        except Organization.DoesNotExist:
            return False