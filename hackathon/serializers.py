from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from django.utils import timezone

from team.models import Team
from team.serializers import TeamSerializer
from .models import Hackathon, Project, Review, Prize, Theme, Rule, Submission


class HackathonSerailizer:
    class CreateHackathonSerializer(serializers.ModelSerializer):
        class Meta:
            model = Hackathon
            fields = ['title', 'description', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'min_team_size', 'max_team_size']

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            if not user.is_organizer:
                raise AuthenticationFailed("You are not authorized to create a hackathon.")
            
            if not data.get('title'):
                raise serializers.ValidationError("Title is required.")
            if not data.get('description'):
                raise serializers.ValidationError("Description is required.")
            if not data.get('venue'):
                raise serializers.ValidationError("Venue is required.")
            if not data.get('start_date'):
                raise serializers.ValidationError("Start date is required.")
            if not data.get('end_date'):
                raise serializers.ValidationError("End date is required.")
            if not data.get('min_team_size'):
                raise serializers.ValidationError("minimum team size is required")
            if not data.get('max_team_size'):
                raise serializers.ValidationError("maximum team size is required")
            return data
        
        def create(self, validated_data):
            request = self.context.get('request')
            user = request.user
            hackathon = Hackathon.objects.create(
                title=validated_data['title'],
                description=validated_data['description'],
                venue=validated_data['venue'],
                details = validated_data.get('details', ''),
                start_date=validated_data['start_date'],
                end_date=validated_data['end_date'],
                organization=user.organization,
                min_team_size = validated_data['min_team_size'],
                max_team_size = validated_data['max_team_size'],
                grand_prize = validated_data.get('grand_prize', 0)
            )
            hackathon.skills.set(validated_data.get('skills', []))
            hackathon.themes.set(validated_data.get('themes', []))
            return hackathon

    class HackathonSerializer(serializers.ModelSerializer):
        id = serializers.IntegerField(read_only=True)
        title = serializers.CharField(read_only=True)
        description = serializers.CharField(read_only=True)
        grand_prize = serializers.IntegerField(read_only=True)
        venue = serializers.CharField(read_only=True)
        details = serializers.CharField(read_only=True)
        organization = serializers.CharField(read_only=True)
        start_date = serializers.DateField(read_only=True)
        end_date = serializers.DateField(read_only=True)
        min_team_size = serializers.IntegerField(read_only=True)
        max_team_size = serializers.IntegerField(read_only=True)
        participants = serializers.SerializerMethodField()
        themes = serializers.SerializerMethodField()
        rules = serializers.SerializerMethodField()
        prizes = serializers.SerializerMethodField()
        submissions = serializers.SerializerMethodField()

        class Meta:
            model = Hackathon
            fields = '__all__'

        def get_participants(self, obj):
            return TeamSerializer.TeamSerializer(obj.participants.all(), many=True).data
        
        def get_themes(self, obj):
            return ThemeSerializer(obj.themes.all(), many=True).data
        
        def get_rules(self, obj):
            return RuleSerializer(obj.rules.all(), many=True).data
        
        def get_prizes(self, obj):
            return PrizeSerializer(obj.prizes.all(), many=True).data
        
        def get_submissions(self, obj):
            return SubmissionSerializer(obj.submissions.all(), many=True).data
        
    class UpdateHackathonSerializer(serializers.ModelSerializer):
        class Meta:
            model = Hackathon
            fields = ['title', 'description', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'min_team_size', 'max_team_size']
            extra_kwargs = {
                'title': {'required': False},
                'description': {'required': False},
                'venue': {'required': False},
                'details': {'required': False},
                'skills': {'required': False},
                'themes': {'required': False},
                'grand_prize': {'required': False},
                'start_date': {'required': False},
                'end_date': {'required': False},
                'min_team_size': {'required': False},
                'max_team_size': {'required': False},
            }

        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            hackathon = self.instance
            
            user = request.user
            if hackathon.organization.organizer != user and user not in hackathon.organization.moderators.all():
                raise AuthenticationFailed("You are not authorized to update this hackathon.")
            
            return data
            
        def update(self, instance, validated_data):
            instance.title = validated_data.get('title', instance.title)
            instance.description = validated_data.get('description', instance.description)
            instance.venue = validated_data.get('venue', instance.venue)
            instance.details = validated_data.get('details', instance.details)
            instance.start_date = validated_data.get('start_date', instance.start_date)
            instance.end_date = validated_data.get('end_date', instance.end_date)
            instance.min_team_size = validated_data.get('min_team_size', instance.min_team_size)
            instance.max_team_size = validated_data.get('max_team_size', instance.max_team_size)
            instance.grand_prize = validated_data.get('grand_prize', instance.grand_prize)
            instance.skills.set(validated_data.get('skills', instance.skills.all()))
            instance.themes.set(validated_data.get('themes', instance.themes.all()))
            instance.save()
            return instance
    
    class RegisterHackathonSerializer(serializers.Serializer):
        team_id = serializers.IntegerField()
        def validate_team_id(self, team_id):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            if not team_id and team_id != 0:
                raise serializers.ValidationError("Team id is required.")
            
            try:
                team = Team.objects.get(id=team_id)
            except Team.DoesNotExist:
                raise serializers.ValidationError("Team does not exist.")
            if user not in team.members.all():
                raise serializers.ValidationError("You are not a member of this team.")
            
            hackathon = self.instance
            if team in hackathon.participants.all():
                raise serializers.ValidationError("You are already registered for this hackathon.")
            
            return team_id
        
        
        def update(self, instance, validated_data):
            team = Team.objects.get(id=validated_data['team_id'])
            instance.teams.add(team)
            return instance
        

