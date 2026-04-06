import pyotp
import qrcode
import io
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import models
from accounts.models import User
from hackathon.models import Hackathon, Submission
from organization.models import Organization
from .models import Review, AuditLog, PlatformSetting
from .serializers import (
    UserSerializer, HackathonSerializer, SubmissionSerializer,
    AdminOrganizationSerializer, AuditLogSerializer, PlatformSettingSerializer
)
from .permissions import IsAdminUser
from .throttles import AdminRateThrottle
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Count, Avg



@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
@throttle_classes([AdminRateThrottle])
@swagger_auto_schema(
    operation_description="Generate QR code for 2FA setup",
    operation_summary="Get 2FA QR Code",
    tags=["2FA"]
)
def generate_2fa_qr(request):
    user = request.user
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        user.save()

    totp_uri = pyotp.TOTP(user.totp_secret).provisioning_uri(
        name=user.email, issuer_name="Vortexis Admin Console"
    )

    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return HttpResponse(buf, content_type="image/png")



class AuditMixin:
    def perform_action(self, action, target_type=None, target_id=None):
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None
        )



class UserViewSet(AuditMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'search', openapi.IN_QUERY,
                description="Search users by email, first name, or last name",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'is_active', openapi.IN_QUERY,
                description="Filter by active status (true/false)",
                type=openapi.TYPE_BOOLEAN
            ),
            openapi.Parameter(
                'is_verified', openapi.IN_QUERY,
                description="Filter by verification status (true/false)",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        tags=["Users"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()

        queryset = User.objects.all()
        search = self.request.query_params.get('search')
        is_active = self.request.query_params.get('is_active')
        is_verified = self.request.query_params.get('is_verified')

        if search:
            queryset = queryset.filter(
                models.Q(email__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search)
            )
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        if is_verified is not None:
            queryset = queryset.filter(is_verified=is_verified.lower() == 'true')

        return queryset

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        self.perform_action('CREATE_USER', target_id=response.data.get('id'))
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        self.perform_action('UPDATE_USER', target_id=kwargs.get('pk'))
        return response

    def destroy(self, request, *args, **kwargs):
        self.perform_action('DELETE_USER', target_id=kwargs.get('pk'))
        return super().destroy(request, *args, **kwargs)



class HackathonViewSet(viewsets.ModelViewSet):
    queryset = Hackathon.objects.all()
    serializer_class = HackathonSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'status', openapi.IN_QUERY,
                description="Filter hackathons by status (upcoming, ongoing, completed)",
                type=openapi.TYPE_STRING,
                enum=['upcoming', 'ongoing', 'completed']
            ),
            openapi.Parameter(
                'start_date', openapi.IN_QUERY,
                description="Filter hackathons starting on or after this date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date'
            ),
            openapi.Parameter(
                'end_date', openapi.IN_QUERY,
                description="Filter hackathons ending on or before this date (YYYY-MM-DD)",
                type=openapi.TYPE_STRING,
                format='date'
            ),
        ],
        tags=["Hackathons"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Hackathon.objects.none()

        queryset = Hackathon.objects.all()
        status_filter = self.request.query_params.get("status")
        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)

        is_approved = self.request.query_params.get('is_approved')
        is_suspended = self.request.query_params.get('is_suspended')
        if is_approved is not None:
            queryset = queryset.filter(is_approved=is_approved.lower() == 'true')
        if is_suspended is not None:
            queryset = queryset.filter(is_suspended=is_suspended.lower() == 'true')

        return queryset.order_by("-start_date")

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        hackathon = self.get_object()
        hackathon.is_approved = True
        hackathon.is_suspended = False
        hackathon.save()
        self.log_action('APPROVE_HACKATHON', target_id=pk)
        return Response({'message': 'Hackathon approved'})

    @action(detail=True, methods=['patch'])
    def reject(self, request, pk=None):
        hackathon = self.get_object()
        hackathon.is_approved = False
        hackathon.save()
        self.log_action('REJECT_HACKATHON', target_id=pk)
        return Response({'message': 'Hackathon rejected'})

    @action(detail=True, methods=['patch'])
    def suspend(self, request, pk=None):
        hackathon = self.get_object()
        hackathon.is_suspended = True
        hackathon.save()
        self.log_action('SUSPEND_HACKATHON', target_id=pk)
        return Response({'message': 'Hackathon suspended'})

    @action(detail=True, methods=['patch'])
    def restore(self, request, pk=None):
        hackathon = self.get_object()
        hackathon.is_suspended = False
        hackathon.save()
        self.log_action('RESTORE_HACKATHON', target_id=pk)
        return Response({'message': 'Hackathon restored'})

    def log_action(self, action, target_id=None):
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action=action,
            target_type="Hackathon",
            target_id=str(target_id) if target_id else None,
            timestamp=timezone.now()
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        self.log_action("CREATE_HACKATHON", target_id=response.data.get("id"))
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        self.log_action("UPDATE_HACKATHON", target_id=kwargs.get("pk"))
        return response

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        self.log_action("PARTIAL_UPDATE_HACKATHON", target_id=kwargs.get("pk"))
        return response

    def destroy(self, request, *args, **kwargs):
        self.log_action("DELETE_HACKATHON", target_id=kwargs.get("pk"))
        return super().destroy(request, *args, **kwargs)



