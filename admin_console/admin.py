from django.contrib import admin
from .models import Review, AuditLog, PlatformSetting

# Register your models here.

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'submission', 'judge', 'overall_score', 'created_at']
    list_filter = ['created_at', 'judge']
    search_fields = ['judge__username', 'submission__project__title', 'review']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'admin', 'action', 'target_type', 'target_id', 'timestamp']
    list_filter = ['action', 'target_type', 'timestamp']
    search_fields = ['admin__username', 'action', 'target_type']
    readonly_fields = ['timestamp']

@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ['id', 'key', 'value', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at']
