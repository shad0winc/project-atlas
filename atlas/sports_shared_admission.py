"""Validate server-owned sharing admission before allocating a resource."""
from atlas.sports_resource_pool import SportsResourcePool, SportsResourcePoolStateError
from atlas.sports_shared_admission_config import (
    load_shared_admission, SharedAdmissionConfig, SharedAdmissionRoute,
    SharedAdmissionConfigError,
)

def verify_api_shared_admission(pool, sports, *, target_id, user_id, jellyfin_item_id, candidates, capacities, configured_options):
    loader = getattr(pool, 'shared_admission_loader', None)
    try:
        config = loader() if loader is not None else getattr(pool, 'shared_admission_config', None)
    except SharedAdmissionConfigError as error:
        raise SportsResourcePoolStateError('Shared admission configuration is unavailable.') from error
    if loader is not None and config.routes:
        pool = SportsResourcePool(pool.path, ttl_seconds=pool.ttl_seconds,
            clock=pool._clock, lease_id_factory=pool._lease_id_factory,
            sharing_bindings=config.bindings())
    if config is None:
        if getattr(pool, 'sharing_bindings', {}):
            raise SportsResourcePoolStateError('Shared route verification is unavailable.')
        return pool, candidates
    route = config.for_target(target_id)
    if route is None: return pool, candidates
    if (user_id not in route.viewer_user_ids or configured_options
            or jellyfin_item_id != route.jellyfin_item_id
            or route.resource_source_id not in candidates
            or capacities.get(route.resource_source_id) != route.capacity
            or pool.sharing_bindings.get((target_id, route.resource_source_id)) != route.fingerprint):
        raise SportsResourcePoolStateError('Shared route is not eligible for this canary.')
    sports.verify_shared_live_route(target_id=target_id, fingerprint=route.fingerprint)
    return pool, (route.resource_source_id,)
