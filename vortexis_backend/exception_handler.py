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

    request = context.get("request")
    view = context.get("view")
    logger.error(
        "Unhandled exception in API request method=%s path=%s view=%s user_id=%s",
        getattr(request, "method", None),
        getattr(request, "path", None),
        type(view).__name__ if view else None,
        getattr(getattr(request, "user", None), "id", None),
        exc_info=exc,
    )

    detail = "Internal server error."
    if settings.DEBUG:
        detail = str(exc)

    return Response({"detail": detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


