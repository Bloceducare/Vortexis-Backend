from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Notification, EmailNotification, NotificationPreference, NotificationTemplate
from .serializers import (
    NotificationSerializer, NotificationListSerializer, NotificationPreferenceSerializer,
    EmailNotificationSerializer, NotificationTemplateSerializer, NotificationStatsSerializer,
    CreateNotificationSerializer, BulkNotificationSerializer, MarkAllReadSerializer,
    NotificationFilterSerializer
)
from .services import NotificationService, NotificationTemplates
from swiftconnect.permissions import IsAdminOrRoleAdmin

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user notifications
    
    Provides endpoints for users to view and manage their notifications.
    """
    serializer_class = NotificationListSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get notifications for the current user"""
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        
        user = self.request.user
        queryset = Notification.objects.filter(user=user)
        
        # Filter by read status
        unread_only = self.request.query_params.get('unread_only', 'false').lower() == 'true'
        if unread_only:
            queryset = queryset.filter(is_read=False)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark a specific notification as read
        
        Marks the specified notification as read for the current user.
        """
        notification = self.get_object()
        if notification.user != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        
        notification.mark_as_read()
        return Response({"message": "Notification marked as read"})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read
        
        Marks all notifications (or notifications in a specific category) as read for the current user.
        """
        serializer = MarkAllReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        category = serializer.validated_data.get('category')
        count = NotificationService.mark_all_notifications_read(request.user, category)
        return Response({
            "message": f"Marked {count} notifications as read",
            "count": count
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get notification statistics for the user
        
        Returns comprehensive statistics about the user's notifications including
        total count, unread count, category breakdown, and recent notifications.
        """
        user = request.user
        
        # Get basic counts
        total_notifications = Notification.objects.filter(user=user).count()
        unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
        
        # Get notifications by category
        notifications_by_category = (
            Notification.objects.filter(user=user)
            .values('category')
            .annotate(count=Count('id'))
            .order_by('category')
        )
        category_stats = {item['category']: item['count'] for item in notifications_by_category}
        
        # Get recent notifications
        recent_notifications = NotificationService.get_user_notifications(user, limit=5)
        
        stats_data = {
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'notifications_by_category': category_stats,
            'recent_notifications': NotificationListSerializer(recent_notifications, many=True).data
        }
        
        serializer = NotificationStatsSerializer(stats_data)
        return Response(serializer.data)


class NotificationPreferenceView(generics.RetrieveUpdateAPIView):
    """
    View for managing notification preferences
    
    Allows users to view and update their notification preferences for different
    categories and channels (email, in-app, SMS).
    """
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Get or create notification preferences for the user"""
        return NotificationService.get_or_create_preferences(self.request.user)


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """
    Admin ViewSet for managing notifications
    
    Provides admin endpoints for viewing, creating, and managing notifications
    across all users in the system.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoleAdmin]
    queryset = Notification.objects.all()
    
    def get_queryset(self):
        """Get notifications with optional filtering"""
        # Handle swagger schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        
        queryset = Notification.objects.select_related('user').all()
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            queryset = queryset.filter(is_read=is_read_bool)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def create_notification(self, request):
        """
        Create a notification for a specific user
        
        This endpoint allows admins to send a notification to a single user
        with full customization options.
        """
        serializer = CreateNotificationSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data.get('user_id')
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
            success = NotificationService.send_notification(
                user=user,
                title=serializer.validated_data['title'],
                message=serializer.validated_data['message'],
                category=serializer.validated_data.get('category', 'system'),
                priority=serializer.validated_data.get('priority', 'normal'),
                data=serializer.validated_data.get('data'),
                action_url=serializer.validated_data.get('action_url'),
                action_text=serializer.validated_data.get('action_text'),
                send_email=serializer.validated_data.get('send_email', True),
                send_in_app=serializer.validated_data.get('send_in_app', True)
            )
            
            if success:
                return Response({"message": "Notification sent successfully"})
            else:
                return Response({"error": "Failed to send notification"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_notification(self, request):
        """
        Send notifications to multiple users
        
        Sends the same notification to multiple users simultaneously.
        Useful for system announcements, promotions, or bulk communications.
        """
        serializer = BulkNotificationSerializer(data=request.data)
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            users = User.objects.filter(id__in=user_ids)
            
            success_count, total_count = NotificationService.send_bulk_notifications(
                users=users,
                title=serializer.validated_data['title'],
                message=serializer.validated_data['message'],
                category=serializer.validated_data.get('category', 'system'),
                priority=serializer.validated_data.get('priority', 'normal'),
                data=serializer.validated_data.get('data'),
                action_url=serializer.validated_data.get('action_url'),
                action_text=serializer.validated_data.get('action_text'),
                send_email=serializer.validated_data.get('send_email', True),
                send_in_app=serializer.validated_data.get('send_in_app', True)
            )
            
            return Response({
                "message": f"Notifications sent: {success_count}/{total_count} successful",
                "success_count": success_count,
                "total_count": total_count
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get admin notification statistics"""
        # Get overall stats
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        
        # Get notifications by category
        notifications_by_category = (
            Notification.objects.values('category')
            .annotate(count=Count('id'))
            .order_by('category')
        )
        category_stats = {item['category']: item['count'] for item in notifications_by_category}
        
        # Get notifications by priority
        notifications_by_priority = (
            Notification.objects.values('priority')
            .annotate(count=Count('id'))
            .order_by('priority')
        )
        priority_stats = {item['priority']: item['count'] for item in notifications_by_priority}
        
        # Get recent activity
        recent_notifications = Notification.objects.select_related('user').order_by('-created_at')[:10]
        
        # Get email notification stats
        email_stats = {
            'total': EmailNotification.objects.count(),
            'sent': EmailNotification.objects.filter(status='sent').count(),
            'failed': EmailNotification.objects.filter(status='failed').count(),
            'pending': EmailNotification.objects.filter(status='pending').count(),
        }
        
        stats_data = {
            'total_notifications': total_notifications,
            'unread_notifications': unread_notifications,
            'notifications_by_category': category_stats,
            'notifications_by_priority': priority_stats,
            'email_notifications': email_stats,
            'recent_notifications': NotificationListSerializer(recent_notifications, many=True).data
        }
        
        return Response(stats_data)


class EmailNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for email notifications (admin only)
    
    Provides admin access to view email notification history and track
    delivery status across all users.
    """
    serializer_class = EmailNotificationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoleAdmin]
    queryset = EmailNotification.objects.all()
    
    def get_queryset(self):
        """Get email notifications with optional filtering"""
        queryset = EmailNotification.objects.select_related('user').all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        return queryset.order_by('-created_at')


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for notification templates (admin only)
    
    Allows admins to create, manage, and use notification templates
    for consistent messaging across the platform.
    """
    serializer_class = NotificationTemplateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoleAdmin]
    queryset = NotificationTemplate.objects.all()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get active notification templates
        
        Returns all active notification templates that can be used
        for sending notifications.
        """
        templates = NotificationTemplate.objects.filter(is_active=True)
        serializer = self.get_serializer(templates, many=True)
        return Response(serializer.data)


class CreateSingleNotificationView(generics.CreateAPIView):
    """
    Create a single notification for a specific user
    
    This endpoint allows admins to send a notification to a single user
    with full customization options.
    """
    serializer_class = CreateNotificationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoleAdmin]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_id = serializer.validated_data.get('user_id')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        success = NotificationService.send_notification(
            user=user,
            title=serializer.validated_data['title'],
            message=serializer.validated_data['message'],
            category=serializer.validated_data.get('category', 'system'),
            priority=serializer.validated_data.get('priority', 'normal'),
            data=serializer.validated_data.get('data'),
            action_url=serializer.validated_data.get('action_url'),
            action_text=serializer.validated_data.get('action_text'),
            send_email=serializer.validated_data.get('send_email', True),
            send_in_app=serializer.validated_data.get('send_in_app', True)
        )
        
        if success:
            return Response({"message": "Notification sent successfully"}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Failed to send notification"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateBulkNotificationView(generics.CreateAPIView):
    """
    Send notifications to multiple users
    
    This endpoint allows admins to send the same notification to multiple
    users simultaneously. Useful for system announcements and promotions.
    """
    serializer_class = BulkNotificationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoleAdmin]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user_ids = serializer.validated_data['user_ids']
        users = User.objects.filter(id__in=user_ids)
        
        success_count, total_count = NotificationService.send_bulk_notifications(
            users=users,
            title=serializer.validated_data['title'],
            message=serializer.validated_data['message'],
            category=serializer.validated_data.get('category', 'system'),
            priority=serializer.validated_data.get('priority', 'normal'),
            data=serializer.validated_data.get('data'),
            action_url=serializer.validated_data.get('action_url'),
            action_text=serializer.validated_data.get('action_text'),
            send_email=serializer.validated_data.get('send_email', True),
            send_in_app=serializer.validated_data.get('send_in_app', True)
        )
        
        return Response({
            "message": f"Notifications sent: {success_count}/{total_count} successful",
            "success_count": success_count,
            "total_count": total_count
        }, status=status.HTTP_201_CREATED)
