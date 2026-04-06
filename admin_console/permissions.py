from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to authenticated superusers or admin users.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_superuser or request.user.is_admin)