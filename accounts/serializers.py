from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from .models import Skill, User, Profile
from .utils import verify_otp

User = get_user_model()

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name']

    def validate_name(self, value):
        # Normalize skill name to lowercase for consistency
        value = value.strip().lower()
        if not value.replace(' ', '').isalpha():
            raise serializers.ValidationError("Skill name must contain only alphabetic characters and spaces.")
        return value

class ProfileSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, required=False)

    class Meta:
        model = Profile
        fields = ['bio', 'github', 'linkedin', 'twitter', 'website', 'location', 'profile_picture', 'skills']

    def validate(self, data):
        # Validate URLs if provided
        for field in ['github', 'linkedin', 'twitter', 'website']:
            if data.get(field):
                if not data[field].startswith(('http://', 'https://')):
                    raise serializers.ValidationError({field: "URL must start with http:// or https://"})
        return data

    def create(self, validated_data):
        skills_data = validated_data.pop('skills', [])
        profile = Profile.objects.create(**validated_data)
        for skill_data in skills_data:
            skill, _ = Skill.objects.get_or_create(name=skill_data['name'].lower())
            profile.skills.add(skill)
        return profile

    def update(self, instance, validated_data):
        skills_data = validated_data.pop('skills', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if skills_data is not None:
            instance.skills.clear()
            for skill_data in skills_data:
                skill, _ = Skill.objects.get_or_create(name=skill_data['name'].lower())
                instance.skills.add(skill)
        return instance

class UserSerializer:
    class RegistrationSerializer(serializers.ModelSerializer):
        password = serializers.CharField(max_length=128, min_length=8, write_only=True)
        password2 = serializers.CharField(max_length=128, min_length=8, write_only=True)

        class Meta:
            model = User
            fields = ['first_name', 'last_name', 'username', 'email', 'password', 'password2']

        def validate(self, data):
            if data['password'] != data['password2']:
                raise serializers.ValidationError({"password": "Passwords do not match."})
            # Check for unique email and username
            if User.objects.filter(email=data['email']).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})
            if User.objects.filter(username=data['username']).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            return data

        def create(self, validated_data):
            validated_data.pop('password2')
            user = User.objects.create_user(
                first_name=validated_data['first_name'],
                last_name=validated_data.get('last_name', ''),
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

        def validate(self, data):
            user = authenticate(username=data['username'], password=data['password'], request=self.context.get('request'))
            if not user:
                raise AuthenticationFailed("Incorrect credentials.")
            if user.auth_provider != 'email':
                raise AuthenticationFailed(f"Please continue your login with {user.auth_provider} to access your account.")
            if not user.is_verified:
                raise AuthenticationFailed("Email is not verified.")
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
        code = serializers.CharField(max_length=6)
        email = serializers.EmailField()

        def validate(self, data):
            try:
                user = User.objects.get(email=data['email'])
            except User.DoesNotExist:
                raise serializers.ValidationError({"email": "User with this email does not exist."})
            if not verify_otp(data['code']):
                raise serializers.ValidationError({"code": "Invalid or expired OTP."})
            return user

    class ResendOtpSerializer(serializers.Serializer):
        email = serializers.EmailField()

        def validate(self, data):
            try:
                user = User.objects.get(email=data['email'])
            except User.DoesNotExist:
                raise serializers.ValidationError({"email": "User with this email does not exist."})
            return user

    class UpdateSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ['first_name', 'last_name', 'username', 'email']
            extra_kwargs = {
                'username': {'required': False, 'max_length': 50},
                'email': {'required': False, 'max_length': 100},
                'first_name': {'required': False, 'max_length': 50},
                'last_name': {'required': False, 'max_length': 50},
            }

        def validate(self, data):
            # Check for unique email and username, excluding the current user
            user = self.instance
            email = data.get('email', user.email)
            username = data.get('username', user.username)
            if email != user.email and User.objects.filter(email=email).exclude(id=user.id).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})
            if username != user.username and User.objects.filter(username=username).exclude(id=user.id).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
            user.first_name = data.get('first_name', user.first_name)
            user.last_name = data.get('last_name', user.last_name)
            user.username = username
            user.email = email
            user.save()
            return data

    class RetrieveSerializer(serializers.ModelSerializer):
        profile = serializers.SerializerMethodField()

        class Meta:
            model = User
            fields = [
                'id', 'username', 'email', 'first_name', 'last_name', 'profile',
                'is_participant', 'is_organizer', 'is_judge', 'is_moderator',
                'is_admin', 'is_verified', 'is_active', 'is_staff', 'is_superuser',
                'date_joined', 'last_login'
            ]

        def get_profile(self, obj):
            profile = Profile.objects.filter(user=obj).first()
            if profile:
                return ProfileSerializer(profile).data
            return None

    class DeleteSerializer(serializers.Serializer):
        def validate(self, data):
            user = self.context.get('user')
            if not user:
                raise serializers.ValidationError("User not found.")
            return data

        def delete(self, user):
            user.delete()
            return {"message": "User deleted successfully."}