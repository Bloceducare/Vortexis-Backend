from django.contrib import admin
from .models import Team, TeamInvitation

# Register your models here.

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'hackathon', 'organizer', 'member_count', 'created_at']
    list_filter = ['hackathon', 'created_at']
    search_fields = ['name', 'organizer__username', 'organizer__email']
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'team', 'invited_by', 'is_accepted', 'created_at', 'is_valid_status']
    list_filter = ['is_accepted', 'created_at', 'team__hackathon']
    search_fields = ['email', 'team__name', 'invited_by__username']
    readonly_fields = ['token', 'created_at', 'accepted_at']
    
    def is_valid_status(self, obj):
        return obj.is_valid()
    is_valid_status.short_description = 'Valid'
    is_valid_status.boolean = True