"""Atlas media-request domain."""

from .models import (
    MediaRequest,
    MediaRequestError,
    MediaRequestStatus,
    MediaRequestType,
)
from .provider import (
    MediaRequestProvider,
    MediaRequestProviderError,
    MediaRequestProviderOperationError,
    ProviderCapabilities,
    ProviderEventContext,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from .providers import (
    BaseMediaRequestHTTPProvider,
    JellyseerrMediaRequestProvider,
    MediaRequestHTTPError,
    default_jellyseerr_media_request_provider,
)
from .repository import (
    JsonMediaRequestRepository,
    MediaRequestRepositoryError,
    SCHEMA_VERSION,
)
from .service import (
    MediaRequestService,
    MediaRequestServiceError,
)

__all__ = [
    "BaseMediaRequestHTTPProvider",
    "JellyseerrMediaRequestProvider",
    "JsonMediaRequestRepository",
    "MediaRequest",
    "MediaRequestError",
    "MediaRequestHTTPError",
    "MediaRequestProvider",
    "MediaRequestProviderError",
    "MediaRequestProviderOperationError",
    "MediaRequestRepositoryError",
    "MediaRequestService",
    "MediaRequestServiceError",
    "MediaRequestStatus",
    "MediaRequestType",
    "ProviderCapabilities",
    "ProviderEventContext",
    "ProviderHealth",
    "ProviderHealthStatus",
    "ProviderStatusResult",
    "ProviderSubmissionResult",
    "SCHEMA_VERSION",
    "default_jellyseerr_media_request_provider",
]
