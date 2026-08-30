# Regression contracts for Sports team/league event discovery.

from __future__ import annotations

import ast
from pathlib import Path


def _function_arguments(
    source: str,
    *,
    class_name: str | None,
    function_name: str,
) -> set[str]:
    tree = ast.parse(source)

    if class_name is None:
        bodies = [tree.body]
    else:
        bodies = [
            node.body
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == class_name
        ]

    for body in bodies:
        for node in body:
            if (
                isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                )
                and node.name == function_name
            ):
                arguments = (
                    node.args.posonlyargs
                    + node.args.args
                    + node.args.kwonlyargs
                )
                return {
                    argument.arg
                    for argument in arguments
                }

    raise AssertionError(f"{function_name} was not found")


def test_writer_event_adapter_projects_team_and_league_ids() -> None:
    source = Path(
        "apps/api/atlas_api/services/sports.py"
    ).read_text(encoding="utf-8")

    arguments = _function_arguments(
        source,
        class_name="SportsWriterBackedAPIService",
        function_name="list_events_for_user",
    )

    assert {"team_ids", "league_ids"} <= arguments
    assert 'query_items.append(("team_id", normalized))' in source
    assert 'query_items.append(("league_id", normalized))' in source


def test_private_writer_routes_discovery_through_fetch_games() -> None:
    source = Path(
        "modules/sports/src/private_api.py"
    ).read_text(encoding="utf-8")

    assert 'params.get("team_id", [])' in source
    assert 'params.get("league_id", [])' in source
    assert "team_ids=team_ids or None" in source
    assert "league_ids=league_ids or None" in source


def test_public_events_route_exposes_team_and_league_filters() -> None:
    source = Path(
        "apps/api/atlas_api/routes/v1/sports.py"
    ).read_text(encoding="utf-8")

    arguments = _function_arguments(
        source,
        class_name=None,
        function_name="list_sports_events",
    )

    assert {"team_id", "league_id"} <= arguments
    assert "team_ids=(" in source
    assert "league_ids=(" in source
