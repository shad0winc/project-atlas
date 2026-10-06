from unittest.mock import patch
from apps.api.tests.test_admin_live_session_policy import _fixture


def test_health_permission_blocks_observation_before_read(tmp_path):
    client, *_ = _fixture(tmp_path, role="member")
    with patch("atlas_api.routes.v1.admin_automation_health.read_automation_health") as reader:
        assert client.get("/api/v1/admin/automation-health").status_code == 403
        reader.assert_not_called()


def test_admin_can_read_but_cannot_mutate_health(tmp_path):
    client, *_ = _fixture(tmp_path)
    with patch("atlas_api.routes.v1.admin_automation_health.read_automation_health", return_value={"observed_at": "test"}) as reader:
        response = client.get("/api/v1/admin/automation-health")
        assert response.status_code == 200
        assert "test" in response.text
        reader.assert_called_once_with()
        for method in (client.post, client.put, client.patch, client.delete):
            assert method("/api/v1/admin/automation-health").status_code == 405
