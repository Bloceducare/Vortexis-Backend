from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to PlatformOwner or SystemAdmin.
    """
    def has_permission(self, request, view):
        return request.user and request.user.role in ['PlatformOwner','SystemAdmin']