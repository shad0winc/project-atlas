"""Security contracts for first-party Atlas runtime images."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_DOCKERFILE = PROJECT_ROOT / "apps" / "api" / "Dockerfile"
PORTAL_DOCKERFILE = PROJECT_ROOT / "apps" / "portal" / "Dockerfile"
NOTIFICATIONS_DOCKERFILE = (
    PROJECT_ROOT / "modules" / "notifications" / "Dockerfile"
)
SPORTS_DOCKERFILE = PROJECT_ROOT / "modules" / "sports" / "Dockerfile"


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
    dockerfiles = {
        "api": (API_DOCKERFILE, "atlas"),
        "portal": (PORTAL_DOCKERFILE, "nextjs"),
        "notifications": (NOTIFICATIONS_DOCKERFILE, "atlas"),
        "sports": (SPORTS_DOCKERFILE, "atlas"),
    }

    for name, (path, user) in dockerfiles.items():
        content = path.read_text(encoding="utf-8")
        assert f"\nUSER {user}\n" in content, (
            f"{name} runtime image must use explicit non-root user {user}"
        )


def test_module_runtime_images_require_operator_identity_build_arguments() -> None:
    for path in (NOTIFICATIONS_DOCKERFILE, SPORTS_DOCKERFILE):
        content = path.read_text(encoding="utf-8")

        assert "\nARG PUID\n" in content
        assert "\nARG PGID\n" in content
        assert "ARG PUID=1000" not in content
        assert "ARG PGID=1000" not in content
        assert 'groupadd --gid "${PGID}" atlas' in content
        assert '--uid "${PUID}"' in content
        assert "--gid atlas" in content
