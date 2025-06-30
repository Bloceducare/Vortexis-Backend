from rest_framework import serializers
from .models import Organization
from accounts.models import User

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
        # Send email notification
        from django.core.mail import send_mail
        send_mail(
            subject='Organization Created',
            message=f'Your organization "{organization.name}" has been created and is pending admin approval.',
            from_email='noreply@hackathon.com',
            recipient_list=[user.email],
            fail_silently=True
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
        # Send email to new moderators
        from django.core.mail import send_mail
        for moderator in moderators:
            send_mail(
                subject='Added as Moderator',
                message=f'You have been added as a moderator for "{instance.name}".',
                from_email='noreply@hackathon.com',
                recipient_list=[moderator.email],
                fail_silently=True
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
        # Send email to removed moderators
        from django.core.mail import send_mail
        for moderator in moderators:
            send_mail(
                subject='Removed as Moderator',
                message=f'You have been removed as a moderator for "{instance.name}".',
                from_email='noreply@hackathon.com',
                recipient_list=[moderator.email],
                fail_silently=True
            )
        return instance