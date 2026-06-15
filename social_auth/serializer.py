from rest_framework import serializers
from .utils import Google, register_social_user, Github
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

class GoogleSocialAuthSerializer(serializers.Serializer):
    access_token = serializers.CharField()

    def validate(self, attrs):
        access_token = attrs.get('access_token')
        try:
            idinfo = Google.validate(access_token)
        except Exception as e:
            raise AuthenticationFailed('Invalid token')
        if idinfo['aud'] != settings.GOOGLE_CLIENT_ID:
            raise AuthenticationFailed('Invalid client id')
        email = idinfo['email']
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        provider = 'google'
        # Use email as username for Google auth
        user_data = register_social_user(provider, email, email, first_name, last_name)
        attrs['user_data'] = user_data
        return attrs
    
class GithubSocialAuthSerializer(serializers.Serializer):
    code = serializers.CharField()

    def validate(self, attrs):
        code = attrs.get('code')
        access_token = Github.get_token(code)
        if not access_token:
            raise AuthenticationFailed(detail='Invalid code')

        github_user = Github.get_user_details(access_token)
        username = github_user.get('login')

        # GitHub returns email: null when the user keeps it private — fall back
        # to the /user/emails endpoint for their primary verified address.
        email = github_user.get('email')
        if not email:
            email = Github.get_primary_email(access_token)
        if not email:
            raise serializers.ValidationError(
                {'email': 'Could not retrieve a verified email from GitHub. '
                          'Please make an email public or grant email access.'}
            )

        # GitHub's name is a single optional string — may be missing, a single
        # name, or "First Last". Split safely and fall back to the login.
        full_name = (github_user.get('name') or '').strip()
        parts = full_name.split(' ', 1) if full_name else []
        first_name = parts[0] if parts and parts[0] else (username or 'githubuser')
        last_name = parts[1] if len(parts) > 1 else ''

        provider = 'github'
        try:
            user_data = register_social_user(provider, username, email, first_name, last_name)
        except ValueError as e:
            # Surface manager-level validation failures as 400, not a 500 crash.
            raise serializers.ValidationError({'detail': str(e)})

        attrs['user_data'] = user_data
        return attrs