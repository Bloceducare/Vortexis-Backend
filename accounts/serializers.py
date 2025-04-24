from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework.exceptions import AuthenticationFailed
from .models import Skill, User
from .utils import verify_otp

User = get_user_model()
class UserSerializer:
    class RegistrationSerializer(serializers.ModelSerializer):
        password = serializers.CharField(max_length=50, min_length=8, write_only=True)
        password2 = serializers.CharField(max_length=50, min_length=8, write_only=True)

        class Meta:
            model = User
            fields = ['first_name', 'last_name', 'username', 'email', 'password', 'password2', 'skills']

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
            user.skills.set(validated_data.get('skills', []))
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
        skills = serializers.PrimaryKeyRelatedField(many=True, queryset=Skill.objects.all())
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