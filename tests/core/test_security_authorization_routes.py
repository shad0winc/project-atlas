"""Fail-closed route coverage for Atlas API authorization."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROUTES_ROOT = Path("apps/api/atlas_api/routes/v1")

# These endpoints are intentionally usable without an access-token permission
# dependency. Login establishes a session; refresh and logout authenticate with
# the supplied refresh credential; health intentionally exposes no user data.
INTENTIONALLY_PUBLIC_ROUTES = frozenset(
    {
        ("auth.py", "POST", "/login"),
        ("auth.py", "POST", "/refresh"),
        ("auth.py", "POST", "/logout"),
        ("auth.py", "POST", "/password-recovery/request"),
        ("auth.py", "POST", "/password-recovery/reset"),
        ("health.py", "GET", "/health"),
    }
)


@dataclass(frozen=True)
class RouteContract:
    source: str
    method: str
    path: str
    function: str
    protected: bool

    @property
    def identity(self) -> tuple[str, str, str]:
        return (self.source, self.method, self.path)


def _route_contracts() -> tuple[RouteContract, ...]:
    contracts: list[RouteContract] = []

    for path in sorted(ROUTES_ROOT.glob("*.py")):
        if path.name == "__init__.py":
            continue

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            function_source = ast.get_source_segment(source, node) or ""
            protected = (
                "Depends(require_" in function_source
                or "Depends(get_current_user" in function_source
            )

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue

                func = decorator.func
                if not (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "router"
                ):
                    continue

                if not decorator.args:
                    raise AssertionError(
                        f"route decorator has no literal path: {path}:{node.lineno}"
                    )

                route_path = decorator.args[0]
                if not (
                    isinstance(route_path, ast.Constant)
                    and isinstance(route_path.value, str)
                ):
                    raise AssertionError(
                        f"route path is not a string literal: {path}:{node.lineno}"
                    )

                contracts.append(
                    RouteContract(
                        source=path.name,
                        method=func.attr.upper(),
                        path=route_path.value,
                        function=node.name,
                        protected=protected,
                    )
                )

    return tuple(contracts)


def test_intentionally_public_route_set_is_exact() -> None:
    routes = _route_contracts()
    observed_public = frozenset(
        route.identity for route in routes if not route.protected
    )

    assert observed_public == INTENTIONALLY_PUBLIC_ROUTES


def test_every_non_public_v1_route_has_authorization_dependency() -> None:
    unprotected = [
        route
        for route in _route_contracts()
        if route.identity not in INTENTIONALLY_PUBLIC_ROUTES
        and not route.protected
    ]

    assert unprotected == []


def test_public_routes_never_expand_implicitly() -> None:
    routes = _route_contracts()
    identities = {route.identity for route in routes}

    assert INTENTIONALLY_PUBLIC_ROUTES <= identities
    assert len(INTENTIONALLY_PUBLIC_ROUTES) == 6
