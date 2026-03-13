from django.db import models
import pyotp
from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

# Custom user with roles
class User(AbstractUser):
    ROLE_CHOICES = [
        ('PlatformOwner','Platform Owner'),
        ('SystemAdmin','System Admin'),
        ('Organizer','Organizer'),
        ('Judge','Judge'),
        ('Participant','Participant')
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=10, choices=[('active','Active'),('inactive','Inactive')], default='active')
    
    # 2FA secret (stored securely)
    totp_secret = models.CharField(max_length=16, blank=True, null=True)
    
    groups = models.ManyToManyField(Group, related_name='admin_console_user_set', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='admin_console_user_permission_set', blank=True)

    def generate_totp_secret(self):
        self.totp_secret = pyotp.random_base32()
        self.save()

    def verify_totp(self, token):
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)
  

class Hackathon(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=[('active','Active'),('inactive','Inactive')], default='active')


class Submission(models.Model):
    hackathon = models.ForeignKey(Hackathon, on_delete=models.CASCADE)
    participant = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('pending','Pending'),('approved','Approved'),('rejected','Rejected')])
    created_at = models.DateTimeField(auto_now_add=True)


class Organization(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField()
    status = models.CharField(max_length=10, choices=[('active','Active'),('inactive','Inactive')], default='active')


class AuditLog(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=200)
    target_type = models.CharField(max_length=50, null=True, blank=True)
    target_id = models.CharField(max_length=50, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class PlatformSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
    
