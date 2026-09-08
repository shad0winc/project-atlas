import os
from pathlib import Path

import pytest

from atlas.sports_resource_pool import (
    SportsResourceLeaseNotFound,
    SportsResourcePool,
    SportsResourcePoolExhausted,
)


class Clock:
    def __init__(
        self,
        value: float = 1000.0,
    ) -> None:
        self.value = value

    def __call__(
        self,
    ) -> float:
        return self.value

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.value += seconds


class LeaseIds:
    def __init__(
        self,
    ) -> None:
        self.value = 0

    def __call__(
        self,
    ) -> str:
        self.value += 1
        return f"lease-{self.value}"


def pool(
    path: Path,
    *,
    clock: Clock,
    ids: LeaseIds,
) -> SportsResourcePool:
    return SportsResourcePool(
        path,
        ttl_seconds=90,
        clock=clock,
        lease_id_factory=ids,
    )


def test_uses_highest_ranked_candidate_with_capacity(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
            "evestv-account-1",
        ),
        capacities={
            "xc-account-2": 3,
            "evestv-account-1": 1,
        },
    )

    assert lease.source_id == "xc-account-2"

    snapshot = store.snapshot(
        capacities={
            "xc-account-2": 3,
            "evestv-account-1": 1,
        }
    )

    assert snapshot.total_capacity == 4
    assert snapshot.active == 1
    assert snapshot.available == 3


def test_falls_through_to_next_candidate_when_primary_is_full(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 3,
        "evestv-account-1": 1,
    }
    candidates = (
        "xc-account-2",
        "evestv-account-1",
    )

    for index in range(3):
        lease = store.acquire(
            user_id=f"usr-{index}",
            target_id=f"game-{index}",
            candidate_source_ids=candidates,
            capacities=capacities,
        )
        assert lease.source_id == "xc-account-2"

    fourth = store.acquire(
        user_id="usr-four",
        target_id="game-four",
        candidate_source_ids=candidates,
        capacities=capacities,
    )

    assert fourth.source_id == "evestv-account-1"

    snapshot = store.snapshot(
        capacities=capacities
    )

    assert snapshot.total_capacity == 4
    assert snapshot.active == 4
    assert snapshot.available == 0


def test_pool_fails_closed_when_all_candidates_are_full(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 1,
        "evestv-account-1": 1,
    }
    candidates = (
        "xc-account-2",
        "evestv-account-1",
    )

    store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=candidates,
        capacities=capacities,
    )
    store.acquire(
        user_id="usr-two",
        target_id="game-two",
        candidate_source_ids=candidates,
        capacities=capacities,
    )

    with pytest.raises(
        SportsResourcePoolExhausted,
        match="capacity is exhausted",
    ):
        store.acquire(
            user_id="usr-three",
            target_id="game-three",
            candidate_source_ids=candidates,
            capacities=capacities,
        )


def test_standby_candidates_do_not_consume_leases(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 3,
        "evestv-account-1": 1,
        "future-xc4": 3,
    }

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
            "future-xc4",
            "evestv-account-1",
        ),
        capacities=capacities,
    )

    assert lease.source_id == "xc-account-2"

    snapshot = store.snapshot(
        capacities=capacities
    )

    assert snapshot.active == 1
    assert len(snapshot.leases) == 1

    by_source = {
        item.source_id: item
        for item in snapshot.sources
    }

    assert by_source["xc-account-2"].active == 1
    assert by_source["future-xc4"].active == 0
    assert by_source["evestv-account-1"].active == 0


def test_release_returns_capacity_to_pool(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 1,
    }

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
    )

    assert store.release(
        lease_id=lease.lease_id,
        user_id="usr-one",
    )

    replacement = store.acquire(
        user_id="usr-two",
        target_id="game-two",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
    )

    assert replacement.source_id == "xc-account-2"


def test_lease_ownership_prevents_cross_user_release(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities={
            "xc-account-2": 1,
        },
    )

    assert (
        store.release(
            lease_id=lease.lease_id,
            user_id="usr-two",
        )
        is False
    )

    assert (
        store.snapshot(
            capacities={
                "xc-account-2": 1,
            }
        ).active
        == 1
    )


