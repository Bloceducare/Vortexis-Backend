from rest_framework import serializers
from .utils import Google, register_social_user, Github
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

class GoogleSocialAuthSerializer(serializers.Serializer):
    access_token = serializers.CharField()


    def validate_access_token(self, access_token):
        try:
            idinfo = Google.validate(access_token)
        except Exception as e:
            raise AuthenticationFailed('Invalid token')
        if idinfo['aud'] != settings.GOOGLE_CLIENT_ID:
            raise AuthenticationFailed('Invalid client id')
        email = idinfo['email']
        first_name = idinfo['given_name']
        last_name = idinfo['family_name']
        provider = 'google'
        return register_social_user(provider, email, email, first_name, last_name)
    
class GithubSocialAuthSerializer(serializers.Serializer):
    code = serializers.CharField()

    def validate_code(self, code):
        access_token = Github.get_token(code)
        if access_token:
                github_user = Github.get_user_details(access_token)
                full_name = github_user.get('name')
                print(full_name)
                email = github_user.get('email')
                if not email:
                    raise AuthenticationFailed(detail='Email is required')
                names = full_name.split(' ')
                if len(names) > 1:
                    first_name = names[0]
                    last_name = names[1]
                else:
                    first_name = names[0]
                    last_name = ''
                username = github_user.get('login')
                provider = 'github'
                return register_social_user(provider, username, email, first_name, last_name)
        else:
            raise AuthenticationFailed(detail='Invalid code')