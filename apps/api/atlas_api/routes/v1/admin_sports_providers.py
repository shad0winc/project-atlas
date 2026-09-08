"""Administrator-safe Sports provider/account inventory."""

from __future__ import annotations

from atlas.sports_resource_pool import (
    SportsResourcePool,
    SportsResourcePoolError,
)
from atlas_api.dependencies import (
    get_security_audit_writer,
    get_sports_resource_pool,
)

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import (
    BaseModel,
    ConfigDict,
)

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.security import require_permission
from atlas_api.services.sports import (
    SportsProviderAccountConflictError,
    SportsProviderAccountInvalidError,
    SportsProviderAccountNotFoundError,
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
    build_default_sports_api_service,
)


router = APIRouter(
    prefix="/admin/sports/providers",
    tags=["admin-sports-providers"],
)

SPORTS_PROVIDERS_MANAGE_PERMISSION = (
    "sports.providers.manage"
)

require_sports_providers_manage = require_permission(
    SPORTS_PROVIDERS_MANAGE_PERMISSION
)


class _StrictAdminSportsModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )


class AdminSportsAccountResponse(
    _StrictAdminSportsModel
):
    source_id: str
    display_name: str
    account_display_name: str
    enabled: bool
    kind: str
    trust_class: str
    priority: int
    max_connections: int
    expires_at: str | None = None
    backend_configured: bool


class AdminSportsProviderResponse(
    _StrictAdminSportsModel
):
    provider_id: str
    display_name: str
    account_count: int
    enabled_account_count: int
    configured_max_connections: int
    enabled_max_connections: int
    accounts: list[AdminSportsAccountResponse]


class AdminSportsProviderListResponse(
    _StrictAdminSportsModel
):
    providers: list[AdminSportsProviderResponse]


class AdminSportsResourceAccountResponse(
    _StrictAdminSportsModel
):
    source_id: str
    enabled: bool
    capacity: int
    active: int
    available: int


class AdminSportsResourcePoolResponse(
    _StrictAdminSportsModel
):
    total_capacity: int
    active: int
    available: int
    accounts: list[AdminSportsResourceAccountResponse]


def get_admin_sports_service(
) -> SportsWriterBackedAPIService:
    service = build_default_sports_api_service()

    if not isinstance(
        service,
        SportsWriterBackedAPIService,
    ):
        raise RuntimeError(
            "Sports provider administration requires "
            "the private writer-backed service."
        )

    return service


def _required_text(
    mapping: dict[str, Any],
    field: str,
) -> str:
    value = str(
        mapping.get(field, "")
    ).strip()

    if not value:
        raise SportsWriterTransportError(
            "Private Sports service returned "
            f"incomplete {field} metadata."
        )

    return value


def _required_int(
    mapping: dict[str, Any],
    field: str,
) -> int:
    value = mapping.get(field)

    if isinstance(value, bool):
        raise SportsWriterTransportError(
            "Private Sports service returned "
            f"invalid {field} metadata."
        )

    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise SportsWriterTransportError(
            "Private Sports service returned "
            f"invalid {field} metadata."
        ) from error

    if parsed < 0:
        raise SportsWriterTransportError(
            "Private Sports service returned "
            f"invalid {field} metadata."
        )

    return parsed


