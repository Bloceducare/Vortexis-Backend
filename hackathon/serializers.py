from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from django.utils import timezone
from team.models import Team
from team.serializers import TeamSerializer
from .models import Hackathon, Theme, Submission, Review
from accounts.models import User


class ThemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theme
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_name(self, value):
        return value.strip().lower()


class PrizeDetailSerializer(serializers.Serializer):
    """A serializer for the structure of a single prize object."""
    name = serializers.CharField(max_length=100)
    amount = serializers.IntegerField()


class SubmitProjectSerializer(serializers.Serializer):
    hackathon_id = serializers.IntegerField()

    def validate_hackathon_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        try:
            hackathon = Hackathon.objects.get(id=value)
        except Hackathon.DoesNotExist:
            raise serializers.ValidationError("Hackathon does not exist.")
        return value

    def save(self, **kwargs):
        from project.models import Project
        project_id = self.context.get('project_id')
        project = Project.objects.get(id=project_id)
        hackathon = Hackathon.objects.get(id=self.validated_data['hackathon_id'])
        
        if Submission.objects.filter(project=project, hackathon=hackathon).exists():
            raise serializers.ValidationError("This project is already submitted to this hackathon.")
        if project.team not in hackathon.teams.all():
            raise serializers.ValidationError("Your team is not registered for this hackathon.")
        if hackathon.submission_deadline < timezone.now():
            raise serializers.ValidationError("Hackathon submission period has ended.")
        
        submission = Submission.objects.create(project=project, hackathon=hackathon, team=project.team)
        return submission


class SubmissionSerializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    hackathon = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Submission
        fields = ['id', 'project', 'team', 'hackathon', 'approved', 'reviews', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'hackathon', 'project', 'team', 'reviews']

    def get_project(self, obj):
        return {
            'id': obj.project.id,
            'title': obj.project.title,
            'description': obj.project.description,
            'github_url': obj.project.github_url,
            'live_link': obj.project.live_link
        }

    def get_team(self, obj):
        return {'id': obj.team.id, 'name': obj.team.name}
    
    def get_reviews(self, obj):
        reviews = obj.reviews.all()
        return [
            {
                'id': review.id,
                'innovation_score': review.innovation_score,
                'technical_score': review.technical_score,
                'user_experience_score': review.user_experience_score,
                'impact_score': review.impact_score,
                'presentation_score': review.presentation_score,
                'overall_score': review.overall_score,
                'review': review.review,
                'judge': {
                    'id': review.judge.id,
                    'username': review.judge.username,
                    'email': review.judge.email
                }
            }
            for review in reviews
        ]


class CreateSubmissionSerializer(serializers.ModelSerializer):
    project = serializers.IntegerField()

    class Meta:
        model = Submission
        fields = ['project']

    def validate_project(self, value):
        from project.models import Project
        request = self.context.get('request')
        user = request.user
        try:
            project = Project.objects.get(id=value)
        except Project.DoesNotExist:
            raise serializers.ValidationError("Project does not exist.")
        
        if project.team not in user.teams.all():
            raise serializers.ValidationError("You are not a member of this project's team.")
        if Submission.objects.filter(project=project, hackathon=self.context.get('hackathon')).exists():
            raise serializers.ValidationError("This project is already submitted to this hackathon.")
        return value

    def create(self, validated_data):
        from project.models import Project
        hackathon = self.context.get('hackathon')
        project = Project.objects.get(id=validated_data['project'])
        return Submission.objects.create(
            project=project,
            hackathon=hackathon,
            team=project.team
        )


class UpdateSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['approved']

    def validate_approved(self, value):
        if not self.context['request'].user.is_organizer:
            raise serializers.ValidationError("Only organizers can update submission status.")
        return value


class ReviewSerializer(serializers.ModelSerializer):
    judge = serializers.SerializerMethodField()
    submission = serializers.PrimaryKeyRelatedField(queryset=Submission.objects.all())

    class Meta:
        model = Review
        fields = ['id', 'submission', 'judge', 'innovation_score', 'technical_score', 'user_experience_score', 'impact_score', 'presentation_score', 'overall_score', 'review', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'judge']

    def get_judge(self, obj):
        return {'id': obj.judge.id, 'username': obj.judge.username, 'email': obj.judge.email}

    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        submission = data['submission']
        if submission.hackathon not in user.judged_hackathons.all():
            raise serializers.ValidationError("You are not authorized to review this submission.")
        if Review.objects.filter(submission=submission, judge=user).exists():
            raise serializers.ValidationError("You have already reviewed this submission.")
        # Validate all score fields are between 0 and 10
        for field in ['innovation_score', 'technical_score', 'user_experience_score', 'impact_score', 'presentation_score', 'overall_score']:
            value = data.get(field)
            if value is not None and (value < 0 or value > 10):
                raise serializers.ValidationError({field: "Score must be between 0 and 10."})
        return data