class ProjectSerializer:
    class CreateProjectSerializer(serializers.Serializer):
        class Meta:
            model = Project
            fields = ['title', 'description', 'github_url', 'live_link', 'team']
            ref_name = 'HackathonProjectCreateSerializer'
        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            user = request.user
            if not user.is_authenticated:
                raise AuthenticationFailed("You are not authenticated.")
            if not data.get('title'):
                raise serializers.ValidationError("Title is required.")
            if not data.get('description'):
                raise serializers.ValidationError("Description is required.")
            if not data.get('github_url'):
                raise serializers.ValidationError("Github url is required.")
            if not data.get('team'):
                raise serializers.ValidationError("Team is required.")
            try:
                team = Team.objects.get(id=data['team'])
            except Team.DoesNotExist:
                raise serializers.ValidationError("Team does not exist.")
            if team not in user.teams.all():
                raise serializers.ValidationError("You are not a member of this team.")
            return data
        def create(self, validated_data):
            request = self.context.get('request')
            user = request.user
            if not user.is_authenticated:
                raise AuthenticationFailed("You are not authenticated.")
            project = Project.objects.create(
                title=validated_data['title'],
                description=validated_data['description'],
                github_url=validated_data['github_url'],
                live_link=validated_data.get('live_link', ''),
                team=validated_data['team']
            )
            return project
    class ProjectSerializer(serializers.ModelSerializer):
        id = serializers.IntegerField(read_only=True)
        title = serializers.CharField(read_only=True)
        description = serializers.CharField(read_only=True)
        github_url = serializers.CharField(read_only=True)
        live_link = serializers.CharField(read_only=True)
        submitted = serializers.BooleanField(read_only=True)
        team = serializers.SerializerMethodField()
        created_at = serializers.DateTimeField(read_only=True)
        updated_at = serializers.DateTimeField(read_only=True)

        class Meta:
            model = Project
            fields = '__all__'
            ref_name = 'HackathonProjectDetailSerializer'
        def get_team(self, obj):
            if obj.team:
                return {
                    'id': obj.team.id,
                    'name': obj.team.name
                }
            return None
        def get_submitted(self, obj):
            return obj.submission is not None
        def get_created_at(self, obj):
            return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
        def get_updated_at(self, obj):
            return obj.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        
    class UpdateProjectSerializer(serializers.ModelSerializer):
        class Meta:
            model = Project
            fields = ['title', 'description', 'github_url', 'live_link']
            extra_kwargs = {
                'title': {'required': False},
                'description': {'required': False},
                'github_url': {'required': False},
                'live_link': {'required': False},
            }
            ref_name = 'HackathonProjectUpdateSerializer'
        def validate(self, data):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            if not user.is_authenticated:
                raise AuthenticationFailed("You are not authenticated.")
            
            team = self.instance.team
            if team not in user.teams.all():
                raise serializers.ValidationError("You are not a member of this team.")
            
            return data
        
        def update(self, instance, validated_data):
            instance.title = validated_data.get('title', instance.title)
            instance.description = validated_data.get('description', instance.description)
            instance.github_url = validated_data.get('github_url', instance.github_url)
            instance.live_link = validated_data.get('live_link', instance.live_link)
            instance.save()
            return instance
        
    class SubmitProjectSerializer(serializers.Serializer):
        hackathon_id = serializers.IntegerField()
        def validate_hackathon_id(self, hackathon_id):
            request = self.context.get('request')
            if not request:
                raise serializers.ValidationError("Request context is required.")
            
            user = request.user
            if not user.is_authenticated:
                raise AuthenticationFailed("You are not authenticated.")
            
            if not hackathon_id and hackathon_id != 0:
                raise serializers.ValidationError("Hackathon id is required.")
            
            try:
                hackathon = Hackathon.objects.get(id=hackathon_id)
            except Hackathon.DoesNotExist:
                raise serializers.ValidationError("Hackathon does not exist.")
            
            project = self.instance
            if project.hackathons.filter(id=hackathon_id).exists():
                raise serializers.ValidationError("You have already submitted this project for this hackathon.")
            if project.team not in hackathon.participants.all():
                raise serializers.ValidationError("You are not a participant of this hackathon.")
            
            return hackathon_id
        
        def update(self, instance, validated_data):
            hackathon = Hackathon.objects.get(id=validated_data['hackathon_id'])
            instance.hackathons.add(hackathon)
            return instance
        

