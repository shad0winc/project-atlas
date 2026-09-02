from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UPDATE = ROOT / "scripts" / "commands" / "update.sh"
DEPLOYMENT = ROOT / "scripts" / "commands" / "deployment.sh"
CADDYFILE = ROOT / "infra" / "caddy" / "Caddyfile"


def test_forward_ingress_update_restarts_caddy_before_readiness():
    content = UPDATE.read_text(encoding="utf-8")
    apply = content.split("atlas_update_ingress_apply() {", 1)[1].split(
        "atlas_update_apply_scope() {",
        1,
    )[0]

    assert apply.index("up -d") < apply.index("docker restart atlas-caddy")


def test_rollback_activates_restored_caddy_before_readiness():
    content = DEPLOYMENT.read_text(encoding="utf-8")
    readiness = content.index("Post-restore ingress readiness:")
    before_readiness = content[:readiness]

    assert (
        before_readiness.rindex("atlas_deployment_restore_surface")
        < before_readiness.rindex("docker restart atlas-caddy")
    )


def test_caddy_admin_api_remains_disabled():
    assert "admin off" in CADDYFILE.read_text(encoding="utf-8")