class HackathonSerializer(serializers.ModelSerializer):
    participants = serializers.SerializerMethodField()
    themes = ThemeSerializer(many=True, read_only=True)
    rules = serializers.ListField(child=serializers.CharField(), required=False)
    prizes = PrizeDetailSerializer(many=True, required=False)
    submissions = SubmissionSerializer(many=True, read_only=True)

    class Meta:
        model = Hackathon
        fields = '__all__'

    def get_participants(self, obj):
        return TeamSerializer(obj.participants.all(), many=True).data


class CreateHackathonSerializer(HackathonSerializer):
    rules = serializers.JSONField(required=False, help_text='A JSON list of rule strings, e.g., ["Rule 1", "Rule 2"]')
    prizes = serializers.JSONField(required=False, help_text='A JSON list of prize objects, e.g., [{"name": "1st Place", "amount": 1000}]')

    class Meta(HackathonSerializer.Meta):
        fields = ['title', 'description', 'banner_image', 'visibility', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'rules', 'prizes']

    def validate_prizes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Prizes must be a list of objects.")
        for prize_data in value:
            serializer = PrizeDetailSerializer(data=prize_data)
            serializer.is_valid(raise_exception=True)
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        if not user.is_organizer or not user.organization or not user.organization.is_approved:
            raise serializers.ValidationError("Only organizers with an approved organization can create a hackathon.")
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date must be before end date.")
        if data.get('end_date') and data.get('submission_deadline') and data['submission_deadline'].date() > data['end_date']:
            raise serializers.ValidationError("Submission deadline must be before or on the end date.")
        if data.get('min_team_size') and data.get('max_team_size') and data['min_team_size'] > data['max_team_size']:
            raise serializers.ValidationError("Minimum team size cannot exceed maximum team size.")
        return data

    def create(self, validated_data):
        skills = validated_data.pop('skills', [])
        themes = validated_data.pop('themes', [])
        hackathon = Hackathon.objects.create(
            **validated_data,
            organization=self.context['request'].user.organization
        )
        hackathon.skills.set(skills)
        hackathon.themes.set(themes)
        return hackathon


class UpdateHackathonSerializer(HackathonSerializer):
    rules = serializers.JSONField(required=False, help_text='A JSON list of rule strings, e.g., ["Rule 1", "Rule 2"]')
    prizes = serializers.JSONField(required=False, help_text='A JSON list of prize objects, e.g., [{"name": "1st Place", "amount": 1000}]')

    class Meta(HackathonSerializer.Meta):
        fields = ['title', 'description', 'banner_image', 'venue', 'details', 'skills', 'themes', 'grand_prize', 'start_date', 'end_date', 'submission_deadline', 'min_team_size', 'max_team_size', 'visibility', 'rules', 'prizes']
        extra_kwargs = {field: {'required': False} for field in fields}

    def validate_prizes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Prizes must be a list of objects.")
        for prize_data in value:
            serializer = PrizeDetailSerializer(data=prize_data)
            serializer.is_valid(raise_exception=True)
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        hackathon = self.instance
        if hackathon.organization.organizer != user and user not in hackathon.organization.moderators.all():
            raise serializers.ValidationError("You are not authorized to update this hackathon.")
        if data.get('start_date') and data.get('end_date') and data['start_date'] > data['end_date']:
            raise serializers.ValidationError("Start date must be before end date.")
        if data.get('end_date') and data.get('submission_deadline') and data['submission_deadline'].date() > data['end_date']:
            raise serializers.ValidationError("Submission deadline must be before or on the end date.")
        if data.get('min_team_size') and data.get('max_team_size') and data['min_team_size'] > data['max_team_size']:
            raise serializers.ValidationError("Minimum team size cannot exceed maximum team size.")
        return data

    def update(self, instance, validated_data):
        skills = validated_data.pop('skills', None)
        themes = validated_data.pop('themes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if skills is not None:
            instance.skills.set(skills)
        if themes is not None:
            instance.themes.set(themes)
        instance.save()
        return instance


class RegisterHackathonSerializer(serializers.Serializer):
    team_id = serializers.IntegerField()

    def validate_team_id(self, value):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError("Request context is required.")
        user = request.user
        try:
            team = Team.objects.get(id=value)
        except Team.DoesNotExist:
            raise serializers.ValidationError("Team does not exist.")
        if user not in team.members.all():
            raise serializers.ValidationError("You are not a member of this team.")
        hackathon = self.instance
        if team in hackathon.participants.all():
            raise serializers.ValidationError("This team is already registered for the hackathon.")
        if hackathon.start_date < timezone.now().date():
            raise serializers.ValidationError("Hackathon registration period has ended.")
        if team.members.count() < hackathon.min_team_size or team.members.count() > hackathon.max_team_size:
            raise serializers.ValidationError("Team size does not meet hackathon requirements.")
        return value

    def update(self, instance, validated_data):
        team = Team.objects.get(id=validated_data['team_id'])
        instance.participants.add(team)
        return instance


class InviteJudgeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            if not user.is_judge:
                raise serializers.ValidationError("User is not a judge.")
            hackathon = self.context.get('hackathon')
            if user in hackathon.judges.all():
                raise serializers.ValidationError("User is already a judge for this hackathon.")
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")