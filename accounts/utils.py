import random
import string
import logging
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from datetime import timedelta
from notifications.services import NotificationService

from .models import User

logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test if Redis is actually working"""
    try:
        # Try to get cache backend info
        cache_backend = cache.__class__.__name__
        logger.info(f"[CACHE_TEST] Cache backend: {cache_backend}")
        
        # Test write and read
        test_key = 'redis_connection_test'
        test_value = 'test_value_12345'
        
        # Set value
        cache.set(test_key, test_value, timeout=30)
        
        # Get value back
        retrieved_value = cache.get(test_key)
        
        if retrieved_value == test_value:
            logger.info(f"[CACHE_TEST] ✓ Redis connection is working correctly")
            cache.delete(test_key)
            return True
        elif retrieved_value is None:
            logger.error(f"[CACHE_TEST] ✗ Redis is NOT working - values are not persisting!")
            logger.error(f"[CACHE_TEST] This usually means Redis is not connected or IGNORE_EXCEPTIONS is hiding errors")
            return False
        else:
            logger.error(f"[CACHE_TEST] ✗ Redis returned wrong value: {retrieved_value} (expected: {test_value})")
            return False
    except Exception as e:
        logger.error(f"[CACHE_TEST] ✗ Redis connection test failed with exception: {str(e)}", exc_info=True)
        return False

def generate_otp(user):
    """
    Generate a 6-digit OTP and store it in cache.
    Invalidates any previous unused OTPs for the user.
    """
    logger.info(f"[OTP] Generating OTP for user: {user.email} (ID: {user.id})")
    try:
        # Test Redis connection first
        logger.info(f"[OTP] Testing Redis connection before generating OTP...")
        redis_working = test_redis_connection()
        if not redis_working:
            logger.error(f"[OTP] ✗ Redis is not working! OTP will not be stored properly.")
            logger.error(f"[OTP] Please check: 1) Redis server is running, 2) Redis connection settings, 3) IGNORE_EXCEPTIONS setting")
        
        # Generate a 6-digit random OTP
        code = ''.join(random.choices(string.digits, k=6))
        logger.info(f"[OTP] Generated OTP code: {code}")
        
        # Store OTP in cache with 10-minute expiration
        # Using user email as cache key to ensure uniqueness
        cache_key = f'otp_{user.email}'
        logger.info(f"[OTP] Cache key (without prefix): {cache_key}")
        logger.info(f"[OTP] Cache key (with prefix): vortexis:{cache_key}")
        
        # Store OTP in cache
        logger.info(f"[OTP] Storing OTP in cache with timeout=600 seconds (10 minutes)")
        try:
            cache.set(cache_key, code, timeout=600)  # 600 seconds = 10 minutes
            logger.info(f"[OTP] Cache.set() called successfully")
        except Exception as set_error:
            logger.error(f"[OTP] ✗ Failed to set OTP in cache: {str(set_error)}", exc_info=True)
            raise
        
        # Immediately verify it was stored (critical check)
        logger.info(f"[OTP] Verifying OTP was stored in cache immediately after set()...")
        try:
            stored_otp = cache.get(cache_key)
            logger.info(f"[OTP] Cache.get() returned: {stored_otp} (type: {type(stored_otp).__name__})")
            
            if stored_otp == code:
                logger.info(f"[OTP] ✓ Verification successful - OTP stored correctly: {stored_otp}")
            elif stored_otp is None:
                logger.error(f"[OTP] ✗ CRITICAL: OTP not found in cache immediately after storing!")
                logger.error(f"[OTP] This indicates Redis is not persisting data or connection is failing silently")
                logger.error(f"[OTP] Check Redis connection and IGNORE_EXCEPTIONS setting")
            else:
                logger.error(f"[OTP] ✗ Verification failed - OTP mismatch! Expected: {code}, Got: {stored_otp}")
        except Exception as get_error:
            logger.error(f"[OTP] ✗ Failed to get OTP from cache during verification: {str(get_error)}", exc_info=True)
        
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
    logger.info(f"[VERIFY_OTP] Code to verify: {code}")
    
    if not user or not code:
        logger.warning(f"[VERIFY_OTP] Invalid input - user: {user}, code: {code}")
        return False
    
    # Get OTP from cache
    cache_key = f'otp_{user.email}'
    logger.info(f"[VERIFY_OTP] Cache key (without prefix): {cache_key}")
    logger.info(f"[VERIFY_OTP] Cache key (with prefix): vortexis:{cache_key}")
    
    # Test cache connection
    logger.info(f"[VERIFY_OTP] Testing Redis connection...")
    redis_working = test_redis_connection()
    if not redis_working:
        logger.error(f"[VERIFY_OTP] ✗ Redis is not working! Cannot verify OTP.")
        logger.error(f"[VERIFY_OTP] Please check: 1) Redis server is running, 2) Redis connection settings")
    
    logger.info(f"[VERIFY_OTP] Attempting to retrieve OTP from cache...")
    cached_otp = cache.get(cache_key)
    
    logger.info(f"[VERIFY_OTP] Cache.get() returned: {cached_otp} (type: {type(cached_otp)})")
    
    if not cached_otp:
        logger.warning(f"[VERIFY_OTP] ✗ OTP not found in cache for user {user.email}")
        logger.warning(f"[VERIFY_OTP] Cache key used: {cache_key}")
        logger.warning(f"[VERIFY_OTP] Full cache key with prefix: vortexis:{cache_key}")
        
        # Try to list all keys with similar pattern (for debugging)
        try:
            # This is a debug attempt - may not work with all cache backends
            logger.info(f"[VERIFY_OTP] Attempting to debug cache keys...")
        except Exception as debug_error:
            logger.debug(f"[VERIFY_OTP] Could not debug cache keys: {str(debug_error)}")
        
        return False
    
    logger.info(f"[VERIFY_OTP] OTP found in cache: {cached_otp}")
    
    # Verify the code matches
    logger.info(f"[VERIFY_OTP] Comparing codes - Cached: {cached_otp}, Provided: {code}")
    if cached_otp != code:
        logger.warning(f"[VERIFY_OTP] ✗ OTP code does not match for user {user.email}")
        logger.warning(f"[VERIFY_OTP] Expected: {cached_otp}, Got: {code}")
        return False
    
    logger.info(f"[VERIFY_OTP] ✓ OTP code matches!")
    
    # Delete OTP from cache after successful verification (one-time use)
    logger.info(f"[VERIFY_OTP] Deleting OTP from cache after successful verification")
    cache.delete(cache_key)
    logger.info(f"[VERIFY_OTP] OTP deleted from cache")
    
    logger.info(f"[VERIFY_OTP] ✓ OTP verified successfully for user {user.email}")
    return True


def send_otp_mail(email):
    try:

        user = User.objects.get(email=email)

        
        
        otp = generate_otp(user)


        subject = 'Vortexis Verification OTP'
        message = f'Hi {user.first_name},\n\nThank you for signing up on Vortexis. Please use the following OTP to verify your account.\n\nOTP: {otp}\n\nIf you did not sign up on Vortexis, please ignore this email.\n\nRegards,\nVortexis Team'




        
        result = NotificationService.send_notification(
            user=user,
            title=subject,
            message=message,
            category='account',
            priority='high',
            send_email=True,
            send_in_app=False,
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
        data={'reset_token': reset_token.token, 'action': 'password_reset'}
    )


def send_judge_invitation_email(email_address, hackathon, invitation_token, request):
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

    # Try to get user by email, create a temporary notification if user exists
    try:
        user = User.objects.get(email=email_address)
        NotificationService.send_notification(
            user=user,
            title=subject,
            message=message,
            category='account',
            priority='high',
            send_email=True,
            send_in_app=True,
            action_url=accept_url,
            action_text='Accept Invitation',
            data={'invitation_token': invitation_token, 'hackathon_id': hackathon.id, 'action': 'judge_invitation'}
        )
    except User.DoesNotExist:
        # For non-existing users, use direct email
        from django.core.mail import EmailMessage
        from_email = settings.DEFAULT_EMAIL_HOST
        email = EmailMessage(subject, message, from_email=from_email, to=[email_address])
        email.send(fail_silently=True)