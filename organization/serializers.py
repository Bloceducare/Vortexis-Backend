from rest_framework import serializers
from .models import Organization
from accounts.models import User
from notifications.services import NotificationService

class ApproveOrganizationSerializer(serializers.Serializer):
    """Empty serializer for the approve organization endpoint."""
    pass

class OrganizationSerializer(serializers.ModelSerializer):
    organizer = serializers.CharField(source='organizer.username', read_only=True)
    moderators = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all(), required=False)

    class Meta:
        model = Organization
        fields = ['id', 'name', 'description', 'organizer', 'moderators', 'is_approved', 'created_at', 'updated_at']
        read_only_fields = ['id', 'is_approved', 'created_at', 'updated_at']

class CreateOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['name', 'description']

    def validate(self, data):
        if not self.context.get('request'):
            raise serializers.ValidationError("Request context is required.")
        user = self.context['request'].user
        if Organization.objects.filter(organizer=user).exists():
            raise serializers.ValidationError("You already have an organization.")
        if not data.get('name').strip():
            raise serializers.ValidationError("Name cannot be empty.")
        if not data.get('description').strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return data

    def create(self, validated_data):
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
    class Meta:
        model = Organization
        fields = ['name', 'description']
        extra_kwargs = {'name': {'required': False}, 'description': {'required': False}}

    def validate(self, data):
        user = self.context['request'].user
        if self.instance.organizer != user:
            raise serializers.ValidationError("You are not authorized to update this organization.")
        return data

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