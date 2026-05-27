from rest_framework import serializers
from accounts.models import User
from hackathon.models import Hackathon, Submission
from organization.models import Organization
from .models import AuditLog, PlatformSetting

class UserSerializer(serializers.ModelSerializer):
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'auth_provider', 'is_participant', 'is_organizer', 'is_judge',
            'is_moderator', 'is_admin', 'is_staff', 'is_active', 'is_verified',
            'date_joined', 'last_login', 'organizations',
        ]
        ref_name = 'AdminUserSerializer'

    def get_organizations(self, obj):
        return list(obj.organizations.values_list('id', flat=True))
    
class HackathonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hackathon
        fields = '__all__'
        ref_name = 'AdminHackathonSerializer'

class SubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = '__all__'
        ref_name = 'AdminSubmissionSerializer'

class AdminOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'
        ref_name = 'AdminOrganizationSerializer'

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = '__all__'
        ref_name = 'AdminAuditLogSerializer'

class PlatformSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSetting
        fields = '__all__'
        ref_name = 'AdminPlatformSettingSerializer'