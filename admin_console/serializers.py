from rest_framework import serializers
from .models import User, Hackathon, Submission, Organization, AuditLog, PlatformSetting

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        ref_name = 'AdminUserSerializer'

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