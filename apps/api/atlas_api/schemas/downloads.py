"""Read-only Downloads response schemas."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict

class DownloadsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: int
    generated_at: str
    summary: dict[str, Any]
    downloads: tuple[dict[str, Any], ...]

    @classmethod
    def from_domain(cls, snapshot: object) -> "DownloadsResponse":
        serializer = getattr(snapshot, "to_dict", None)
        if not callable(serializer):
            raise TypeError("Downloads API value must expose to_dict()")
        payload = serializer()
        if not isinstance(payload, dict):
            raise TypeError("Downloads to_dict() must return a dictionary")
        return cls.model_validate(payload)

__all__ = ["DownloadsResponse"]