def _response(
    registry: dict[str, list[dict[str, Any]]],
) -> AdminSportsProviderListResponse:
    raw_providers = registry["providers"]
    raw_sources = registry["sources"]

    accounts_by_provider: dict[
        str,
        list[AdminSportsAccountResponse],
    ] = {}

    for source in raw_sources:
        provider_id = _required_text(
            source,
            "provider_id",
        )

        source_id = _required_text(
            source,
            "source_id",
        )

        display_name = _required_text(
            source,
            "display_name",
        )

        account_display_name = _required_text(
            source,
            "account_display_name",
        )

        kind = _required_text(
            source,
            "kind",
        )

        trust_class = _required_text(
            source,
            "trust_class",
        )

        enabled = source.get("enabled")

        if not isinstance(enabled, bool):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid enabled metadata."
            )

        backend_reference = source.get(
            "backend_reference"
        )

        backend_configured = (
            isinstance(backend_reference, str)
            and bool(
                backend_reference.strip()
            )
        )

        expires_at_raw = source.get(
            "expires_at"
        )

        expires_at = (
            str(expires_at_raw).strip()
            if expires_at_raw is not None
            else None
        )

        accounts_by_provider.setdefault(
            provider_id,
            [],
        ).append(
            AdminSportsAccountResponse(
                source_id=source_id,
                display_name=display_name,
                account_display_name=(
                    account_display_name
                ),
                enabled=enabled,
                kind=kind,
                trust_class=trust_class,
                priority=_required_int(
                    source,
                    "priority",
                ),
                max_connections=_required_int(
                    source,
                    "max_connections",
                ),
                expires_at=expires_at,
                backend_configured=(
                    backend_configured
                ),
            )
        )

    providers: list[
        AdminSportsProviderResponse
    ] = []

    for provider in raw_providers:
        provider_id = _required_text(
            provider,
            "provider_id",
        )

        accounts = sorted(
            accounts_by_provider.get(
                provider_id,
                [],
            ),
            key=lambda item: (
                item.priority,
                item.source_id,
            ),
        )

        account_count = _required_int(
            provider,
            "account_count",
        )

        if account_count != len(accounts):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "inconsistent provider account metadata."
            )

        providers.append(
            AdminSportsProviderResponse(
                provider_id=provider_id,
                display_name=_required_text(
                    provider,
                    "display_name",
                ),
                account_count=account_count,
                enabled_account_count=(
                    _required_int(
                        provider,
                        "enabled_account_count",
                    )
                ),
                configured_max_connections=(
                    _required_int(
                        provider,
                        "configured_max_connections",
                    )
                ),
                enabled_max_connections=(
                    _required_int(
                        provider,
                        "enabled_max_connections",
                    )
                ),
                accounts=accounts,
            )
        )

    known_provider_ids = {
        provider.provider_id
        for provider in providers
    }

    orphan_provider_ids = (
        set(accounts_by_provider)
        - known_provider_ids
    )

    if orphan_provider_ids:
        raise SportsWriterTransportError(
            "Private Sports service returned "
            "orphan account metadata."
        )

    return AdminSportsProviderListResponse(
        providers=sorted(
            providers,
            key=lambda item: (
                item.display_name.casefold(),
                item.provider_id,
            ),
        )
    )


@router.get(
    "",
    response_model=AdminSportsProviderListResponse,
    summary=(
        "List administrator-safe Sports "
        "providers and accounts"
    ),
)
def read_admin_sports_providers(
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
) -> AdminSportsProviderListResponse:
    try:
        registry = service.get_source_registry()
        return _response(registry)
    except SportsWriterTransportError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider administration "
                "is unavailable."
            ),
        ) from error


@router.get(
    "/resource-pool",
    response_model=AdminSportsResourcePoolResponse,
    summary="Read administrator-safe Sports resource-pool utilization",
)
def read_admin_sports_resource_pool(
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
    resource_pool: SportsResourcePool = Depends(
        get_sports_resource_pool
    ),
) -> AdminSportsResourcePoolResponse:
    try:
        registry = service.get_source_registry()

        capacities: dict[str, int] = {}
        enabled_by_source: dict[str, bool] = {}

        for source in registry["sources"]:
            source_id = _required_text(
                source,
                "source_id",
            )

            enabled = source.get(
                "enabled"
            )

            if not isinstance(enabled, bool):
                raise SportsWriterTransportError(
                    "Private Sports service returned "
                    "invalid enabled metadata."
                )

            configured_capacity = _required_int(
                source,
                "max_connections",
            )

            capacities[source_id] = (
                configured_capacity
                if enabled
                else 0
            )
            enabled_by_source[source_id] = enabled

        snapshot = resource_pool.snapshot(
            capacities=capacities
        )

        return AdminSportsResourcePoolResponse(
            total_capacity=snapshot.total_capacity,
            active=snapshot.active,
            available=snapshot.available,
            accounts=[
                AdminSportsResourceAccountResponse(
                    source_id=item.source_id,
                    enabled=enabled_by_source[
                        item.source_id
                    ],
                    capacity=item.capacity,
                    active=item.active,
                    available=item.available,
                )
                for item in snapshot.sources
            ],
        )
    except (
        SportsWriterTransportError,
        SportsResourcePoolError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Sports resource-pool administration "
                "is unavailable."
            ),
        ) from error