class SubmissionViewSet(viewsets.ModelViewSet):
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'status', openapi.IN_QUERY,
                description="Filter submissions by status (pending, approved, rejected)",
                type=openapi.TYPE_STRING,
                enum=['pending', 'approved', 'rejected']
            ),
            openapi.Parameter(
                'hackathon_id', openapi.IN_QUERY,
                description="Filter submissions by hackathon ID",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'user_id', openapi.IN_QUERY,
                description="Filter submissions by user ID",
                type=openapi.TYPE_INTEGER
            ),
        ],
        tags=["Submissions"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Submission.objects.none()

        queryset = Submission.objects.all()
        status_filter = self.request.query_params.get('status')
        hackathon_id = self.request.query_params.get('hackathon_id')
        user_id = self.request.query_params.get('user_id')

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if hackathon_id:
            queryset = queryset.filter(hackathon_id=hackathon_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    @action(detail=False, methods=['get'], url_path='score-overview')
    def score_overview(self, request):
        hackathon_id = request.query_params.get('hackathon_id')
        submissions = Submission.objects.all()
        if hackathon_id:
            submissions = submissions.filter(hackathon_id=hackathon_id)

        score_stats = submissions.aggregate(
            total_submissions=Count('id'),
            reviewed_submissions=Count('id', filter=models.Q(status='reviewed')),
            approved_submissions=Count('id', filter=models.Q(status='approved')),
            rejected_submissions=Count('id', filter=models.Q(status='rejected')),
            average_overall_score=Avg('reviews__overall_score'),
            average_technical_score=Avg('reviews__technical_score'),
            average_innovation_score=Avg('reviews__innovation_score')
        )

        submission_scores = submissions.annotate(
            avg_overall=Avg('reviews__overall_score'),
            avg_technical=Avg('reviews__technical_score'),
            avg_innovation=Avg('reviews__innovation_score'),
            review_count=Count('reviews')
        ).values(
            'id', 'project__title', 'hackathon__title', 'status', 'approved',
            'avg_overall', 'avg_technical', 'avg_innovation', 'review_count'
        )

        return Response({
            'score_stats': score_stats,
            'submissions': list(submission_scores)
        })

    def log_action(self, action, target_id=None):
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action=action,
            target_type="Submission",
            target_id=str(target_id) if target_id else None,
            timestamp=timezone.now()
        )

    @action(detail=True, methods=["patch"])
    def approve(self, request, pk=None):
        submission = self.get_object()
        submission.status = "approved"
        submission.approved = True
        submission.save()
        self.log_action("APPROVE_SUBMISSION", target_id=pk)
        return Response({"message": "Submission approved"})

    @action(detail=True, methods=["patch"])
    def reject(self, request, pk=None):
        submission = self.get_object()
        submission.status = "rejected"
        submission.approved = False
        submission.save()
        self.log_action("REJECT_SUBMISSION", target_id=pk)
        return Response({"message": "Submission rejected"})

    def destroy(self, request, *args, **kwargs):
        self.log_action("DELETE_SUBMISSION", target_id=kwargs.get("pk"))
        return super().destroy(request, *args, **kwargs)



class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = AdminOrganizationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'name', openapi.IN_QUERY,
                description="Search organizations by name",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'is_active', openapi.IN_QUERY,
                description="Filter by active status (true/false)",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        tags=["Organizations"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Organization.objects.none()

        queryset = Organization.objects.all()
        name = self.request.query_params.get('name')
        is_active = self.request.query_params.get('is_active')

        if name:
            queryset = queryset.filter(name__icontains=name)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        is_approved = self.request.query_params.get('is_approved')
        is_suspended = self.request.query_params.get('is_suspended')
        if is_approved is not None:
            queryset = queryset.filter(is_approved=is_approved.lower() == 'true')
        if is_suspended is not None:
            queryset = queryset.filter(is_suspended=is_suspended.lower() == 'true')

        return queryset

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        organization = self.get_object()
        organization.is_approved = True
        organization.is_suspended = False
        organization.save()
        self.log_action('APPROVE_ORGANIZATION', target_id=pk)
        return Response({'message': 'Organization approved'})

    @action(detail=True, methods=['patch'])
    def reject(self, request, pk=None):
        organization = self.get_object()
        organization.is_approved = False
        organization.save()
        self.log_action('REJECT_ORGANIZATION', target_id=pk)
        return Response({'message': 'Organization rejected'})

    @action(detail=True, methods=['patch'])
    def suspend(self, request, pk=None):
        organization = self.get_object()
        organization.is_suspended = True
        organization.save()
        self.log_action('SUSPEND_ORGANIZATION', target_id=pk)
        return Response({'message': 'Organization suspended'})

    @action(detail=True, methods=['patch'])
    def restore(self, request, pk=None):
        organization = self.get_object()
        organization.is_suspended = False
        organization.save()
        self.log_action('RESTORE_ORGANIZATION', target_id=pk)
        return Response({'message': 'Organization restored'})

    def log_action(self, action, target_id=None):
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action=action,
            target_type="Organization",
            target_id=str(target_id) if target_id else None,
            timestamp=timezone.now()
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        self.log_action("CREATE_ORGANIZATION", target_id=response.data.get("id"))
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        self.log_action("UPDATE_ORGANIZATION", target_id=kwargs.get("pk"))
        return response

    def destroy(self, request, *args, **kwargs):
        self.log_action("DELETE_ORGANIZATION", target_id=kwargs.get("pk"))
        return super().destroy(request, *args, **kwargs)


# admin_console/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.db.models import Count, Avg
from accounts.models import User
from hackathon.models import Hackathon, Submission
from organization.models import Organization

class AnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'month', openapi.IN_QUERY, description="Month to filter (1-12)", type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'year', openapi.IN_QUERY, description="Year to filter (e.g., 2026)", type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'hackathon_id', openapi.IN_QUERY, description="Optional hackathon ID to filter analytics", type=openapi.TYPE_INTEGER
            ),
        ],
        tags=["Analytics"]
    )
    def get(self, request):
        # Parse query parameters
        try:
            month = int(request.GET.get('month')) if request.GET.get('month') else None
            year = int(request.GET.get('year')) if request.GET.get('year') else None
            hackathon_id = int(request.GET.get('hackathon_id')) if request.GET.get('hackathon_id') else None
        except ValueError:
            return Response({"error": "month, year, and hackathon_id must be integers"}, status=400)

        # Base metrics
        total_users = User.objects.count()
        total_hackathons = Hackathon.objects.count()
        total_submissions = Submission.objects.count()
        total_organizations = Organization.objects.count()

        # Optional filtering by month/year
        if month or year:
            submissions_qs = Submission.objects.all()
            if month:
                submissions_qs = submissions_qs.filter(created_at__month=month)
            if year:
                submissions_qs = submissions_qs.filter(created_at__year=year)
            total_submissions = submissions_qs.count()

        # Optional hackathon-specific metrics
        hackathon_specific = None
        if hackathon_id:
            submissions_for_hackathon = Submission.objects.filter(hackathon_id=hackathon_id)
            participants_count = User.objects.filter(submissions__hackathon_id=hackathon_id).distinct().count()
            hackathon_specific = {
                "submissions": submissions_for_hackathon.count(),
                "participants": participants_count
            }

        # Compile response
        data = {
            "total_users": total_users,
            "total_hackathons": total_hackathons,
            "total_submissions": total_submissions,
            "total_organizations": total_organizations
        }

        if hackathon_specific:
            data["hackathon_specific"] = hackathon_specific

        return Response(data)


class LogsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'admin_id', openapi.IN_QUERY,
                description="Filter logs by admin user ID",
                type=openapi.TYPE_INTEGER
            ),
            openapi.Parameter(
                'action', openapi.IN_QUERY,
                description="Filter logs by action type (case-insensitive search)",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'start_date', openapi.IN_QUERY,
                description="Filter logs from this date onwards (ISO format: YYYY-MM-DDTHH:MM:SS)",
                type=openapi.TYPE_STRING,
                format='date-time'
            ),
            openapi.Parameter(
                'end_date', openapi.IN_QUERY,
                description="Filter logs up to this date (ISO format: YYYY-MM-DDTHH:MM:SS)",
                type=openapi.TYPE_STRING,
                format='date-time'
            ),
        ],
        tags=["Audit Logs"]
    )
    def get(self, request):
        if getattr(self, 'swagger_fake_view', False):
            return Response([])

        logs = AuditLog.objects.all().order_by('-timestamp')
        admin_id = request.query_params.get('admin_id')
        action = request.query_params.get('action')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if admin_id:
            logs = logs.filter(admin__id=admin_id)
        if action:
            logs = logs.filter(action__icontains=action)
        if start_date:
            logs = logs.filter(timestamp__gte=parse_datetime(start_date))
        if end_date:
            logs = logs.filter(timestamp__lte=parse_datetime(end_date))

        serializer = AuditLogSerializer(logs, many=True)
        return Response(serializer.data)



