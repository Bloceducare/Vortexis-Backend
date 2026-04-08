import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    logger.error("Unhandled exception in API request", exc_info=exc)

    detail = "Internal server error."
    if settings.DEBUG:
        detail = str(exc)

    return Response({"detail": detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
