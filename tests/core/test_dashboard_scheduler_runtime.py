import pytest
from atlas.dashboard_runtime import DashboardRuntimeError, scheduler_tasks_from_payload

def payload(tasks):
    return {
        "schema_version": 1,
        "generated_at": "2026-08-29T12:00:00Z",
        "tasks": tasks,
    }
def test_empty_is_valid():
    assert scheduler_tasks_from_payload(payload([])) == ()
def test_sorted():
    tasks = scheduler_tasks_from_payload(
        payload([{"name": "z"}, {"name": "a"}])
    )
    assert [task["name"] for task in tasks] == ["a", "z"]
def test_missing_name_rejected():
    with pytest.raises(DashboardRuntimeError): scheduler_tasks_from_payload(payload([{}]))
