from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_HELPER = ROOT / "scripts/lib/identity-writer-runtime.sh"
UPDATE_SCRIPT = ROOT / "scripts/commands/update.sh"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_identity_writer_runtime_helper_exists() -> None:
    assert RUNTIME_HELPER.is_file()


def test_runtime_helper_defines_narrow_storage_contract() -> None:
    source = _read(RUNTIME_HELPER)

    assert "20000" in source
    assert "20001" in source
    assert "/mnt/storage/configs/atlas/users" in source
    assert "/mnt/storage/configs/atlas/identity" in source
    assert "ATLAS_IDENTITY_DIR" in source
    assert "%s/invitations" in source

    # Runtime mutation authority is group-scoped while root retains
    # host-side ownership. setgid preserves the intended group on
    # newly created children.
    assert "2770" in source


def test_runtime_helper_does_not_use_recursive_permission_mutation() -> None:
    source = _read(RUNTIME_HELPER)

    forbidden = (
        "chmod -R",
        "chmod --recursive",
        "chown -R",
        "chown --recursive",
    )

    for token in forbidden:
        assert token not in source


def test_runtime_helper_has_provision_and_verify_boundaries() -> None:
    source = _read(RUNTIME_HELPER)

    assert "atlas_identity_writer_runtime_provision()" in source
    assert "atlas_identity_writer_runtime_verify()" in source


def test_ingress_apply_provisions_identity_writer_runtime() -> None:
    source = _read(UPDATE_SCRIPT)

    apply_start = source.index("atlas_update_ingress_apply()")
    next_function = source.find("\n}\n", apply_start)

    assert next_function != -1

    body = source[apply_start:next_function]

    assert "atlas_identity_writer_runtime_provision" in body


def test_core_apply_does_not_provision_identity_writer_runtime() -> None:
    source = _read(UPDATE_SCRIPT)

    core_start = source.index("atlas_update_core_apply()")
    core_end = source.find("\n}\n", core_start)

    assert core_end != -1

    body = source[core_start:core_end]

    assert "atlas_identity_writer_runtime_provision" not in body


def test_update_script_loads_identity_writer_runtime_helper() -> None:
    source = _read(UPDATE_SCRIPT)

    assert "identity-writer-runtime.sh" in source
