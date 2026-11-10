import random
import string
import logging
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.cache import cache

from notifications.services import NotificationService

from .models import User

logger = logging.getLogger(__name__)

OTP_TIMEOUT_SECONDS = 600  # 10 minutes


def generate_otp(user):
    """
    Generate a 6-digit OTP and store it in Django's cache.
    Invalidates any previous unused OTPs for the user.
    """
    logger.info(f"[OTP] Generating OTP for user: {user.email} (ID: {user.id})")
    try:
        code = ''.join(random.choices(string.digits, k=6))
        cache_key = f'otp_{user.email}'

        cache.set(cache_key, code, timeout=OTP_TIMEOUT_SECONDS)

        stored_otp = cache.get(cache_key)
        if stored_otp != code:
            logger.error(
                f"[OTP] Failed to persist OTP in cache for {user.email}. "
                f"Got: {stored_otp!r}"
            )
            raise Exception("OTP verification failed - OTP not found in cache after storing")

        logger.info(f"[OTP] OTP stored successfully in cache for user {user.email}")
        return code
    except Exception as e:
        logger.error(f"[OTP] Failed to generate/store OTP for user {user.email}: {str(e)}", exc_info=True)
        raise


def verify_otp(user, code):
    """
    Verify an OTP code for a user.
    Returns True if the OTP is valid, False otherwise.
    """
    logger.info(f"[VERIFY_OTP] Starting OTP verification for user: {user.email} (ID: {user.id})")

    if not user or not code:
        logger.warning(f"[VERIFY_OTP] Invalid input - user: {user}, code: {code}")
        return False

    cache_key = f'otp_{user.email}'
    cached_otp = cache.get(cache_key)

    if not cached_otp:
        logger.warning(f"[VERIFY_OTP] OTP not found in cache for user {user.email}")
        return False

    if cached_otp != code:
        logger.warning(
            f"[VERIFY_OTP] OTP code does not match for user {user.email}. "
            f"Expected: {cached_otp}, Got: {code}"
        )
        return False

    cache.delete(cache_key)
    logger.info(f"[VERIFY_OTP] OTP verified successfully for user {user.email}")
    return True


def send_otp_mail(email):
    try:
        user = User.objects.get(email=email)
        otp = generate_otp(user)

        subject = 'Vortexis Verification OTP'
        message = (
            f'Hi {user.first_name},\n\n'
            f'Thank you for signing up on Vortexis. Please use the following OTP to verify your account.\n\n'
            f'OTP: {otp}\n\n'
            f'If you did not sign up on Vortexis, please ignore this email.\n\n'
            f'Regards,\nVortexis Team'
        )

        result = NotificationService.send_notification(
            user=user,
            title=subject,
            message=message,
            category='account',
            priority='high',
            send_email=True,
            send_in_app=False,
            template_name="emails/otp_verification.html",
            context={
                'user': user,
                'otp': otp
            },
            data={'otp': otp, 'action': 'verify_account'}
        )

        if result:
            logger.info(f"[SEND_OTP_MAIL] NotificationService.send_notification returned success for user {user.id}")
        else:
            logger.error(f"[SEND_OTP_MAIL] NotificationService.send_notification returned False for user {user.id}")

        logger.info(f"[SEND_OTP_MAIL] OTP email process completed for {email}")
        return result

    except User.DoesNotExist:
        logger.error(f"[SEND_OTP_MAIL] User not found with email: {email}")
        raise
    except Exception as e:
        logger.error(f"[SEND_OTP_MAIL] Failed to send OTP email to {email}: {str(e)}", exc_info=True)
        raise


def send_password_reset_email(user, reset_token, request):
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

    NotificationService.send_notification(
        user=user,
        title=subject,
        message=message,
        category='security',
        priority='high',
        send_email=True,
        send_in_app=True,
        action_url=reset_url,
        action_text='Reset Password',
        template_name="emails/password_reset.html",
        context={
            'user': user,
            'action_url': reset_url,
            'link': reset_url
        },
        data={'reset_token': reset_token.token, 'action': 'password_reset'}
    )


def send_judge_invitation_email(email_address, hackathon, invitation_token, request):
    # Get frontend URL from request origin
    if request:
        origin = request.META.get('HTTP_ORIGIN') or f"http://{request.get_host()}"
    else:
        origin = "https://vortexis.io"
    accept_url = f"{origin}/judge-invitation?token={invitation_token}"

    organizer_name = None
    if hackathon.organization and hackathon.organization.organizer:
        organizer = hackathon.organization.organizer
        organizer_name = (organizer.first_name + ' ' + organizer.last_name).strip() or organizer.username

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

    context = {
        'hackathon': hackathon,
        'hackathon_title': hackathon.title,
        'invitation_token': invitation_token,
        'accept_url': accept_url,
        'action_url': accept_url,
        'action_text': 'Accept Judge Invitation',
        'organizer_name': organizer_name,
        'invited_by_name': organizer_name,
        'site_url': origin,
        'email': email_address,
    }

    # Try to get user by email, create a notification if user exists
    try:
        user = User.objects.get(email=email_address)
        context['user'] = user
        NotificationService.send_notification(
            user=user,
            title=subject,
            message=message,
            category='account',
            priority='high',
            send_email=True,
            send_in_app=True,
            template_name='emails/judge_invitation.html',
            context=context,
            action_url=accept_url,
            action_text='Accept Judge Invitation',
            data={'invitation_token': invitation_token, 'hackathon_id': hackathon.id, 'action': 'judge_invitation'}
        )
    except User.DoesNotExist:
        # For non-existing users, use direct email with HTML message
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        try:
            html_message = render_to_string('emails/judge_invitation.html', context)
        except Exception as e:
            logger.error(f"Failed to render judge invitation template: {e}")
            html_message = None

        from_email = getattr(settings, 'EMAIL_HOST_USER', settings.DEFAULT_EMAIL_HOST) or settings.DEFAULT_EMAIL_HOST
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[email_address],
            html_message=html_message,
            fail_silently=False
        )
