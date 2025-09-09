from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
from django.conf import settings
from accounts.models import User
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed


class Google:

    @staticmethod
    def validate(access_token):
        try:
            idinfo = id_token.verify_oauth2_token(access_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)

            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')

            return idinfo
        except Exception as e:
            raise AuthenticationFailed('Invalid or expired token')
        

def register_social_user(provider, username, email, first_name, last_name):
    user = User.objects.filter(email=email).first()
    if user:
        if provider == user.auth_provider:
            return login_social_user(username)
        else:
            raise AuthenticationFailed(
                detail=f"Please continue your login with {user.auth_provider} to access your account"
            )
    else:
        new_user = User.objects.create_user(email=email, username=username, first_name=first_name, last_name=last_name, password=settings.SOCIAL_AUTH_PASSWORD, auth_provider=provider)
        new_user.is_verified = True
        new_user.save()
        return login_social_user(username)

def login_social_user(username):
    login_user = authenticate(username=username, password=settings.SOCIAL_AUTH_PASSWORD)
    if not login_user:
        raise AuthenticationFailed('Invalid credentials')
    user_tokens = login_user.tokens()
    return {
            'username': login_user.username,
            'email': login_user.email,
            'full_name': (login_user.first_name + ' ' + login_user.last_name).strip() or login_user.username,
            'access_token': str(user_tokens['access']),
            'refresh_token': str(user_tokens['refresh'])
        }


class Github:
    @staticmethod
    def get_token(code):
        payload = {
            'client_id': settings.GITHUB_CLIENT_ID,
            'client_secret': settings.GITHUB_CLIENT_SECRET,
            'code': code
        }
        headers = {
            'Accept': 'application/json'
        }
        response = requests.post('https://github.com/login/oauth/access_token', data=payload, headers=headers)
        return response.json().get('access_token')
    
    @staticmethod
    def get_user_details(access_token):
        try:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            response = requests.get('https://api.github.com/user', headers=headers)
            return response.json()
        except Exception as e:
            raise AuthenticationFailed('Invalid or expired token')
    