class ReviewSerializer(serializers.ModelSerializer):
    judge = serializers.SerializerMethodField()
    submission = serializers.PrimaryKeyRelatedField(queryset=Submission.objects.all())
    
    class Meta:
        model = Review
        fields = ['id', 'submission', 'judge', 'score', 'review', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_judge(self, obj):
        return {
            'id': obj.judge.id,
            'username': obj.judge.username,
            'email': obj.judge.email
        }
    
    def validate_score(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("Score must be between 0 and 100")
        return value
    
    def validate(self, data):
        submission = data['submission']
        user = self.context['request'].user
        
        if submission.hackathon not in user.judged_hackathons.all():
            raise serializers.ValidationError("You are not authorized to review this submission")
            
        if Review.objects.filter(submission=submission, judge=user).exists():
            raise serializers.ValidationError("You have already reviewed this submission")
            
        return data

class SubmissionSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    reviews = ReviewSerializer(many=True, read_only=True)
    hackathon = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Submission
        fields = ['id', 'project', 'team', 'hackathon', 'approved', 'reviews', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'approved']
    
    def get_project(self, obj):
        return {
            'id': obj.project.id,
            'title': obj.project.title,
            'description': obj.project.description,
            'github_url': obj.project.github_url,
            'live_link': obj.project.live_link
        }
    
    def get_team(self, obj):
        return {
            'id': obj.team.id,
            'name': obj.team.name
        }

class CreateSubmissionSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    
    class Meta:
        model = Submission
        fields = ['project']
    
    def validate_project(self, project):
        user = self.context['request'].user
        if project.team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this project's team")
        return project

class UpdateSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['approved']
    
    def validate_approved(self, value):
        if not self.context['request'].user.is_organizer:
            raise serializers.ValidationError("Only organizers can update submission status")
        return value

class PrizeSerializer(serializers.ModelSerializer):
    recipient = serializers.SerializerMethodField()
    
    class Meta:
        model = Prize
        fields = ['id', 'name', 'amount', 'hackathon', 'recipient', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_recipient(self, obj):
        if obj.recipient:
            return {
                'id': obj.recipient.id,
                'name': obj.recipient.name
            }
        return None

class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = ['id', 'description', 'hackathon', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
