"""Public API foundation contracts for Project Atlas."""

from .errors import (
    ApiContractError,
    ApiError,
)
from .responses import (
    ApiFailureResponse,
    ApiSuccessResponse,
)
from .serialization import (
    ApiSerializationError,
    to_api_json,
    to_api_value,
)
from .version import (
    API_MEDIA_TYPE,
    API_SCHEMA_VERSION,
    API_VERSION,
)


__all__ = [
    "API_MEDIA_TYPE",
    "API_SCHEMA_VERSION",
    "API_VERSION",
    "ApiContractError",
    "ApiError",
    "ApiFailureResponse",
    "ApiSerializationError",
    "ApiSuccessResponse",
    "to_api_json",
    "to_api_value",
]