class AdminSportsProviderUpdateRequest(
    _StrictAdminSportsModel
):
    display_name: str


class AdminSportsAccountUpdateRequest(
    _StrictAdminSportsModel
):
    account_display_name: str | None = None
    enabled: bool | None = None
    max_connections: int | None = None


def _normalized_label(
    value: str,
    *,
    field: str,
) -> str:
    normalized = value.strip()

    if (
        not normalized
        or len(normalized) > 128
        or any(
            ord(character) < 32
            for character in normalized
        )
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=f"{field} is invalid.",
        )

    return normalized


def _source_belongs_to_provider(
    registry: dict[
        str,
        list[dict[str, Any]],
    ],
    *,
    provider_id: str,
    source_id: str,
) -> bool:
    return any(
        (
            str(
                source.get(
                    "provider_id",
                    "",
                )
            ).strip()
            == provider_id
        )
        and (
            str(
                source.get(
                    "source_id",
                    "",
                )
            ).strip()
            == source_id
        )
        for source in registry["sources"]
    )


def _provider_exists(
    registry: dict[
        str,
        list[dict[str, Any]],
    ],
    provider_id: str,
) -> bool:
    return any(
        str(
            provider.get(
                "provider_id",
                "",
            )
        ).strip()
        == provider_id
        for provider in registry["providers"]
    )


@router.patch(
    "/{provider_id}",
    response_model=AdminSportsProviderListResponse,
    summary="Rename one Sports provider",
)
def update_admin_sports_provider(
    provider_id: str,
    request: AdminSportsProviderUpdateRequest,
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
) -> AdminSportsProviderListResponse:
    normalized_provider_id = (
        provider_id.strip()
    )

    if not normalized_provider_id:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="Sports provider was not found.",
        )

    display_name = _normalized_label(
        request.display_name,
        field="Provider display name",
    )

    try:
        current = service.get_source_registry()

        if not _provider_exists(
            current,
            normalized_provider_id,
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Sports provider "
                    "was not found."
                ),
            )

        updated = (
            service.update_provider_display_name(
                provider_id=(
                    normalized_provider_id
                ),
                display_name=display_name,
            )
        )

        return _response(updated)

    except HTTPException:
        raise

    except (
        SportsWriterTransportError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider administration "
                "is unavailable."
            ),
        ) from error


