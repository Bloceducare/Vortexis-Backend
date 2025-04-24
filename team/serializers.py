from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

from accounts.models import User
from hackathon.models import Hackathon
from .models import Team

class TeamSerializer(serializers.ModelSerializer):
    class CreateTeamSerializer(serializers.ModelSerializer):
        class Meta:
            model = Team
            fields = ['name', 'members']
        
        def validate(self, data):
            if not data.get('name'):
                raise serializers.ValidationError("Team name is required.")
            if not data.get('members'):
                raise serializers.ValidationError("At least one member is required.")
            members = data.get('members')
            if len(members) != len(set(members)):
                raise serializers.ValidationError("Duplicate members are not allowed.")
            return data
        
        def create(self, validated_data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            
            team = Team.objects.create(
                name=validated_data['name'],
                organizer=user
            )
            team.members.set(validated_data['members'])
            return team
        
    class TeamSerializer(serializers.ModelSerializer):
        id = serializers.IntegerField(read_only=True)
        name = serializers.CharField(read_only=True)
        organizer = serializers.CharField(read_only=True)
        members = serializers.SlugRelatedField(many=True, slug_field='username', queryset=User.objects.all())
        hackathons = serializers.SlugRelatedField(many=True, slug_field='title', queryset=Hackathon.objects.all())
        projects = serializers.SerializerMethodField()
        submissions = serializers.SerializerMethodField()
        prizes = serializers.SerializerMethodField()
        created_at = serializers.DateTimeField(read_only=True)
        updated_at = serializers.DateTimeField(read_only=True)

        class Meta:
            model = Team
            fields = '__all__'

        def get_projects(self, obj):
            return obj.projects.all()
        
        def get_submissions(self, obj):
            return obj.submissions.all()
        
        def get_prizes(self, obj):
            return obj.prizes.all()
        
    class UpdateTeamSerializer(serializers.ModelSerializer):
        class Meta:
            model = Team
            fields = ['name']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            user = request.user
            team = self.instance
            if team.organizer != user:
                raise AuthenticationFailed("You are not authorized to update this team.")
            
            if not data.get('name'):
                raise serializers.ValidationError("Team name is required.")
            return data
        
        def update(self, instance, validated_data):
            instance.name = validated_data['name']
            instance.save()
            return instance
        
    class AddMemberSerializer(serializers.ModelSerializer):
        class Meta:
            model = Team
            fields = ['members']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            user = request.user
            team = self.instance
            if team and team.organizer != user:
                raise AuthenticationFailed("You are not authorized to add members to this team.")
            
            if not data.get('members'):
                raise serializers.ValidationError("At least one member is required.")
            members = data.get('members')
            if len(members) != len(set(members)):
                raise serializers.ValidationError("Duplicate members are not allowed.")
            return data
        
        def update(self, instance, validated_data):
            instance.members.add(validated_data['members'])
            return instance
        
    class RemoveMemberSerializer(serializers.ModelSerializer):
        class Meta:
            model = Team
            fields = ['members']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            user = request.user
            team = self.instance
            if team.organizer != user:
                raise AuthenticationFailed("You are not authorized to remove members from this team.")
            
            if not data.get('members'):
                raise serializers.ValidationError("At least one member is required.")
            members = data.get('members')
            if len(members) != len(set(members)):
                raise serializers.ValidationError("Duplicate members are not allowed.")
            return data
        
        def update(self, instance, validated_data):
            instance.members.remove(validated_data['members'])
            return instance
        
    