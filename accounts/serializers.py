from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework.exceptions import AuthenticationFailed
from .models import Skill, User, Profile
from .utils import verify_otp

User = get_user_model()
class UserSerializer:
    class RegistrationSerializer(serializers.ModelSerializer):
        password = serializers.CharField(max_length=50, min_length=8, write_only=True)
        password2 = serializers.CharField(max_length=50, min_length=8, write_only=True)

        class Meta:
            model = User
            fields = ['first_name', 'last_name', 'username', 'email', 'password', 'password2']

        def validate(self, data):
            if data['password'] != data['password2']:
                raise serializers.ValidationError("Passwords do not match.")
            return data

        def create(self, validated_data):
            user = User.objects.create_user(
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                is_participant=True,
                is_organizer=False,
                is_judge=False,
                is_moderator=False,
                is_admin=False
            )
            return user

    class LoginSerializer(serializers.Serializer):
        username = serializers.CharField()
        password = serializers.CharField(write_only=True)
        email = serializers.EmailField(read_only=True)
        full_name = serializers.CharField(read_only=True)
        access_token = serializers.CharField(read_only=True)
        refresh_token = serializers.CharField(read_only=True)

        class Meta:
            model = User
            fields = ['username', 'password', 'email', 'full_name', 'access_token', 'refresh_token']

        def validate(self, data):
            email_user = User.objects.filter(username=data['username']).first()
            if email_user:
                if 'email' != email_user.auth_provider:
                    raise AuthenticationFailed(
                        detail=f"Please continue your login with {email_user.auth_provider} to access your account"
                    )
            user = authenticate(username=data['username'], password=data['password'], request=self.context.get('request'))
            if not user:
                raise AuthenticationFailed("Incorrect credentials.")
            if not user.is_verified:
                raise AuthenticationFailed("Email is not verified.")
            else:
                user_tokens = user.tokens()
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name,
                    'access_token': user_tokens['access'],
                    'refresh_token': user_tokens['refresh']
                }
        
    class VerifyOtpSerializer(serializers.Serializer):
        code = serializers.CharField()
        email = serializers.EmailField()

        def validate(self, data):
            if not verify_otp(data['code']):
                raise serializers.ValidationError("Invalid or Expired OTP.")
            user = User.objects.get(email=data['email'])
            return user
        
    class ResendOtpSerializer(serializers.Serializer):
        email = serializers.EmailField()

        def validate(self, data):
            try:
                user = User.objects.get(email=data['email'])
            except User.DoesNotExist:
                raise serializers.ValidationError("User with this email does not exist.")
            return user
    
    class Retrieve(serializers.Serializer):
        id = serializers.IntegerField()
        username = serializers.CharField()
        email = serializers.EmailField()
        first_name = serializers.CharField()
        last_name = serializers.CharField()
        profile = serializers.SerializerMethodField()
        is_participant = serializers.BooleanField()
        is_organizer = serializers.BooleanField()
        is_judge = serializers.BooleanField()
        is_moderator = serializers.BooleanField()
        is_admin = serializers.BooleanField()
        is_verified = serializers.BooleanField()
        is_active = serializers.BooleanField()
        is_staff = serializers.BooleanField()
        is_superuser = serializers.BooleanField()
        date_joined = serializers.DateTimeField()
        last_login = serializers.DateTimeField()
        class Meta:
            model = User
            fields = "__all__"

        def get_profile(self, obj):
            profile = Profile.objects.filter(user=obj).first()
            if profile:
                return {
                    'bio': profile.bio,
                    'github': profile.github,
                    'linkedin': profile.linkedin,
                    'twitter': profile.twitter,
                    'website': profile.website,
                    'location': profile.location,
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,
                    'skills': [skill.name for skill in profile.skills.all()]
                }
            return None
class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']

    def validate_name(self, value):
        if not value.isalpha():
            raise serializers.ValidationError("Skill name must contain only alphabetic characters.")
        return value
    
class ProfileSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, required=False)

    class Meta:
        model = Profile
        fields = ['bio', 'github', 'linkedin', 'twitter', 'website', 'location', 'profile_picture', 'skills']

    def create(self, validated_data):
        skills_data = validated_data.pop('skills', [])
        profile = Profile.objects.create(**validated_data)
        for skill_data in skills_data:
            skill, created = Skill.objects.get_or_create(name=skill_data['name'])
            profile.skills.add(skill)
        return profile

    def update(self, instance, validated_data):
        skills_data = validated_data.pop('skills', [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if skills_data:
            instance.skills.clear()
            for skill_data in skills_data:
                skill, created = Skill.objects.get_or_create(name=skill_data['name'])
                instance.skills.add(skill)
        
        return instance