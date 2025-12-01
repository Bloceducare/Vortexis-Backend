from rest_framework import serializers
from .models import Organization, ModeratorInvitation
from accounts.models import User
from notifications.services import NotificationService
from django.utils import timezone
from utils.cloudinary_utils import upload_image_to_cloudinary
import re

class ApproveOrganizationSerializer(serializers.Serializer):
    """Empty serializer for the approve organization endpoint."""
    pass

class OrganizationSerializer(serializers.ModelSerializer):
    organizer = serializers.CharField(source='organizer.username', read_only=True)
    moderators = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all(), required=False)

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'description', 'website', 'logo', 'custom_url', 
            'location', 'tagline', 'about', 'organizer', 'moderators', 
            'is_approved', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_approved', 'created_at', 'updated_at']

class CreateOrganizationSerializer(serializers.ModelSerializer):
    logo_file = serializers.ImageField(write_only=True, required=False)
    
    class Meta:
        model = Organization
        fields = [
            'name', 'description', 'website', 'logo_file', 'custom_url', 
            'location', 'tagline', 'about'
        ]
        extra_kwargs = {
            'logo': {'read_only': True},
            'website': {'required': False, 'allow_blank': True},
            'custom_url': {'required': False, 'allow_blank': True},
            'location': {'required': False, 'allow_blank': True},
            'tagline': {'required': False, 'allow_blank': True},
            'about': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Name cannot be empty.")
        if len(value) > 128:
            raise serializers.ValidationError("Name cannot exceed 128 characters.")
        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip()

    def validate_website(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Website URL must start with http:// or https://")
        return value

    def validate_custom_url(self, value):
        if value:
            if len(value) > 128:
                raise serializers.ValidationError("Custom URL cannot exceed 128 characters.")
            if not re.match(r'^[a-zA-Z0-9_-]+$', value):
                raise serializers.ValidationError(
                    "Custom URL can only contain letters, numbers, hyphens, and underscores."
                )
            # Check if custom_url already exists
            if Organization.objects.filter(custom_url=value).exists():
                raise serializers.ValidationError("This custom URL is already taken.")
        return value

    def validate_location(self, value):
        if value and len(value) > 32:
            raise serializers.ValidationError("Location cannot exceed 32 characters.")
        return value

    def validate_tagline(self, value):
        if value and len(value) > 200:
            raise serializers.ValidationError("Tagline cannot exceed 200 characters.")
        return value

    def validate_about(self, value):
        if value and len(value) > 5000:
            raise serializers.ValidationError("About cannot exceed 5000 characters.")
        return value

    def validate(self, data):
        if not self.context.get('request'):
            raise serializers.ValidationError("Request context is required.")
        return data

    def create(self, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        
        # Upload logo to Cloudinary if provided
        if logo_file:
            logo_url = upload_image_to_cloudinary(logo_file, folder='organization_logos')
            validated_data['logo'] = logo_url
        
        user = self.context['request'].user
        organization = Organization.objects.create(
            **validated_data,
            organizer=user
        )
        # Send notification
        NotificationService.send_notification(
            user=user,
            title='Organization Created',
            message=f'Your organization "{organization.name}" has been created and is pending admin approval.',
            category='account',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={
                'organization_id': organization.id,
                'organization_name': organization.name,
                'action': 'organization_created'
            }
        )
        return organization

class UpdateOrganizationSerializer(serializers.ModelSerializer):
    logo_file = serializers.ImageField(write_only=True, required=False)
    
    class Meta:
        model = Organization
        fields = [
            'name', 'description', 'website', 'logo_file', 'custom_url', 
            'location', 'tagline', 'about'
        ]
        extra_kwargs = {
            'logo': {'read_only': True},
            'name': {'required': False},
            'description': {'required': False},
            'website': {'required': False, 'allow_blank': True},
            'custom_url': {'required': False, 'allow_blank': True},
            'location': {'required': False, 'allow_blank': True},
            'tagline': {'required': False, 'allow_blank': True},
            'about': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value):
        if value and len(value) > 128:
            raise serializers.ValidationError("Name cannot exceed 128 characters.")
        return value.strip() if value else value

    def validate_website(self, value):
        if value and not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("Website URL must start with http:// or https://")
        return value

    def validate_custom_url(self, value):
        if value:
            if len(value) > 128:
                raise serializers.ValidationError("Custom URL cannot exceed 128 characters.")
            if not re.match(r'^[a-zA-Z0-9_-]+$', value):
                raise serializers.ValidationError(
                    "Custom URL can only contain letters, numbers, hyphens, and underscores."
                )
            # Check if custom_url already exists (excluding current instance)
            if Organization.objects.filter(custom_url=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("This custom URL is already taken.")
        return value

    def validate_location(self, value):
        if value and len(value) > 32:
            raise serializers.ValidationError("Location cannot exceed 32 characters.")
        return value

    def validate_tagline(self, value):
        if value and len(value) > 200:
            raise serializers.ValidationError("Tagline cannot exceed 200 characters.")
        return value

    def validate_about(self, value):
        if value and len(value) > 5000:
            raise serializers.ValidationError("About cannot exceed 5000 characters.")
        return value

    def validate(self, data):
        user = self.context['request'].user
        if self.instance.organizer != user:
            raise serializers.ValidationError("You are not authorized to update this organization.")
        return data

    def update(self, instance, validated_data):
        logo_file = validated_data.pop('logo_file', None)
        
        # Upload new logo to Cloudinary if provided
        if logo_file:
            logo_url = upload_image_to_cloudinary(logo_file, folder='organization_logos')
            validated_data['logo'] = logo_url
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class AddModeratorSerializer(serializers.Serializer):
    moderators = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all())

    def validate(self, data):
        user = self.context['request'].user
        if self.instance.organizer != user:
            raise serializers.ValidationError("Only the organizer can add moderators.")
        return data

    def update(self, instance, validated_data):
        moderators = validated_data.get('moderators', [])
        instance.moderators.add(*moderators)
        # Send notification to new moderators
        for moderator in moderators:
            NotificationService.send_notification(
                user=moderator,
                title='Added as Moderator',
                message=f'You have been added as a moderator for "{instance.name}".',
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                data={
                    'organization_id': instance.id,
                    'organization_name': instance.name,
                    'role': 'moderator',
                    'action': 'added_as_moderator'
                },
                action_url=f'/organizations/{instance.id}',
                action_text='View Organization'
            )
        return instance

class RemoveModeratorSerializer(serializers.Serializer):
    moderators = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all())

    def validate(self, data):
        user = self.context['request'].user
        if self.instance.organizer != user:
            raise serializers.ValidationError("Only the organizer can remove moderators.")
        return data

    def update(self, instance, validated_data):
        moderators = validated_data.get('moderators', [])
        instance.moderators.remove(*moderators)
        # Send notification to removed moderators
        for moderator in moderators:
            NotificationService.send_notification(
                user=moderator,
                title='Removed as Moderator',
                message=f'You have been removed as a moderator for "{instance.name}".',
                category='account',
                priority='normal',
                send_email=True,
                send_in_app=True,
                data={
                    'organization_id': instance.id,
                    'organization_name': instance.name,
                    'role': 'moderator',
                    'action': 'removed_as_moderator'
                }
            )
        return instance


class ModeratorInvitationSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    inviter_username = serializers.CharField(source='inviter.username', read_only=True)
    invitee_username = serializers.CharField(source='invitee.username', read_only=True)

    class Meta:
        model = ModeratorInvitation
        fields = [
            'id', 'organization', 'organization_name', 'inviter', 'inviter_username',
            'email', 'invitee', 'invitee_username', 'status', 'message',
            'created_at', 'expires_at', 'responded_at'
        ]
        read_only_fields = [
            'id', 'organization_name', 'inviter_username', 'invitee_username',
            'inviter', 'created_at', 'expires_at', 'responded_at'
        ]


class CreateModeratorInvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeratorInvitation
        fields = ['email', 'message']

    def validate_email(self, value):
        organization_id = self.context.get('organization_id')
        if not organization_id:
            raise serializers.ValidationError("Organization context is required.")

        if ModeratorInvitation.objects.filter(
            organization_id=organization_id,
            email=value,
            status=ModeratorInvitation.PENDING
        ).exists():
            raise serializers.ValidationError("A pending invitation already exists for this email.")

        try:
            organization = Organization.objects.get(id=organization_id)
            if organization.moderators.filter(email=value).exists():
                raise serializers.ValidationError("This user is already a moderator.")
            if organization.organizer and organization.organizer.email == value:
                raise serializers.ValidationError("The organizer cannot be invited as a moderator.")
        except Organization.DoesNotExist:
            raise serializers.ValidationError("Organization not found.")

        return value

    def create(self, validated_data):
        organization_id = self.context.get('organization_id')
        inviter = self.context.get('inviter')

        organization = Organization.objects.get(id=organization_id)

        try:
            invitee = User.objects.get(email=validated_data['email'])
        except User.DoesNotExist:
            invitee = None

        invitation = ModeratorInvitation.objects.create(
            organization=organization,
            inviter=inviter,
            invitee=invitee,
            **validated_data
        )

        NotificationService.send_notification(
            user=invitee if invitee else None,
            title='Moderator Invitation',
            message=f'You have been invited to be a moderator for "{organization.name}".',
            category='invitation',
            priority='normal',
            send_email=True,
            send_in_app=True if invitee else False,
            email_override=validated_data['email'] if not invitee else None,
            data={
                'organization_id': organization.id,
                'organization_name': organization.name,
                'invitation_id': invitation.id,
                'invitation_token': invitation.token,
                'action': 'moderator_invitation'
            },
            action_url=f'/invitations/moderator/{invitation.token}',
            action_text='View Invitation'
        )

        return invitation


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            invitation = ModeratorInvitation.objects.get(token=value)
        except ModeratorInvitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token.")

        if not invitation.is_valid():
            raise serializers.ValidationError("This invitation has expired or is no longer valid.")

        self.invitation = invitation
        return value

    def save(self):
        user = self.context.get('user')
        invitation = self.invitation

        if invitation.invitee and invitation.invitee != user:
            raise serializers.ValidationError("This invitation is for a different user.")

        if not invitation.invitee:
            invitation.invitee = user

        invitation.status = ModeratorInvitation.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save()

        invitation.organization.moderators.add(user)

        if not user.is_moderator:
            user.is_moderator = True
            user.save()

        NotificationService.send_notification(
            user=invitation.inviter,
            title='Invitation Accepted',
            message=f'{user.username} has accepted the moderator invitation for "{invitation.organization.name}".',
            category='invitation',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={
                'organization_id': invitation.organization.id,
                'organization_name': invitation.organization.name,
                'moderator_username': user.username,
                'action': 'invitation_accepted'
            }
        )

        return invitation


class DeclineInvitationSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            invitation = ModeratorInvitation.objects.get(token=value)
        except ModeratorInvitation.DoesNotExist:
            raise serializers.ValidationError("Invalid invitation token.")

        if not invitation.is_valid():
            raise serializers.ValidationError("This invitation has expired or is no longer valid.")

        self.invitation = invitation
        return value

    def save(self):
        user = self.context.get('user')
        invitation = self.invitation

        if invitation.invitee and invitation.invitee != user:
            raise serializers.ValidationError("This invitation is for a different user.")

        if not invitation.invitee:
            invitation.invitee = user

        invitation.status = ModeratorInvitation.DECLINED
        invitation.responded_at = timezone.now()
        invitation.save()

        NotificationService.send_notification(
            user=invitation.inviter,
            title='Invitation Declined',
            message=f'{user.username} has declined the moderator invitation for "{invitation.organization.name}".',
            category='invitation',
            priority='normal',
            send_email=True,
            send_in_app=True,
            data={
                'organization_id': invitation.organization.id,
                'organization_name': invitation.organization.name,
                'moderator_username': user.username,
                'action': 'invitation_declined'
            }
        )

        return invitation