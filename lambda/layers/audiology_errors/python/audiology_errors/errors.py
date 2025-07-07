import datetime as datetime
import logging

logger = logging.getLogger(__name__)


class AudiologyAPIError(Exception):
    """Base class for Audiology API errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationError(AudiologyAPIError):
    def __init__(self, message: str, field: str = None):
        super().__init__(message, 400, "VALIDATION_ERROR")
        self.field = field


class ResourceNotFoundError(AudiologyAPIError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} '{identifier}' not found", 404, "RESOURCE_NOT_FOUND"
        )


class ResourceConflictError(AudiologyAPIError):
    def __init__(self, message: str):
        super().__init__(message, 409, "RESOURCE_CONFLICT")


class ExternalServiceError(AudiologyAPIError):
    def __init__(self, service: str, message: str):
        super().__init__(f"{service} error: {message}", 502, "EXTERNAL_SERVICE_ERROR")
