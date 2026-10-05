"""Provider-neutral authorized Sports live-source catalog."""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import json
import os
import re
from uuid import UUID
from pathlib import Path
import tempfile
from urllib.parse import urlsplit


STATE_VERSION = 1

DEFAULT_LIVE_SOURCE_CATALOG_PATH = Path(
    "/mnt/storage/configs/sportyfin/state/live-sources.json"
)


class LiveSourceCatalogError(ValueError):
    """Raised when an authorized live-source catalog is invalid."""


@dataclass(frozen=True, slots=True)
class LivePlaybackOption:
    option_id: str
    resource_source_id: str
    stream_url: str
    dispatcharr_channel_id: int
    dispatcharr_channel_uuid: str
    dispatcharr_stream_id: int

    def channel_id(self, root: str) -> str:
        return root if self.option_id == "primary" else f"{root}--{self.option_id}"

    def safe_dict(self, root: str) -> dict[str, str]:
        return {
            "option_id": self.option_id,
            "atlas_channel_id": self.channel_id(root),
            "resource_source_id": self.resource_source_id,
        }

    def state_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class LiveSource:
    source_id: str
    name: str
    stream_url: str
    provider: str | None = None
    provider_event_id: str | None = None
    standalone: bool = False
    resource_source_ids: tuple[str, ...] = ()
    playback_options: tuple[LivePlaybackOption, ...] = ()

    @property
    def event_key(self) -> tuple[str, str] | None:
        if not self.provider or not self.provider_event_id:
            return None

        return (
            self.provider,
            self.provider_event_id,
        )

    @property
    def atlas_channel_id(self) -> str:
        return f"sports-live-{self.source_id}"

    def state_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.source_id,
            "name": self.name,
            "stream_url": self.stream_url,
        }

        if self.provider is not None:
            result["provider"] = self.provider

        if self.provider_event_id is not None:
            result["provider_event_id"] = (
                self.provider_event_id
            )

        if self.standalone:
            result["standalone"] = True

        if self.resource_source_ids:
            result["resource_source_ids"] = list(
                self.resource_source_ids
            )

        if self.playback_options:
            result["playback_options"] = [option.state_dict() for option in self.playback_options]
        return result


