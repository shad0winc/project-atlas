"""Health endpoint response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Stable health response returned by the Atlas API."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: Literal["ok"]
    service: Literal["atlas-api"]
    api_version: Literal["v1"]
