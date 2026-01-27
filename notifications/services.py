import logging
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import Notification, EmailNotification, NotificationPreference, NotificationTemplate
import json

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling all types of notifications"""
    
    @staticmethod
    def get_or_create_preferences(user):
        """Get or create notification preferences for a user"""
        preferences, created = NotificationPreference.objects.get_or_create(user=user)
        return preferences
    
    @staticmethod
    def send_notification(
        user,
        title,
        message,
        category='system',
        priority='normal',
        data=None,
        action_url=None,
        action_text=None,
        send_email=True,
        send_in_app=True,
        template_name=None,
        context=None
    ):
        """
        Send notification to user through multiple channels
        
        Args:
            user: User object
            title: Notification title
            message: Notification message
            category: Notification category (account, kyc, transaction, etc.)
            priority: Notification priority (low, normal, high, urgent)
            data: Additional JSON data
            action_url: URL for action button
            action_text: Text for action button
            send_email: Whether to send email notification
            send_in_app: Whether to create in-app notification
            template_name: Email template name
            context: Context data for email template
        """
        try:
            # Get user preferences
            preferences = NotificationService.get_or_create_preferences(user)
            
            # Create in-app notification if enabled
            if send_in_app and preferences.get_in_app_preference(category):
                notification = Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    category=category,
                    priority=priority,
                    data=data or {},
                    action_url=action_url or None,
                    action_text=action_text or None
                )
                logger.info(f"Created in-app notification for user {user.id}: {title}")
            
            # Send email notification if enabled
            if send_email and preferences.get_email_preference(category):
                NotificationService.send_email_notification(
                    user, title, message, template_name, context
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending notification to user {user.id}: {str(e)}")
            print(e)
            # print(traceback.format_exc())
            return False
    
    @staticmethod
    def send_email_notification(user, subject, message, template_name=None, context=None):
        """Send email notification to user"""
        try:
            # Use template if provided
            if template_name and context:
                message = render_to_string(template_name, context)
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
                fail_silently=False,
                html_message=message if '<html>' in message else None
            )
            
            # Track email notification
            EmailNotification.objects.create(
                user=user,
                subject=subject,
                message=message,
                status='sent',
                sent_at=timezone.now()
            )
            
            logger.info(f"Email notification sent to {user.email}: {subject}")
            return True
            
        except Exception as e:
            # Track failed email
            EmailNotification.objects.create(
                user=user,
                subject=subject,
                message=message,
                status='failed',
                error_message=str(e)
            )
            logger.error(f"Failed to send email to {user.email}: {str(e)}")
            return False
    
    @staticmethod
    def send_bulk_notifications(
        users,
        title,
        message,
        category='system',
        priority='normal',
        data=None,
        action_url=None,
        action_text=None,
        send_email=True,
        send_in_app=True
    ):
        """Send notifications to multiple users"""
        success_count = 0
        total_count = len(users)
        
        for user in users:
            if NotificationService.send_notification(
                user, title, message, category, priority, data, 
                action_url, action_text, send_email, send_in_app
            ):
                success_count += 1
        
        logger.info(f"Bulk notification sent: {success_count}/{total_count} successful")
        return success_count, total_count
    
    @staticmethod
    def mark_notification_read(notification_id, user):
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def mark_all_notifications_read(user, category=None):
        """Mark all notifications as read for a user"""
        try:
            queryset = Notification.objects.filter(user=user, is_read=False)
            if category:
                queryset = queryset.filter(category=category)
            
            updated_count = queryset.update(
                is_read=True,
                read_at=timezone.now()
            )
            
            logger.info(f"Marked {updated_count} notifications as read for user {user.id}")
            return updated_count
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            return 0
    
    @staticmethod
    def get_user_notifications(user, unread_only=False, category=None, limit=50):
        """Get notifications for a user"""
        queryset = Notification.objects.filter(user=user)
        
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        if category:
            queryset = queryset.filter(category=category)
        
        return queryset.order_by('-created_at')[:limit]
    
    @staticmethod
    def get_notification_count(user, unread_only=True):
        """Get notification count for a user"""
        queryset = Notification.objects.filter(user=user)
        if unread_only:
            queryset = queryset.filter(is_read=False)
        return queryset.count()


class NotificationTemplates:
    """Predefined notification templates"""
    
    @staticmethod
    def kyc_approved(user):
        """KYC approval notification"""
        return NotificationService.send_notification(
            user=user,
            title="KYC Verification Approved",
            message="Congratulations! Your KYC verification has been approved. You can now access all platform features.",
            category='kyc',
            priority='high',
            action_url="/kyc/status",
            action_text="View Status",
            data={'kyc_status': 'approved'}
        )
    
    @staticmethod
    def kyc_rejected(user, reason=""):
        """KYC rejection notification"""
        message = "Your KYC verification has been rejected."
        if reason:
            message += f" Reason: {reason}"
        message += " Please submit new documents for verification."
        
        return NotificationService.send_notification(
            user=user,
            title="KYC Verification Rejected",
            message=message,
            category='kyc',
            priority='high',
            action_url="/kyc/submit",
            action_text="Resubmit KYC",
            data={'kyc_status': 'rejected', 'reason': reason}
        )
    
    @staticmethod
    def transaction_successful(user, amount, transaction_type, reference):
        """Transaction success notification"""
        return NotificationService.send_notification(
            user=user,
            title=f"{transaction_type} Successful",
            message=f"Your {transaction_type} of ₦{amount:,.2f} was successful. Reference: {reference}",
            category='transaction',
            priority='normal',
            action_url=f"/transactions/{reference}",
            action_text="View Details",
            data={
                'amount': amount,
                'transaction_type': transaction_type,
                'reference': reference,
                'status': 'successful'
            }
        )
    
    @staticmethod
    def transaction_failed(user, amount, transaction_type, reference, reason=""):
        """Transaction failure notification"""
        message = f"Your {transaction_type} of ₦{amount:,.2f} failed."
        if reason:
            message += f" Reason: {reason}"
        message += f" Reference: {reference}"
        
        return NotificationService.send_notification(
            user=user,
            title=f"{transaction_type} Failed",
            message=message,
            category='transaction',
            priority='high',
            action_url=f"/transactions/{reference}",
            action_text="View Details",
            data={
                'amount': amount,
                'transaction_type': transaction_type,
                'reference': reference,
                'status': 'failed',
                'reason': reason
            }
        )
    
    @staticmethod
    def referral_bonus(user, referred_user, amount):
        """Referral bonus notification"""
        return NotificationService.send_notification(
            user=user,
            title="Referral Bonus Earned!",
            message=f"You earned ₦{amount:,.2f} for referring {referred_user.username} to SwiftConnect!",
            category='referral',
            priority='normal',
            action_url="/referrals",
            action_text="View Referrals",
            data={
                'bonus_amount': amount,
                'referred_user': referred_user.username,
                'type': 'referral_bonus'
            }
        )
    
    @staticmethod
    def security_alert(user, alert_type, details=""):
        """Security alert notification"""
        return NotificationService.send_notification(
            user=user,
            title="Security Alert",
            message=f"Security alert: {alert_type}. {details}",
            category='security',
            priority='urgent',
            action_url="/security",
            action_text="Review Security",
            data={
                'alert_type': alert_type,
                'details': details,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    @staticmethod
    def account_update(user, update_type, details=""):
        """Account update notification"""
        return NotificationService.send_notification(
            user=user,
            title="Account Update",
            message=f"Your account has been updated: {update_type}. {details}",
            category='account',
            priority='normal',
            action_url="/account",
            action_text="View Account",
            data={
                'update_type': update_type,
                'details': details
            }
        )