def _required(
    value: object,
    field: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise LiveSourceCatalogError(
            f"{field} is required"
        )

    return value.strip()


def _optional(
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise LiveSourceCatalogError(
            "optional live-source fields must be strings"
        )

    value = value.strip()

    return value or None


def _stream_url(
    value: object,
) -> str:
    url = _required(
        value,
        "stream_url",
    )

    parsed = urlsplit(url)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise LiveSourceCatalogError(
            "stream_url must use an absolute "
            "http or https URL"
        )

    if parsed.username or parsed.password:
        raise LiveSourceCatalogError(
            "stream_url must not contain "
            "URL userinfo credentials"
        )

    return url


def _playback_options(value: object, root_url: str, resources: tuple[str, ...]) -> tuple[LivePlaybackOption, ...]:
    if not isinstance(value, list) or len(value) > 3:
        raise LiveSourceCatalogError("playback_options must contain at most three options")
    options = []
    for index, row in enumerate(value):
        fields = {"option_id", "resource_source_id", "stream_url", "dispatcharr_channel_id",
                  "dispatcharr_channel_uuid", "dispatcharr_stream_id"}
        if not isinstance(row, dict) or set(row) != fields:
            raise LiveSourceCatalogError("playback option fields are invalid")
        if row["option_id"] != ("primary", "backup-1", "backup-2")[index]:
            raise LiveSourceCatalogError("playback option order is invalid")
        resource = _required(row["resource_source_id"], "resource_source_id")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", resource):
            raise LiveSourceCatalogError("playback option resource is invalid")
        for field in ("dispatcharr_channel_id", "dispatcharr_stream_id"):
            if type(row[field]) is not int or row[field] <= 0:
                raise LiveSourceCatalogError("playback option identity is invalid")
        try:
            uuid = str(UUID(row["dispatcharr_channel_uuid"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise LiveSourceCatalogError("playback option UUID is invalid") from exc
        url = _stream_url(row["stream_url"])
        parsed, parent = urlsplit(url), urlsplit(root_url)
        if (parsed.scheme, parsed.netloc) != (parent.scheme, parent.netloc) or not parsed.path.rstrip("/").endswith("/" + uuid):
            raise LiveSourceCatalogError("playback option URL does not identify its Dispatcharr channel")
        options.append(LivePlaybackOption(row["option_id"], resource, url,
            row["dispatcharr_channel_id"], uuid, row["dispatcharr_stream_id"]))
    if options:
        if options[0].stream_url != root_url or tuple(o.resource_source_id for o in options) != resources:
            raise LiveSourceCatalogError("playback option resources and primary URL must match the source")
        for field in ("resource_source_id", "stream_url", "dispatcharr_channel_id", "dispatcharr_channel_uuid", "dispatcharr_stream_id"):
            values = [getattr(option, field) for option in options]
            if len(values) != len(set(values)):
                raise LiveSourceCatalogError("playback options must have independent routes and accounts")
    return tuple(options)


def _parse_source(
    entry: object,
) -> LiveSource:
    if not isinstance(entry, dict):
        raise LiveSourceCatalogError(
            "live source entries must be objects"
        )

    allowed_fields = {
        "id",
        "name",
        "stream_url",
        "provider",
        "provider_event_id",
        "standalone",
        "resource_source_ids",
        "playback_options",
    }

    if not set(entry).issubset(
        allowed_fields
    ):
        raise LiveSourceCatalogError(
            "live source entry contains "
            "unsupported fields"
        )

    source_id = _required(
        entry.get("id"),
        "id",
    )

    name = _required(
        entry.get("name"),
        "name",
    )

    stream_url = _stream_url(
        entry.get("stream_url")
    )

    provider = _optional(
        entry.get("provider")
    )

    provider_event_id = _optional(
        entry.get("provider_event_id")
    )

    standalone = bool(
        entry.get(
            "standalone",
            False,
        )
    )

    raw_resource_source_ids = entry.get(
        "resource_source_ids",
        [],
    )

    if not isinstance(
        raw_resource_source_ids,
        list,
    ):
        raise LiveSourceCatalogError(
            "resource_source_ids must be a list"
        )

    resource_source_ids: list[str] = []
    seen_resource_source_ids: set[str] = set()

    for raw_source_id in raw_resource_source_ids:
        source_id_value = _required(
            raw_source_id,
            "resource_source_ids entry",
        )

        if source_id_value in seen_resource_source_ids:
            raise LiveSourceCatalogError(
                "resource_source_ids must not contain duplicates"
            )

        seen_resource_source_ids.add(
            source_id_value
        )

        resource_source_ids.append(
            source_id_value
        )

    if bool(provider) != bool(
        provider_event_id
    ):
        raise LiveSourceCatalogError(
            "provider and provider_event_id "
            "must be supplied together"
        )

    if standalone and provider_event_id:
        raise LiveSourceCatalogError(
            "standalone sources cannot also "
            "bind to a provider event"
        )

    if (
        not standalone
        and not provider_event_id
    ):
        raise LiveSourceCatalogError(
            "a live source must be standalone "
            "or explicitly event-bound"
        )

    return LiveSource(
        source_id=source_id,
        name=name,
        stream_url=stream_url,
        provider=(
            provider.lower()
            if provider
            else None
        ),
        provider_event_id=(
            provider_event_id
        ),
        standalone=standalone,
        resource_source_ids=tuple(resource_source_ids),
        playback_options=_playback_options(entry.get("playback_options", []), stream_url, tuple(resource_source_ids)),
    )


def normalize_live_source(
    entry: object,
) -> LiveSource:
    """Validate and normalize one authorized live source."""

    return _parse_source(entry)


class LiveSourceCatalog:
    """Read-only authorized live-source mappings."""

    def __init__(
        self,
        sources: tuple[LiveSource, ...],
    ) -> None:
        self._sources = sources

        self._by_event: dict[
            tuple[str, str],
            LiveSource,
        ] = {}

        seen_ids: set[str] = set()

        for source in sources:
            if source.source_id in seen_ids:
                raise LiveSourceCatalogError(
                    "duplicate live source id: "
                    f"{source.source_id}"
                )

            seen_ids.add(
                source.source_id
            )

            if source.event_key is None:
                continue

            if (
                source.event_key
                in self._by_event
            ):
                raise LiveSourceCatalogError(
                    "duplicate live source "
                    "event mapping: "
                    f"{source.event_key[0]}:"
                    f"{source.event_key[1]}"
                )

            self._by_event[
                source.event_key
            ] = source

    @property
    def sources(
        self,
    ) -> tuple[LiveSource, ...]:
        return self._sources

    def for_event(
        self,
        provider: str,
        provider_event_id: str,
    ) -> LiveSource | None:
        return self._by_event.get(
            (
                _required(
                    provider,
                    "provider",
                ).lower(),
                _required(
                    provider_event_id,
                    "provider_event_id",
                ),
            )
        )

    def standalone_sources(
        self,
    ) -> tuple[LiveSource, ...]:
        return tuple(
            source
            for source in self._sources
            if source.standalone
        )


def _catalog_from_document(
    raw: object,
) -> LiveSourceCatalog:
    if not isinstance(raw, dict):
        raise LiveSourceCatalogError(
            "live source catalog root "
            "must be an object"
        )

    version = raw.get("version")

    # Versionless documents are accepted for
    # compatibility with the original read-only
    # catalog format. All durable writes use v1.
    if version not in {
        None,
        STATE_VERSION,
    }:
        raise LiveSourceCatalogError(
            "live source catalog version "
            "is invalid"
        )

    allowed_root_fields = {
        "version",
        "sources",
    }

    if not set(raw).issubset(
        allowed_root_fields
    ):
        raise LiveSourceCatalogError(
            "live source catalog root "
            "contains unsupported fields"
        )

    entries = raw.get(
        "sources",
        [],
    )

    if not isinstance(entries, list):
        raise LiveSourceCatalogError(
            "live source catalog sources "
            "must be a list"
        )

    return LiveSourceCatalog(
        tuple(
            _parse_source(entry)
            for entry in entries
        )
    )


def _read_catalog_path(
    path: Path,
) -> LiveSourceCatalog:
    if path.is_symlink():
        raise LiveSourceCatalogError(
            "live source catalog must "
            "not be a symlink"
        )

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except FileNotFoundError as exc:
        raise LiveSourceCatalogError(
            "live source catalog "
            f"does not exist: {path}"
        ) from exc

    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise LiveSourceCatalogError(
            "live source catalog "
            "could not be read"
        ) from exc

    return _catalog_from_document(
        raw
    )


def load_live_source_catalog(
    path: str | os.PathLike[str] | None = None,
) -> LiveSourceCatalog:
    """Load configured live sources.

    An unset environment path intentionally
    remains an empty catalog for compatibility.
    """

    configured = (
        str(path)
        if path is not None
        else os.getenv(
            "SPORTS_LIVE_SOURCE_CATALOG_PATH",
            "",
        )
    ).strip()

    if not configured:
        return LiveSourceCatalog(())

    return _read_catalog_path(
        Path(configured)
    )


class LiveSourceRegistry:
    """Durable authorized live-source state.

    Mutations are serialized by an adjacent flock
    and committed with atomic replace. Readers may
    safely consume the state without taking the
    mutation lock.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
    ) -> None:
        self.path = Path(path)
        self.lock_path = Path(
            f"{self.path}.lock"
        )

    def _validate_path(
        self,
    ) -> None:
        if self.path.is_symlink():
            raise LiveSourceCatalogError(
                "live source catalog must "
                "not be a symlink"
            )

        if self.lock_path.is_symlink():
            raise LiveSourceCatalogError(
                "live source catalog lock "
                "must not be a symlink"
            )

    def _load_existing(
        self,
    ) -> tuple[LiveSource, ...]:
        if not self.path.exists():
            return ()

        return _read_catalog_path(
            self.path
        ).sources

    def _document(
        self,
        sources: tuple[LiveSource, ...],
    ) -> dict[str, object]:
        # Revalidate duplicate identities and
        # event mappings before every commit.
        catalog = LiveSourceCatalog(
            tuple(sources)
        )

        return {
            "version": STATE_VERSION,
            "sources": [
                source.state_dict()
                for source
                in catalog.sources
            ],
        }

    def _write_locked(
        self,
        sources: tuple[LiveSource, ...],
    ) -> None:
        document = self._document(
            sources
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_name: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_name = (
                    temporary.name
                )

                json.dump(
                    document,
                    temporary,
                    indent=2,
                    sort_keys=True,
                )

                temporary.write("\n")
                temporary.flush()
                os.fsync(
                    temporary.fileno()
                )

            os.chmod(
                temporary_name,
                0o600,
            )

            os.replace(
                temporary_name,
                self.path,
            )

            temporary_name = None

            os.chmod(
                self.path,
                0o600,
            )

        finally:
            if temporary_name is not None:
                try:
                    Path(
                        temporary_name
                    ).unlink()
                except FileNotFoundError:
                    pass

    def _with_exclusive_lock(
        self,
    ):
        self._validate_path()

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lock_fd = os.open(
            self.lock_path,
            os.O_RDWR
            | os.O_CREAT,
            0o600,
        )

        os.chmod(
            self.lock_path,
            0o600,
        )

        return os.fdopen(
            lock_fd,
            "r+",
            encoding="utf-8",
        )

    def ensure(
        self,
    ) -> None:
        with self._with_exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                self._validate_path()

                if self.path.exists():
                    self._load_existing()
                    return

                self._write_locked(())

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

    def list_sources(
        self,
    ) -> tuple[LiveSource, ...]:
        self._validate_path()

        return self._load_existing()

    def add(
        self,
        source: LiveSource,
    ) -> LiveSource:
        normalized = _parse_source(
            source.state_dict()
        )

        with self._with_exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                current = (
                    self._load_existing()
                )

                if any(
                    item.source_id
                    == normalized.source_id
                    for item in current
                ):
                    raise LiveSourceCatalogError(
                        "duplicate live source id: "
                        f"{normalized.source_id}"
                    )

                updated = (
                    *current,
                    normalized,
                )

                self._write_locked(
                    tuple(updated)
                )

                return normalized

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

    def set(
        self,
        source: LiveSource,
    ) -> LiveSource:
        normalized = _parse_source(
            source.state_dict()
        )

        with self._with_exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                current = (
                    self._load_existing()
                )

                updated = tuple(
                    normalized
                    if item.source_id
                    == normalized.source_id
                    else item
                    for item in current
                )

                if not any(
                    item.source_id
                    == normalized.source_id
                    for item in current
                ):
                    updated = (
                        *updated,
                        normalized,
                    )

                self._write_locked(
                    tuple(updated)
                )

                return normalized

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )

    def delete(
        self,
        source_id: str,
    ) -> bool:
        normalized_id = _required(
            source_id,
            "source_id",
        )

        with self._with_exclusive_lock() as lock:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                current = (
                    self._load_existing()
                )

                updated = tuple(
                    item
                    for item in current
                    if (
                        item.source_id
                        != normalized_id
                    )
                )

                if len(updated) == len(
                    current
                ):
                    return False

                self._write_locked(
                    updated
                )

                return True

            finally:
                fcntl.flock(
                    lock.fileno(),
                    fcntl.LOCK_UN,
                )


def default_live_source_registry(
) -> LiveSourceRegistry:
    configured = os.getenv(
        "SPORTS_LIVE_SOURCE_CATALOG_PATH",
        "",
    ).strip()

    return LiveSourceRegistry(
        configured
        or DEFAULT_LIVE_SOURCE_CATALOG_PATH
    )


def safe_source_summary(
    source: LiveSource,
) -> dict[str, object]:
    """Return metadata without exposing stream_url."""

    result: dict[str, object] = {
        "id": source.source_id,
        "name": source.name,
        "provider": source.provider,
        "provider_event_id": (
            source.provider_event_id
        ),
        "standalone": source.standalone,
    }

    if source.resource_source_ids:
        result["atlas_channel_id"] = (
            source.atlas_channel_id
        )
        result["resource_source_ids"] = list(
            source.resource_source_ids
        )

    if source.playback_options:
        result["playback_options"] = [option.safe_dict(source.atlas_channel_id) for option in source.playback_options]
    return result


def verify_playback_option(source, option_id, lifecycle_sources, client):
    matches = [option for option in source.playback_options if option.option_id == option_id]
    if len(matches) != 1:
        raise LiveSourceCatalogError("Playback option is not configured")
    option = matches[0]
    if option.stream_url != client._base_url.rstrip("/") + "/proxy/ts/stream/" + option.dispatcharr_channel_uuid:
        raise LiveSourceCatalogError("Playback URL does not identify the configured Dispatcharr route")
    account_ids = []
    for route in source.playback_options:
        associated = [row for row in lifecycle_sources if row.source_id == route.resource_source_id]
        if len(associated) != 1:
            raise LiveSourceCatalogError("Playback account mapping is unavailable")
        reference = str(associated[0].backend_reference or "").removeprefix("dispatcharr:m3u:")
        if not reference.isascii() or not reference.isdecimal() or int(reference) <= 0:
            raise LiveSourceCatalogError("Playback account mapping is invalid")
        account_ids.append(int(reference))
    if len(account_ids) != len(set(account_ids)):
        raise LiveSourceCatalogError("Playback options must use distinct actual accounts")
    resources = [row for row in lifecycle_sources if row.source_id == option.resource_source_id]
    if len(resources) != 1 or not resources[0].enabled:
        raise LiveSourceCatalogError("Playback account is unavailable")
    resource = resources[0]
    reference = str(resource.backend_reference or "").removeprefix("dispatcharr:m3u:")
    if not reference.isascii() or not reference.isdecimal() or int(reference) <= 0:
        raise LiveSourceCatalogError("Playback account mapping is invalid")
    account_id = int(reference)
    token = client._access_token()
    channel = client._safe_channel(client._json_request("GET",
        f"/api/channels/channels/{option.dispatcharr_channel_id}/", access_token=token))
    if channel.channel_id != option.dispatcharr_channel_id or channel.channel_uuid != option.dispatcharr_channel_uuid or channel.stream_ids != (option.dispatcharr_stream_id,):
        raise LiveSourceCatalogError("Playback route changed")
    stream = client._json_request("GET", f"/api/channels/streams/{option.dispatcharr_stream_id}/", access_token=token)
    if not isinstance(stream, dict) or stream.get("id") != option.dispatcharr_stream_id or stream.get("m3u_account") != account_id or stream.get("is_stale") is not False:
        raise LiveSourceCatalogError("Playback stream account changed")
    account = client.read_account(account_id=account_id)
    if account.account_id != account_id or not account.enabled or not account.credentials_configured or not 0 < resource.max_connections <= account.configured_max_connections:
        raise LiveSourceCatalogError("Playback account capacity changed")
    return option.safe_dict(source.atlas_channel_id)
