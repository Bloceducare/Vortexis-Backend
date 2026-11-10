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
    # Email addresses are case-insensitive in practice, but the unique index on
    # User.email is case-sensitive. Prefer an exact match (so accounts that
    # already differ only by case keep resolving exactly as before), then fall
    # back to a case-insensitive match so "Ada@x.com" and "ada@x.com" resolve to
    # the same account instead of creating a duplicate.
    email = (email or '').strip()
    user = (
        User.objects.filter(email=email).first()
        or User.objects.filter(email__iexact=email).order_by('id').first()
    )
    if user:
        # User exists - link the social account to existing account.
        # Never overwrite details the user already has: a social provider's
        # display name (or, failing that, its login) must not replace the name
        # they registered with. Only fill in what is missing.
        if not user.first_name and first_name and first_name.strip():
            user.first_name = first_name
        if not user.last_name and last_name and last_name.strip():
            user.last_name = last_name

        # Mark user as verified if they weren't before (social auth is inherently verified)
        if not user.is_verified:
            user.is_verified = True
        
        # If user was created with email/password, we can still allow social login
        # We don't change auth_provider to preserve the original method, but allow both
        # Alternatively, we can track that they can use both methods
        user.save()
        return get_user_tokens(user)
    else:
        # New user - check for username conflicts
        original_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{original_username}_{counter}"
            counter += 1
        
        # Create new user with social auth
        new_user = User.objects.create_user(
            email=email, 
            username=username, 
            first_name=first_name, 
            last_name=last_name or '', 
            password=settings.SOCIAL_AUTH_PASSWORD, 
            auth_provider=provider
        )
        new_user.is_verified = True
        new_user.is_participant = True  # Set default role
        new_user.save()
        
        # Create profile for new user
        from accounts.models import Profile
        Profile.objects.get_or_create(user=new_user)
        
        return get_user_tokens(new_user)

def get_user_tokens(user):
    """Generate tokens for a user without requiring password authentication."""
    user_tokens = user.tokens()
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': (user.first_name + ' ' + user.last_name).strip() or user.username,
        'access_token': str(user_tokens['access']),
        'refresh_token': str(user_tokens['refresh'])
    }

def login_social_user(username):
    """Deprecated: Use get_user_tokens instead for social auth."""
    login_user = authenticate(username=username, password=settings.SOCIAL_AUTH_PASSWORD)
    if not login_user:
        raise AuthenticationFailed('Invalid credentials')
    return get_user_tokens(login_user)


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

    @staticmethod
    def get_primary_email(access_token):
        """Fetch the user's primary, verified email.

        GitHub returns ``email: null`` from /user when the user has set their
        email to private, so we fall back to the /user/emails endpoint and pick
        the primary verified address.
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }
            response = requests.get('https://api.github.com/user/emails', headers=headers)
            emails = response.json()
        except Exception:
            return None

        if not isinstance(emails, list):
            return None

        # Prefer the primary + verified address, then any verified address.
        primary = next((e['email'] for e in emails if e.get('primary') and e.get('verified')), None)
        if primary:
            return primary
        return next((e['email'] for e in emails if e.get('verified')), None)
    