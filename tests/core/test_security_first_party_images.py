"""Security contracts for first-party Atlas runtime images."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_DOCKERFILE = PROJECT_ROOT / "apps" / "api" / "Dockerfile"
PORTAL_DOCKERFILE = PROJECT_ROOT / "apps" / "portal" / "Dockerfile"


def test_api_removes_package_installer_after_build() -> None:
    content = API_DOCKERFILE.read_text(encoding="utf-8")

    install = "python -m pip install --no-cache-dir ."
    removal = "python -m pip uninstall --yes pip"

    assert install in content
    assert removal in content
    assert content.index(removal) > content.index(install)


def test_portal_retains_npm_only_in_build_stages() -> None:
    content = PORTAL_DOCKERFILE.read_text(encoding="utf-8")

    assert "RUN npm ci\n" in content
    assert "RUN npm run build\n" in content
    assert "rm -rf /usr/local/lib/node_modules/npm" in content
    assert "rm -f /usr/local/bin/npm /usr/local/bin/npx" in content


def test_first_party_runtime_images_remain_non_root() -> None:
    api = API_DOCKERFILE.read_text(encoding="utf-8")
    portal = PORTAL_DOCKERFILE.read_text(encoding="utf-8")

    assert "\nUSER atlas\n" in api
    assert "\nUSER nextjs\n" in portal