def test_heartbeat_refreshes_owned_lease(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities={
            "xc-account-2": 1,
        },
    )

    clock.advance(60)

    refreshed = store.heartbeat(
        lease_id=lease.lease_id,
        user_id="usr-one",
    )

    assert refreshed.last_seen_at == 1060.0

    clock.advance(60)

    snapshot = store.snapshot(
        capacities={
            "xc-account-2": 1,
        }
    )

    assert snapshot.active == 1


def test_expired_lease_is_pruned_and_capacity_recovers(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 1,
    }

    store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
    )

    clock.advance(90)

    replacement = store.acquire(
        user_id="usr-two",
        target_id="game-two",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
    )

    assert replacement.user_id == "usr-two"

    snapshot = store.snapshot(
        capacities=capacities
    )

    assert snapshot.active == 1


def test_two_store_instances_share_the_same_authoritative_state(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    path = tmp_path / "resource-pool.json"

    first = pool(
        path,
        clock=clock,
        ids=ids,
    )
    second = pool(
        path,
        clock=clock,
        ids=ids,
    )

    first.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities={
            "xc-account-2": 1,
        },
    )

    with pytest.raises(
        SportsResourcePoolExhausted
    ):
        second.acquire(
            user_id="usr-two",
            target_id="game-two",
            candidate_source_ids=(
                "xc-account-2",
            ),
            capacities={
                "xc-account-2": 1,
            },
        )


def test_zero_capacity_source_is_never_selected(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "disabled-source",
            "xc-account-2",
        ),
        capacities={
            "disabled-source": 0,
            "xc-account-2": 1,
        },
    )

    assert lease.source_id == "xc-account-2"


def test_wrong_user_cannot_heartbeat_lease(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()
    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    lease = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities={
            "xc-account-2": 1,
        },
    )

    with pytest.raises(
        SportsResourceLeaseNotFound
    ):
        store.heartbeat(
            lease_id=lease.lease_id,
            user_id="usr-two",
        )


def test_user_limit_is_enforced_across_sources(
    tmp_path: Path,
) -> None:
    from atlas.sports_resource_pool import (
        SportsResourceUserLimitExceeded,
    )

    clock = Clock()
    ids = LeaseIds()

    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 3,
        "evestv-account-1": 1,
    }

    candidates = (
        "xc-account-2",
        "evestv-account-1",
    )

    first = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=candidates,
        capacities=capacities,
        user_limit=2,
    )

    second = store.acquire(
        user_id="usr-one",
        target_id="game-two",
        candidate_source_ids=candidates,
        capacities=capacities,
        user_limit=2,
    )

    assert first.user_id == "usr-one"
    assert second.user_id == "usr-one"

    with pytest.raises(
        SportsResourceUserLimitExceeded,
        match="session limit reached",
    ):
        store.acquire(
            user_id="usr-one",
            target_id="game-three",
            candidate_source_ids=candidates,
            capacities=capacities,
            user_limit=2,
        )

    # Another user can still consume remaining account capacity.
    third = store.acquire(
        user_id="usr-two",
        target_id="game-three",
        candidate_source_ids=candidates,
        capacities=capacities,
        user_limit=2,
    )

    assert third.user_id == "usr-two"

    snapshot = store.snapshot(
        capacities=capacities
    )

    assert snapshot.active == 3


def test_user_limit_and_source_capacity_are_one_shared_admission(
    tmp_path: Path,
) -> None:
    from atlas.sports_resource_pool import (
        SportsResourceUserLimitExceeded,
    )

    clock = Clock()
    ids = LeaseIds()
    path = tmp_path / "resource-pool.json"

    first = pool(
        path,
        clock=clock,
        ids=ids,
    )

    second = pool(
        path,
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 3,
    }

    first.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
        user_limit=1,
    )

    # Independent store/process view must observe the same user's lease
    # before admitting another one.
    with pytest.raises(
        SportsResourceUserLimitExceeded,
        match="session limit reached",
    ):
        second.acquire(
            user_id="usr-one",
            target_id="game-two",
            candidate_source_ids=(
                "xc-account-2",
            ),
            capacities=capacities,
            user_limit=1,
        )

    snapshot = second.snapshot(
        capacities=capacities
    )

    assert snapshot.active == 1
    assert len(snapshot.leases) == 1
    assert snapshot.leases[0].user_id == "usr-one"


