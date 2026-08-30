"""HTTP contract tests for the read-only Downloads API."""
from __future__ import annotations
from fastapi.testclient import TestClient
from atlas.downloads import DownloadItem, DownloadsError, DownloadsSnapshot, DownloadState
from atlas_api.dependencies import get_downloads_service
from atlas_api.main import create_app
from atlas_api.routes.v1.downloads import require_downloads_read

class FakeDownloadsService:
    def __init__(self) -> None:
        self.fail=False
        self.calls=0
    def current(self) -> DownloadsSnapshot:
        self.calls += 1
        if self.fail:
            raise DownloadsError("private provider detail")
        return DownloadsSnapshot.build((DownloadItem(name="Example",category="tv",state=DownloadState.DOWNLOADING,progress=0.5,total_bytes=1000,downloaded_bytes=500,download_rate=100,upload_rate=10,eta_seconds=5),),total_download_rate=100,total_upload_rate=10)

def _client(service):
    app=create_app()
    app.dependency_overrides[get_downloads_service]=lambda: service
    app.dependency_overrides[require_downloads_read]=lambda: object()
    return app,TestClient(app)

def test_downloads_route_returns_bounded_snapshot():
    s=FakeDownloadsService(); app,c=_client(s)
    try: r=c.get("/api/v1/downloads")
    finally: app.dependency_overrides.clear(); c.close()
    assert r.status_code==200
    p=r.json(); assert p["schema_version"]==1 and p["summary"]["active"]==1
    assert p["downloads"][0]["name"]=="Example" and s.calls==1
    low=r.text.lower()
    for forbidden in ("hash","magnet","tracker","peer","save_path","content_path","password","cookie"): assert forbidden not in low

def test_downloads_route_maps_runtime_failure_to_generic_503():
    s=FakeDownloadsService(); s.fail=True; app,c=_client(s)
    try: r=c.get("/api/v1/downloads")
    finally: app.dependency_overrides.clear(); c.close()
    assert r.status_code==503
    assert r.json()=={"detail":"Downloads runtime data is unavailable."}
    assert "private provider detail" not in r.text

def test_downloads_route_is_get_only():
    s=FakeDownloadsService(); app,c=_client(s)
    try: r=c.post("/api/v1/downloads",json={})
    finally: app.dependency_overrides.clear(); c.close()
    assert r.status_code==405
