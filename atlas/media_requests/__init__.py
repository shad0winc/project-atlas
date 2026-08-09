"""Atlas media-request domain."""

from .discovery import (
    MediaDiscoveryAvailability,
    MediaDiscoveryError,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
)
from .events import (
    MediaRequestEvent,
    MediaRequestEventError,
    MediaRequestEventType,
    event_type_for_status,
)
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
    "MediaDiscoveryAvailability",
    "MediaDiscoveryError",
    "MediaDiscoveryItem",
    "MediaDiscoveryPage",
    "JellyseerrMediaRequestProvider",
    "JsonMediaRequestRepository",
    "MediaRequest",
    "MediaRequestError",
    "MediaRequestEvent",
    "MediaRequestEventError",
    "MediaRequestEventType",
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
    "event_type_for_status",
]