def test_release_restores_user_admission_slot(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()

    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 2,
    }

    first = store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
        user_limit=1,
    )

    assert store.release(
        lease_id=first.lease_id,
        user_id="usr-one",
    )

    replacement = store.acquire(
        user_id="usr-one",
        target_id="game-two",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
        user_limit=1,
    )

    assert replacement.user_id == "usr-one"


def test_expired_lease_restores_user_admission_slot(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = LeaseIds()

    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    capacities = {
        "xc-account-2": 2,
    }

    store.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
        user_limit=1,
    )

    clock.advance(90)

    replacement = store.acquire(
        user_id="usr-one",
        target_id="game-two",
        candidate_source_ids=(
            "xc-account-2",
        ),
        capacities=capacities,
        user_limit=1,
    )

    assert replacement.target_id == "game-two"


@pytest.mark.parametrize(
    "value",
    (
        0,
        -1,
        True,
        1.5,
        "2",
    ),
)
def test_user_limit_must_be_positive_integer(
    tmp_path: Path,
    value,
) -> None:
    clock = Clock()
    ids = LeaseIds()

    store = pool(
        tmp_path / "resource-pool.json",
        clock=clock,
        ids=ids,
    )

    with pytest.raises(
        ValueError,
        match="user limit must be a positive integer",
    ):
        store.acquire(
            user_id="usr-one",
            target_id="game-one",
            candidate_source_ids=(
                "xc-account-2",
            ),
            capacities={
                "xc-account-2": 1,
            },
            user_limit=value,
        )


def test_resource_pool_files_are_shared_private_despite_restrictive_umask(
    tmp_path: Path,
) -> None:
    import os

    path = tmp_path / "resource-pool.json"
    store = pool(
        path,
        clock=Clock(),
        ids=LeaseIds(),
    )

    previous_umask = os.umask(0o077)

    try:
        snapshot = store.snapshot(
            capacities={},
        )
    finally:
        os.umask(previous_umask)

    assert snapshot.active == 0
    assert path.is_file()
    assert store.lock_path.is_file()
    assert path.stat().st_mode & 0o777 == 0o660
    assert store.lock_path.stat().st_mode & 0o777 == 0o660


def test_resource_pool_repairs_owner_accessible_private_lock_mode(
    tmp_path: Path,
) -> None:
    path = tmp_path / "resource-pool.json"
    lock = path.with_name(
        path.name + ".lock"
    )

    lock.touch()
    lock.chmod(0o600)

    store = pool(
        path,
        clock=Clock(),
        ids=LeaseIds(),
    )

    store.snapshot(
        capacities={},
    )

    assert lock.stat().st_mode & 0o777 == 0o660
    assert path.stat().st_mode & 0o777 == 0o660


def test_resource_pool_uses_nonowned_shared_lock_without_chmod(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "sports-resource-pool.json"

    store = SportsResourcePool(
        path,
        clock=Clock(),
    )

    store.lock_path.touch()
    store.lock_path.chmod(0o660)

    lock_owner = store.lock_path.stat().st_uid

    # Simulate production: the process can open the shared lock through
    # its group permissions, but the inode belongs to another uid.
    monkeypatch.setattr(
        os,
        "geteuid",
        lambda: lock_owner + 1,
    )

    def reject_fchmod(*_args):
        raise AssertionError(
            "non-owner shared lock must not be chmodded"
        )

    monkeypatch.setattr(
        os,
        "fchmod",
        reject_fchmod,
    )

    with store._locked():
        pass

    assert store.lock_path.stat().st_mode & 0o777 == 0o660