class PlatformSettingViewSet(viewsets.ModelViewSet):
    queryset = PlatformSetting.objects.all()
    serializer_class = PlatformSettingSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes = [AdminRateThrottle]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'key', openapi.IN_QUERY,
                description="Search settings by key name",
                type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                'is_active', openapi.IN_QUERY,
                description="Filter by active status (true/false)",
                type=openapi.TYPE_BOOLEAN
            ),
        ],
        tags=["Platform Settings"]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return PlatformSetting.objects.none()

        queryset = PlatformSetting.objects.all()
        key = self.request.query_params.get('key')
        is_active = self.request.query_params.get('is_active')

        if key:
            queryset = queryset.filter(key__icontains=key)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset

    def perform_create(self, serializer):
        setting = serializer.save()
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action="CREATE_SETTING",
            target_type="PlatformSetting",
            target_id=str(setting.id),
            timestamp=timezone.now()
        )

    def perform_update(self, serializer):
        setting = serializer.save()
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action="UPDATE_SETTING",
            target_type="PlatformSetting",
            target_id=str(setting.id),
            timestamp=timezone.now()
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            admin=getattr(self.request, 'user', None),
            action="DELETE_SETTING",
            target_type="PlatformSetting",
            target_id=str(instance.id),
            timestamp=timezone.now()
        )
        instance.delete()