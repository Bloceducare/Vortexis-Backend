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


def send_password_reset_email(user, reset_token, request):
    from_email = settings.DEFAULT_EMAIL_HOST
    
    # Get frontend URL from request origin
    origin = request.META.get('HTTP_ORIGIN') or f"http://{request.get_host()}"
    reset_url = f"{origin}/reset-password?token={reset_token.token}"
    
    subject = 'Password Reset - Vortexis'
    message = f'''Hi {user.first_name},

You have requested to reset your password for your Vortexis account.

Please click the following link to reset your password:

{reset_url}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email and your password will remain unchanged.

For security reasons, this reset link can only be used once.

Regards,
Vortexis Team'''
    
    email = EmailMessage(subject, message, from_email=from_email, to=[user.email])
    email.send(fail_silently=True)


def send_judge_invitation_email(email_address, hackathon, invitation_token, request):
    from_email = settings.DEFAULT_EMAIL_HOST
    
    # Get frontend URL from request origin
    origin = request.META.get('HTTP_ORIGIN') or f"http://{request.get_host()}"
    accept_url = f"{origin}/judge-invitation?token={invitation_token}"
    
    subject = f'Invitation to Judge {hackathon.title}'
    message = f'''Hello,

You have been invited to judge the hackathon '{hackathon.title}'.

Hackathon Details:
- Title: {hackathon.title}
- Description: {hackathon.description}
- Venue: {hackathon.venue}
- Start Date: {hackathon.start_date}
- End Date: {hackathon.end_date}

To accept this invitation, please click the following link:

{accept_url}

If you don't have an account yet, you'll be redirected to create one first.

This invitation will expire in 7 days.

If you did not expect this invitation, please ignore this email.

Regards,
Vortexis Team'''
    
    email = EmailMessage(subject, message, from_email=from_email, to=[email_address])
    email.send(fail_silently=True)