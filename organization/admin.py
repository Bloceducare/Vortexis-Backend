from django.contrib import admin
from .models import Organization, ModeratorInvitation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'organizer', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['name', 'organizer__username']


@admin.register(ModeratorInvitation)
class ModeratorInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'organization', 'inviter', 'status', 'created_at', 'expires_at']
    list_filter = ['status', 'created_at']
    search_fields = ['email', 'organization__name', 'inviter__username']
    readonly_fields = ['token', 'created_at', 'expires_at']