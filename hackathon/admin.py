from django.contrib import admin
from .models import Hackathon

# Register your models here.

@admin.register(Hackathon)
class HackathonAdmin(admin.ModelAdmin):
    list_display = ['title', 'venue', 'start_date', 'end_date', 'visibility', 'organization']
    list_filter = ['visibility', 'start_date', 'end_date', 'organization']
    search_fields = ['title', 'description', 'venue']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'banner_image', 'venue', 'details')
        }),
        ('Event Details', {
            'fields': ('start_date', 'end_date', 'grand_prize', 'min_team_size', 'max_team_size')
        }),
        ('Settings', {
            'fields': ('visibility', 'organization', 'skills', 'themes', 'judges')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )