from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to superusers or admin users.
    """
    def has_permission(self, request, view):
        return request.user and (request.user.is_superuser or request.user.is_admin)