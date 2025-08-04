import pyotp
import time
from django.conf import settings
from django.core.mail import EmailMessage

from .models import User

secret_key = pyotp.random_base32()
totp = pyotp.TOTP(secret_key, interval=120)

def generate_otp():
    return totp.now()

def verify_otp(token):
    return totp.verify(token)


def send_otp_mail(email):
    otp = generate_otp()
    user = User.objects.get(email=email)
    from_email = settings.DEFAULT_EMAIL_HOST

    subject = 'Vortexis Verification OTP'
    message = f'Hi {user.first_name},\n\nThank you for signing up on Vortexis. Please use the following OTP to verify your account.\n\nOTP: {otp}\n\nIf you did not sign up on Vortexis, please ignore this email.\n\nRegards,\nVortexis Team' 
    email = EmailMessage(subject, message, from_email=from_email, to=[email])
    email.send(fail_silently=True)


def send_password_reset_email(user, reset_token):
    from_email = settings.DEFAULT_EMAIL_HOST
    
    subject = 'Password Reset - Vortexis'
    message = f'''Hi {user.first_name},

You have requested to reset your password for your Vortexis account.

Please use the following token to reset your password:

Token: {reset_token.token}

This token will expire in 1 hour.

If you did not request a password reset, please ignore this email and your password will remain unchanged.

For security reasons, this reset link can only be used once.

Regards,
Vortexis Team'''
    
    email = EmailMessage(subject, message, from_email=from_email, to=[user.email])
    email.send(fail_silently=True)