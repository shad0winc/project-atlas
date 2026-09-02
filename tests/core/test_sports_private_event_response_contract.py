from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_API = ROOT / "modules" / "sports" / "src" / "private_api.py"
EXPECTED = {"provider","provider_event_id","name","sport","league","start_at","status","requested"}
FORBIDDEN = {"id","provider_league_id","home_team","away_team","home_team_id","away_team_id","duration_minutes","stream_url"}

def _safe_event_keys() -> set[str]:
    tree = ast.parse(PRIVATE_API.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_safe_event":
            returns = [item for item in ast.walk(node) if isinstance(item, ast.Return) and isinstance(item.value, ast.Dict)]
            assert len(returns) == 1
            return {key.value for key in returns[0].value.keys if isinstance(key, ast.Constant)}
    raise AssertionError("_safe_event helper was not found")

def test_private_sports_event_response_is_explicitly_bounded() -> None:
    keys = _safe_event_keys()
    assert keys == EXPECTED
    assert keys.isdisjoint(FORBIDDEN)

def test_private_sports_events_route_uses_safe_event_boundary() -> None:
    source = PRIVATE_API.read_text(encoding="utf-8")
    assert 'events.append(self._safe_event(event))' in source
    assert 'events.append(event)' not in source
