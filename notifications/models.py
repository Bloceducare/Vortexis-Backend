from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
import uuid

User = get_user_model()


class NotificationTemplate(models.Model):
    """Template for notifications"""
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('in_app', 'In-App'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    subject = models.CharField(max_length=200, blank=True)
    template_content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.notification_type})"


class Notification(models.Model):
    """In-app notification model"""
    NOTIFICATION_CATEGORIES = [
        ('account', 'Account'),
        ('kyc', 'KYC'),
        ('transaction', 'Transaction'),
        ('referral', 'Referral'),
        ('security', 'Security'),
        ('system', 'System'),
        ('promotion', 'Promotion'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=NOTIFICATION_CATEGORIES, default='system')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Additional data for rich notifications
    data = models.JSONField(default=dict, blank=True)
    action_url = models.URLField(blank=True, null=True)
    action_text = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'category']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        if not self.is_sent:
            self.is_sent = True
            self.sent_at = timezone.now()
            self.save(update_fields=['is_sent', 'sent_at'])


class EmailNotification(models.Model):
    """Email notification tracking"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_notifications')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.user.email}"


class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email preferences
    email_notifications = models.BooleanField(default=True)
    email_account_updates = models.BooleanField(default=True)
    email_kyc_updates = models.BooleanField(default=True)
    email_transaction_alerts = models.BooleanField(default=True)
    email_referral_updates = models.BooleanField(default=True)
    email_security_alerts = models.BooleanField(default=True)
    email_promotions = models.BooleanField(default=False)
    
    # In-app preferences
    in_app_notifications = models.BooleanField(default=True)
    in_app_account_updates = models.BooleanField(default=True)
    in_app_kyc_updates = models.BooleanField(default=True)
    in_app_transaction_alerts = models.BooleanField(default=True)
    in_app_referral_updates = models.BooleanField(default=True)
    in_app_security_alerts = models.BooleanField(default=True)
    in_app_promotions = models.BooleanField(default=True)
    
    # SMS preferences
    sms_notifications = models.BooleanField(default=False)
    sms_security_alerts = models.BooleanField(default=True)
    sms_transaction_alerts = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    def get_email_preference(self, category):
        """Get email preference for a specific category"""
        preference_map = {
            'account': self.email_account_updates,
            'kyc': self.email_kyc_updates,
            'transaction': self.email_transaction_alerts,
            'referral': self.email_referral_updates,
            'security': self.email_security_alerts,
            'promotion': self.email_promotions,
        }
        return preference_map.get(category, self.email_notifications)
    
    def get_in_app_preference(self, category):
        """Get in-app preference for a specific category"""
        preference_map = {
            'account': self.in_app_account_updates,
            'kyc': self.in_app_kyc_updates,
            'transaction': self.in_app_transaction_alerts,
            'referral': self.in_app_referral_updates,
            'security': self.in_app_security_alerts,
            'promotion': self.in_app_promotions,
        }
        return preference_map.get(category, self.in_app_notifications)
