from rest_framework import serializers
from .models import Organization
from accounts.models import User

class OrganizationSerializer(serializers.ModelSerializer):
    class CreateOrganizationSerializer(serializers.ModelSerializer):
        class Meta:
            model = Organization
            fields = ['name', 'description']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            if Organization.objects.filter(organizer=user).exists():
                raise serializers.ValidationError("You already have an existing organization.")
            
            if not data.get('name'):
                raise serializers.ValidationError("Name is required.")
            if not data.get('description'):
                raise serializers.ValidationError("Description is required.")
            
            return data
        
        def create(self, validated_data):
            request = self.context.get('request')
            user = request.user
            organization = Organization.objects.create(
                name=validated_data['name'],
                description=validated_data['description'],
                organizer=user,
            )
            organization.moderators.set(validated_data.get('moderators', []))
            return organization

    class OrganizationSerializer(serializers.ModelSerializer):
        id = serializers.IntegerField(read_only=True)
        name = serializers.CharField(read_only=True)
        description = serializers.CharField(read_only=True)
        organizer = serializers.CharField(read_only=True)
        moderators = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all())
        is_approved = serializers.BooleanField(read_only=True)
        created_at = serializers.DateTimeField(read_only=True)
        updated_at = serializers.DateTimeField(read_only=True)

        class Meta:
            model = Organization
            fields = '__all__'

    class AddModeratorSerializer(serializers.ModelSerializer):
        class Meta:
            model = Organization
            fields = ['moderators']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            organization = self.instance
            if organization.organizer != user:
                raise serializers.ValidationError("You are not authorized to add moderators to this organization.")
            
            return data

        def update(self, instance, validated_data):
            moderators = validated_data.get('moderators', [])
            instance.moderators.add(moderators)
            return instance
        
    class UpdateOrganizationSerializer(serializers.ModelSerializer):
        class Meta:
            model = Organization
            fields = ['name', 'description']
            extra_kwargs = {
                'name': {'required': False},
                'description': {'required': False},
            }
            

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            organization = self.instance
            if organization.organizer != user:
                raise serializers.ValidationError("You are not authorized to update this organization.")
            
            return data

        def update(self, instance, validated_data):
            instance.name = validated_data.get('name', instance.name)
            instance.description = validated_data.get('description', instance.description)
            instance.save()
            return instance
        