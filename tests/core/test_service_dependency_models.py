"""Contract tests for Service Lifecycle dependency graph models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    InfrastructureDependencyGraph,
    ManagedService,
    ServiceDependencyNode,
    ServiceLifecycleError,
)
from atlas.service_lifecycle.service import (
    InfrastructureDependencyGraph as CompatibilityGraph,
)
from atlas.service_lifecycle.service import (
    ServiceDependencyNode as CompatibilityNode,
)


def managed(
    identifier: str,
    *,
    name: str | None = None,
    provider: str = "docker-compose",
    compose_project: str | None = "project-atlas",
) -> ManagedService:
    return ManagedService(
        identifier=identifier,
        name=name or identifier.title(),
        provider=provider,
        compose_project=compose_project,
    )


def test_dependency_node_is_immutable() -> None:
    node = ServiceDependencyNode(service=managed("jellyfin"))
    with pytest.raises(FrozenInstanceError):
        node.service = managed("sonarr")  # type: ignore[misc]


def test_dependency_node_requires_service_identity() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="require ManagedService identities",
    ):
        ServiceDependencyNode(service="jellyfin")  # type: ignore[arg-type]


def test_dependency_node_normalizes_collections_and_order() -> None:
    node = ServiceDependencyNode(
        service=managed("jellyseerr"),
        dependencies=[managed("sonarr"), managed("jellyfin")],  # type: ignore[arg-type]
        dependents=[managed("tautulli"), managed("homepage")],  # type: ignore[arg-type]
        unresolved_dependencies=[" Zeta ", "ALPHA"],  # type: ignore[arg-type]
    )
    assert tuple(item.identifier for item in node.dependencies) == (
        "jellyfin",
        "sonarr",
    )
    assert tuple(item.identifier for item in node.dependents) == (
        "homepage",
        "tautulli",
    )
    assert node.unresolved_dependencies == ("alpha", "zeta")


@pytest.mark.parametrize(
    "field,value",
    [
        ("dependencies", "jellyfin"),
        ("dependents", object()),
        ("unresolved_dependencies", "database"),
    ],
)
def test_dependency_node_rejects_non_collection_fields(
    field: str,
    value: object,
) -> None:
    values = {field: value}
    with pytest.raises(ServiceLifecycleError, match="must be a collection"):
        ServiceDependencyNode(service=managed("portal"), **values)  # type: ignore[arg-type]


def test_dependency_node_validates_child_contracts() -> None:
    with pytest.raises(ServiceLifecycleError, match="only ManagedService"):
        ServiceDependencyNode(
            service=managed("portal"),
            dependencies=("api",),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("field", ["dependencies", "dependents"])
def test_dependency_node_rejects_duplicate_child_identity(field: str) -> None:
    child = managed("api")
    with pytest.raises(ServiceLifecycleError, match="duplicate"):
        ServiceDependencyNode(
            service=managed("portal"),
            **{field: (child, child)},
        )


def test_dependency_node_rejects_duplicate_unresolved_identity() -> None:
    with pytest.raises(ServiceLifecycleError, match="duplicate"):
        ServiceDependencyNode(
            service=managed("portal"),
            unresolved_dependencies=("API", "api"),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("dependencies", (managed("portal"),)),
        ("dependents", (managed("portal"),)),
        ("unresolved_dependencies", ("portal",)),
    ],
)
def test_dependency_node_rejects_self_reference(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ServiceLifecycleError, match="cannot reference themselves"):
        ServiceDependencyNode(
            service=managed("portal"),
            **{field: value},
        )


def test_dependency_node_serializes_deterministically() -> None:
    node = ServiceDependencyNode(
        service=managed("portal"),
        dependencies=(managed("api"),),
    )
    payload = node.to_dict()
    assert payload["service"]["identifier"] == "portal"
    assert payload["dependencies"][0]["identifier"] == "api"
    assert payload["dependents"] == []
    assert payload["unresolved_dependencies"] == []
    assert payload["connected"] is True


def test_standalone_dependency_node_is_not_connected() -> None:
    assert ServiceDependencyNode(service=managed("dozzle")).connected is False


def test_graph_normalizes_nodes_and_timestamp() -> None:
    graph = InfrastructureDependencyGraph(
        nodes=[
            ServiceDependencyNode(service=managed("sonarr")),
            ServiceDependencyNode(service=managed("jellyfin")),
        ],  # type: ignore[arg-type]
        evaluated_at="2026-08-04T22:15:00-04:00",
    )
    assert tuple(item.identifier for item in graph.services) == (
        "jellyfin",
        "sonarr",
    )
    assert graph.evaluated_at == "2026-08-05T02:15:00Z"


@pytest.mark.parametrize(
    "value,message",
    [
        ("nodes", "must be a collection"),
        (("jellyfin",), "contain only ServiceDependencyNode"),
    ],
)
def test_graph_validates_node_collection(value: object, message: str) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        InfrastructureDependencyGraph(
            nodes=value,  # type: ignore[arg-type]
            evaluated_at="2026-08-05T02:15:00Z",
        )


def test_graph_rejects_duplicate_service_identity() -> None:
    node = ServiceDependencyNode(service=managed("jellyfin"))
    with pytest.raises(ServiceLifecycleError, match="duplicate service"):
        InfrastructureDependencyGraph(
            nodes=(node, node),
            evaluated_at="2026-08-05T02:15:00Z",
        )


@pytest.mark.parametrize(
    "timestamp,message",
    [
        ("not-a-time", "ISO-8601"),
        ("2026-08-05T02:15:00", "include a timezone"),
        ("", "ISO-8601"),
    ],
)
def test_graph_validates_evaluated_at(timestamp: str, message: str) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        InfrastructureDependencyGraph(nodes=(), evaluated_at=timestamp)


def test_graph_rejects_resolved_dependency_outside_graph() -> None:
    node = ServiceDependencyNode(
        service=managed("portal"),
        dependencies=(managed("api"),),
    )
    with pytest.raises(ServiceLifecycleError, match="not a graph service"):
        InfrastructureDependencyGraph(
            nodes=(node,),
            evaluated_at="2026-08-05T02:15:00Z",
        )


def test_graph_rejects_resolved_dependent_outside_graph() -> None:
    node = ServiceDependencyNode(
        service=managed("api"),
        dependents=(managed("portal"),),
    )
    with pytest.raises(ServiceLifecycleError, match="not a graph service"):
        InfrastructureDependencyGraph(
            nodes=(node,),
            evaluated_at="2026-08-05T02:15:00Z",
        )


def test_graph_rejects_known_service_marked_unresolved() -> None:
    api = ServiceDependencyNode(service=managed("api"))
    portal = ServiceDependencyNode(
        service=managed("portal"),
        unresolved_dependencies=("api",),
    )
    with pytest.raises(ServiceLifecycleError, match="must not reference known"):
        InfrastructureDependencyGraph(
            nodes=(api, portal),
            evaluated_at="2026-08-05T02:15:00Z",
        )


def test_graph_derived_contract_and_serialization() -> None:
    api_service = managed("api")
    portal_service = managed("portal")
    graph = InfrastructureDependencyGraph(
        nodes=(
            ServiceDependencyNode(
                service=api_service,
                dependents=(portal_service,),
            ),
            ServiceDependencyNode(
                service=portal_service,
                dependencies=(api_service,),
            ),
            ServiceDependencyNode(service=managed("dozzle")),
        ),
        evaluated_at="2026-08-05T02:15:00Z",
    )
    assert graph.provider == "docker-compose"
    assert graph.compose_project == "project-atlas"
    assert graph.edge_count == 1
    assert tuple(node.service.identifier for node in graph.roots) == ("api",)
    assert tuple(node.service.identifier for node in graph.standalone) == (
        "dozzle",
    )
    assert graph.unresolved == ()
    assert graph.node(" PORTAL ").service.identifier == "portal"
    assert graph.to_dict()["total_edges"] == 1


def test_graph_node_rejects_unknown_identity() -> None:
    graph = InfrastructureDependencyGraph(
        nodes=(),
        evaluated_at="2026-08-05T02:15:00Z",
    )
    with pytest.raises(ServiceLifecycleError, match="not present"):
        graph.node("missing")


def test_empty_graph_has_explicit_aggregate_identity() -> None:
    graph = InfrastructureDependencyGraph(
        nodes=(),
        evaluated_at="2026-08-05T02:15:00Z",
    )
    assert graph.provider == "unknown"
    assert graph.compose_project is None
    assert graph.services == ()
    assert graph.edge_count == 0


def test_mixed_graph_has_explicit_aggregate_identity() -> None:
    graph = InfrastructureDependencyGraph(
        nodes=(
            ServiceDependencyNode(service=managed("api")),
            ServiceDependencyNode(
                service=managed(
                    "worker",
                    provider="systemd",
                    compose_project="other-project",
                )
            ),
        ),
        evaluated_at="2026-08-05T02:15:00Z",
    )
    assert graph.provider == "mixed"
    assert graph.compose_project == "mixed"


def test_dependency_models_are_publicly_exported() -> None:
    assert CompatibilityGraph is InfrastructureDependencyGraph
    assert CompatibilityNode is ServiceDependencyNode
