import datetime as datetime
import logging

logger = logging.getLogger(__name__)


class AudiologyAPIError(Exception):
    """Base class for Audiology API errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InternalServerError(AudiologyAPIError):
    """For server-side violated invariants--e.g., env variables not set."""

    def __init__(self):
        super().__init__(message, 500)
        self.timestamp = datetime.datetime.utcnow().isoformat()
        logger.error(f"Internal Server Error at {self.timestamp}")


class ValidationError(AudiologyAPIError):
    """For invalid requests--e.g., missing required fields or invalid data types."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, 400, "VALIDATION_ERROR")
        self.field = field