@router.patch(
    "/{provider_id}/accounts/{source_id}",
    response_model=AdminSportsProviderListResponse,
    summary="Update safe Sports provider account metadata",
)
def update_admin_sports_account(
    provider_id: str,
    source_id: str,
    request: AdminSportsAccountUpdateRequest,
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
) -> AdminSportsProviderListResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        source_id.strip()
    )

    if (
        not normalized_provider_id
        or not normalized_source_id
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Sports provider account "
                "was not found."
            ),
        )

    fields: dict[str, Any] = {}

    if (
        request.account_display_name
        is not None
    ):
        fields["account_display_name"] = (
            _normalized_label(
                request.account_display_name,
                field=(
                    "Account display name"
                ),
            )
        )

    if request.enabled is not None:
        fields["enabled"] = request.enabled

    if request.max_connections is not None:
        if request.max_connections < 1:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Account connection limit "
                    "must be a positive integer."
                ),
            )

        fields["max_connections"] = (
            request.max_connections
        )

    if not fields:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "At least one editable account "
                "field is required."
            ),
        )

    try:
        current = service.get_source_registry()

        if not _source_belongs_to_provider(
            current,
            provider_id=(
                normalized_provider_id
            ),
            source_id=(
                normalized_source_id
            ),
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Sports provider account "
                    "was not found."
                ),
            )

        updated = service.update_source_metadata(
            source_id=normalized_source_id,
            fields=fields,
        )

        return _response(updated)

    except HTTPException:
        raise

    except (
        SportsWriterTransportError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider administration "
                "is unavailable."
            ),
        ) from error


class AdminSportsDispatcharrAccountResponse(
    _StrictAdminSportsModel
):
    account_id: int
    name: str
    account_type: str
    enabled: bool
    configured_max_connections: int
    credentials_configured: bool


class AdminSportsConnectionTestResponse(
    _StrictAdminSportsModel
):
    ok: bool
    status: str
    expires_at: str | None = None
    provider_max_connections: int | None = None
    active_connections: int | None = None


def _require_provider_account(
    service: SportsWriterBackedAPIService,
    *,
    provider_id: str,
    source_id: str,
) -> None:
    registry = (
        service.get_source_registry()
    )

    if not _source_belongs_to_provider(
        registry,
        provider_id=provider_id,
        source_id=source_id,
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Sports provider account "
                "was not found."
            ),
        )


@router.get(
    "/{provider_id}/accounts/{source_id}/connection",
    response_model=(
        AdminSportsDispatcharrAccountResponse
    ),
    summary=(
        "Read secret-safe Sports provider "
        "connection configuration"
    ),
)
def read_admin_sports_account_connection(
    provider_id: str,
    source_id: str,
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
) -> AdminSportsDispatcharrAccountResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        source_id.strip()
    )

    try:
        _require_provider_account(
            service,
            provider_id=(
                normalized_provider_id
            ),
            source_id=(
                normalized_source_id
            ),
        )

        account = (
            service.get_dispatcharr_account(
                source_id=(
                    normalized_source_id
                )
            )
        )

        return (
            AdminSportsDispatcharrAccountResponse(
                **account
            )
        )

    except HTTPException:
        raise

    except (
        SportsWriterTransportError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider connection "
                "configuration is unavailable."
            ),
        ) from error


@router.post(
    "/{provider_id}/accounts/{source_id}/test-connection",
    response_model=(
        AdminSportsConnectionTestResponse
    ),
    summary=(
        "Test one Sports provider "
        "connection without activation"
    ),
)
def test_admin_sports_account_connection(
    provider_id: str,
    source_id: str,
    _current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
) -> AdminSportsConnectionTestResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        source_id.strip()
    )

    try:
        _require_provider_account(
            service,
            provider_id=(
                normalized_provider_id
            ),
            source_id=(
                normalized_source_id
            ),
        )

        result = (
            service.test_dispatcharr_connection(
                source_id=(
                    normalized_source_id
                )
            )
        )

        return (
            AdminSportsConnectionTestResponse(
                **result
            )
        )

    except HTTPException:
        raise

    except (
        SportsWriterTransportError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider connection "
                "test is unavailable."
            ),
        ) from error



class AdminSportsConnectionUpdateRequest(
    _StrictAdminSportsModel
):
    server_url: str | None = None
    username: str | None = None
    password: str | None = None


