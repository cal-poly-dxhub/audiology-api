from audiology_errors.errors import (
    AudiologyAPIError,
    ExternalServiceError,
)
from datetime import datetime
from functools import wraps
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


def create_error_response(error: AudiologyAPIError, request_id: str = None) -> dict:
    """Create standardized error response to give back to the client"""
    response_body = {
        "error": {
            "code": error.error_code or "INTERNAL_ERROR",
            "message": error.message,
            "timestamp": datetime.now().isoformat(),
        }
    }

    if request_id:
        response_body["error"]["request_id"] = request_id

    if hasattr(error, "field") and error.field:
        response_body["error"]["field"] = error.field

    return {
        "statusCode": error.status_code,
        "body": response_body,
        "headers": {"Content-Type": "application/json"},
    }


def handle_errors(func):
    """Decorator for formatting errors raised in user-facing functions (e.g., top-level route handlers that construct the response passed to the user directly)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AudiologyAPIError as e:
            logger.error(
                f"API Error in {func.__name__}: {e.message}",
                extra={"error_code": e.error_code, "status_code": e.status_code},
            )
            return create_error_response(e)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(
                f"AWS Client Error in {func.__name__}: {error_code}",
                extra={"aws_error": str(e)},
            )
            aws_error = ExternalServiceError("AWS", f"Service error: {error_code}")
            return create_error_response(aws_error)
        except Exception as e:
            logger.error(
                f"Unexpected error in {func.__name__}: {str(e)}", exc_info=True
            )
            internal_error = AudiologyAPIError(
                "An unexpected error occurred", 500, "INTERNAL_ERROR"
            )
            return create_error_response(internal_error)

    return wrapper
