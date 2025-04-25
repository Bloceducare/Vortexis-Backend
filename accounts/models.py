from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from rest_framework_simplejwt.tokens import RefreshToken
from .managers import UserManager

# Create your models here.

class Skill(models.Model):
    name = models.CharField(max_length=50, null=False, blank=False)

AUTH_PROVIDERS = {'email': 'email', 'google': 'google', 'github': 'github'}

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=False, blank=False)
    username = models.CharField(max_length=50, unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=50, null=False, blank=False)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    skills = models.ManyToManyField(Skill, related_name='participants', blank=True)
    auth_provider = models.CharField(max_length=20, default=AUTH_PROVIDERS.get('email'))
    is_participant = models.BooleanField(default=False)
    is_organizer = models.BooleanField(default=False)
    is_judge = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True, null=True)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    objects = UserManager()

    def __str__(self):
        return self.username
    
    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def tokens(self):
        refresh = RefreshToken.for_user(self)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token)
        }