@router.patch(
    "/{provider_id}/accounts/{source_id}/credentials",
    response_model=(
        AdminSportsDispatcharrAccountResponse
    ),
    summary=(
        "Update one Sports provider "
        "account connection"
    ),
)
def update_admin_sports_account_credentials(
    provider_id: str,
    source_id: str,
    request: AdminSportsConnectionUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
    audit_writer=Depends(
        get_security_audit_writer
    ),
) -> AdminSportsDispatcharrAccountResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        source_id.strip()
    )

    submitted = request.model_dump(
        exclude_unset=True
    )

    if not submitted:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "At least one provider "
                "connection field is required."
            ),
        )

    try:
        _require_provider_account(
            service,
            provider_id=(
                normalized_provider_id
            ),
            source_id=(
                normalized_source_id
            ),
        )

        account = (
            service.update_dispatcharr_credentials(
                source_id=(
                    normalized_source_id
                ),
                server_url=(
                    submitted.get(
                        "server_url"
                    )
                ),
                username=(
                    submitted.get(
                        "username"
                    )
                ),
                password=(
                    submitted.get(
                        "password"
                    )
                ),
            )
        )

    except HTTPException:
        raise

    except (
        SportsWriterTransportError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Sports provider connection "
                "settings could not be updated."
            ),
        ) from error

    # Intentionally record stable identity only.
    # Never place submitted authentication data,
    # request fields, backend IDs, or provider URLs
    # in the security audit payload.
    audit_writer.publish(
        "security.sports.provider_connection_updated",
        {
            "actor_user_id": (
                current_user.user_id
            ),
            "provider_id": (
                normalized_provider_id
            ),
            "source_id": (
                normalized_source_id
            ),
        },
    )

    return (
        AdminSportsDispatcharrAccountResponse(
            **account
        )
    )

class AdminSportsProviderAccountCreateRequest(
    _StrictAdminSportsModel
):
    source_id: str
    provider_display_name: str
    account_display_name: str
    server_url: str
    username: str
    password: str
    max_connections: int
    priority: int = 100


class AdminSportsProviderAccountRemoveResponse(
    _StrictAdminSportsModel
):
    removed: bool
    source_id: str


def _provider_account_source(
    registry: dict[str, list[dict[str, Any]]],
    *,
    provider_id: str,
    source_id: str,
) -> dict[str, Any] | None:
    for source in registry["sources"]:
        if (
            _required_text(
                source,
                "provider_id",
            )
            == provider_id
            and _required_text(
                source,
                "source_id",
            )
            == source_id
        ):
            return source

    return None


@router.post(
    "/{provider_id}/accounts",
    response_model=AdminSportsProviderListResponse,
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Create one disabled Sports provider "
        "account securely"
    ),
)
def create_admin_sports_provider_account(
    provider_id: str,
    request: AdminSportsProviderAccountCreateRequest,
    current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
    audit_writer=Depends(
        get_security_audit_writer
    ),
) -> AdminSportsProviderListResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        request.source_id.strip()
    )

    if (
        not normalized_provider_id
        or not normalized_source_id
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Provider and source identities "
                "are required."
            ),
        )

    if (
        isinstance(
            request.max_connections,
            bool,
        )
        or request.max_connections <= 0
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Provider account capacity must "
                "be a positive integer."
            ),
        )

    if (
        isinstance(
            request.priority,
            bool,
        )
        or request.priority < 0
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Provider account priority must "
                "be a non-negative integer."
            ),
        )

    try:
        updated = (
            service.create_provider_account(
                source_id=(
                    normalized_source_id
                ),
                provider_id=(
                    normalized_provider_id
                ),
                provider_display_name=(
                    request.provider_display_name
                ),
                account_display_name=(
                    request.account_display_name
                ),
                server_url=(
                    request.server_url
                ),
                username=(
                    request.username
                ),
                password=(
                    request.password
                ),
                max_connections=(
                    request.max_connections
                ),
                priority=(
                    request.priority
                ),
            )
        )

    except SportsProviderAccountConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Sports provider account "
                "already exists or conflicts "
                "with current provider state."
            ),
        ) from error

    except (
        SportsProviderAccountInvalidError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Sports provider account "
                "configuration is invalid."
            ),
        ) from error

    except (
        SportsProviderAccountNotFoundError,
        SportsWriterTransportError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider account "
                "creation is unavailable."
            ),
        ) from error

    # Credentials are deliberately absent from
    # audit metadata. Only stable Atlas identity
    # is recorded.
    audit_writer.publish(
        "security.sports.provider_account_created",
        {
            "actor_user_id": (
                current_user.user_id
            ),
            "provider_id": (
                normalized_provider_id
            ),
            "source_id": (
                normalized_source_id
            ),
        },
    )

    return _response(updated)


