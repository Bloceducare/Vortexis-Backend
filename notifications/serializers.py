from rest_framework import serializers
from .models import Notification, EmailNotification, NotificationPreference, NotificationTemplate


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for in-app notifications"""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'category', 'priority', 'is_read', 
            'created_at', 'data', 'action_url', 'action_text'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationListSerializer(serializers.ModelSerializer):
    """Serializer for notification list with read status"""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'category', 'priority', 'is_read', 
            'created_at', 'action_url', 'action_text'
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences"""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_notifications', 'email_account_updates', 'email_kyc_updates',
            'email_transaction_alerts', 'email_referral_updates', 'email_security_alerts',
            'email_promotions', 'in_app_notifications', 'in_app_account_updates',
            'in_app_kyc_updates', 'in_app_transaction_alerts', 'in_app_referral_updates',
            'in_app_security_alerts', 'in_app_promotions', 'sms_notifications',
            'sms_security_alerts', 'sms_transaction_alerts'
        ]


class EmailNotificationSerializer(serializers.ModelSerializer):
    """Serializer for email notifications"""
    
    class Meta:
        model = EmailNotification
        fields = [
            'id', 'subject', 'message', 'status', 'sent_at', 'error_message', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for notification templates"""
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'notification_type', 'subject', 'template_content',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class NotificationStatsSerializer(serializers.Serializer):
    """Serializer for notification statistics"""
    total_notifications = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    notifications_by_category = serializers.DictField()
    recent_notifications = NotificationListSerializer(many=True)


class CreateNotificationSerializer(serializers.Serializer):
    """Serializer for creating a single notification"""
    user_id = serializers.IntegerField(
        help_text="ID of the user to send notification to"
    )
    title = serializers.CharField(
        max_length=200,
        help_text="Notification title"
    )
    message = serializers.CharField(
        help_text="Notification message content"
    )
    category = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_CATEGORIES,
        default='system',
        help_text="Notification category"
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_CHOICES,
        default='normal',
        help_text="Notification priority level"
    )
    data = serializers.JSONField(
        required=False,
        help_text="Additional JSON data for rich notifications"
    )
    action_url = serializers.URLField(
        required=False,
        help_text="URL for action button"
    )
    action_text = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Text for action button"
    )
    send_email = serializers.BooleanField(
        default=True,
        help_text="Whether to send email notification"
    )
    send_in_app = serializers.BooleanField(
        default=True,
        help_text="Whether to create in-app notification"
    )


class BulkNotificationSerializer(serializers.Serializer):
    """Serializer for sending notifications to multiple users"""
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of user IDs to send notifications to"
    )
    title = serializers.CharField(
        max_length=200,
        help_text="Notification title"
    )
    message = serializers.CharField(
        help_text="Notification message content"
    )
    category = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_CATEGORIES,
        default='system',
        help_text="Notification category"
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_CHOICES,
        default='normal',
        help_text="Notification priority level"
    )
    data = serializers.JSONField(
        required=False,
        help_text="Additional JSON data for rich notifications"
    )
    action_url = serializers.URLField(
        required=False,
        help_text="URL for action button"
    )
    action_text = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Text for action button"
    )
    send_email = serializers.BooleanField(
        default=True,
        help_text="Whether to send email notification"
    )
    send_in_app = serializers.BooleanField(
        default=True,
        help_text="Whether to create in-app notification"
    )


class MarkAllReadSerializer(serializers.Serializer):
    """Serializer for marking all notifications as read"""
    category = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_CATEGORIES,
        required=False,
        help_text="Optional category filter for marking notifications as read"
    )


class NotificationFilterSerializer(serializers.Serializer):
    """Serializer for filtering notifications"""
    unread_only = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Filter to show only unread notifications"
    )
    category = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_CATEGORIES,
        required=False,
        help_text="Filter by notification category"
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_CHOICES,
        required=False,
        help_text="Filter by notification priority"
    )
    limit = serializers.IntegerField(
        required=False,
        default=50,
        min_value=1,
        max_value=100,
        help_text="Number of notifications to return (max 100)"
    )