@router.delete(
    "/{provider_id}/accounts/{source_id}",
    response_model=(
        AdminSportsProviderAccountRemoveResponse
    ),
    summary=(
        "Remove one disabled Sports provider "
        "account when no upstream lease is active"
    ),
)
def remove_admin_sports_provider_account(
    provider_id: str,
    source_id: str,
    current_user: AuthenticatedUser = Depends(require_sports_providers_manage),
    service: SportsWriterBackedAPIService = Depends(
        get_admin_sports_service
    ),
    resource_pool: SportsResourcePool = Depends(
        get_sports_resource_pool
    ),
    audit_writer=Depends(
        get_security_audit_writer
    ),
) -> AdminSportsProviderAccountRemoveResponse:
    normalized_provider_id = (
        provider_id.strip()
    )
    normalized_source_id = (
        source_id.strip()
    )

    try:
        registry = service.get_source_registry()

        source = _provider_account_source(
            registry,
            provider_id=(
                normalized_provider_id
            ),
            source_id=(
                normalized_source_id
            ),
        )

        if source is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_404_NOT_FOUND
                ),
                detail=(
                    "Sports provider account "
                    "was not found."
                ),
            )

        enabled = source.get("enabled")

        if not isinstance(enabled, bool):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid enabled metadata."
            )

        if enabled:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Disable the Sports provider "
                    "account before removing it."
                ),
            )

        # The disabled account contributes zero
        # future capacity, but snapshot still
        # reports leases that are already active
        # for this exact source_id.
        snapshot = resource_pool.snapshot(
            capacities={
                normalized_source_id: 0,
            }
        )

        resource_source = next(
            (
                item
                for item in snapshot.sources
                if item.source_id
                == normalized_source_id
            ),
            None,
        )

        if resource_source is None:
            raise SportsWriterTransportError(
                "Sports resource pool omitted "
                "the provider account."
            )

        active = resource_source.active

        if (
            isinstance(active, bool)
            or not isinstance(active, int)
            or active < 0
        ):
            raise SportsWriterTransportError(
                "Sports resource pool returned "
                "invalid active lease metadata."
            )

        if active > 0:
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Sports provider account has "
                    "active upstream leases."
                ),
            )

        removed = (
            service.remove_provider_account(
                source_id=(
                    normalized_source_id
                )
            )
        )

        if removed is not True:
            raise SportsWriterTransportError(
                "Sports provider account removal "
                "was not confirmed."
            )

    except HTTPException:
        raise

    except SportsProviderAccountNotFoundError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "Sports provider account "
                "was not found."
            ),
        ) from error

    except SportsProviderAccountConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Sports provider account cannot "
                "be removed while playback "
                "dependencies exist."
            ),
        ) from error

    except (
        SportsProviderAccountInvalidError,
        SportsWriterTransportError,
        SportsResourcePoolError,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Sports provider account "
                "removal is unavailable."
            ),
        ) from error

    audit_writer.publish(
        "security.sports.provider_account_removed",
        {
            "actor_user_id": (
                current_user.user_id
            ),
            "provider_id": (
                normalized_provider_id
            ),
            "source_id": (
                normalized_source_id
            ),
        },
    )

    return (
        AdminSportsProviderAccountRemoveResponse(
            removed=True,
            source_id=(
                normalized_source_id
            ),
        )
    )
