"""Verify a server-pinned single-feed sharing canary against native metadata."""
from dataclasses import replace
try:
    from atlas.sports_shared_admission_config import load_shared_admission, CONTROLLER_CONFIG_PATH
except ModuleNotFoundError as error:
    if error.name != "atlas": raise
    from sports_shared_admission_config import load_shared_admission, CONTROLLER_CONFIG_PATH
from dispatcharr_admin import verify_configured_playback_option
from dispatcharr_channel_bindings import default_dispatcharr_channel_binding_registry
from live_tv_bindings import default_live_tv_binding_registry
from live_sources import default_live_source_registry, LivePlaybackOption, LiveSourceCatalogError

def verify_shared_live_route(target_id, lifecycle_sources):
    route = load_shared_admission(CONTROLLER_CONFIG_PATH).for_target(target_id)
    if route is None: raise LiveSourceCatalogError('Shared route is not enabled')
    sources = [row for row in default_live_source_registry().list_sources() if row.atlas_channel_id == target_id]
    if len(sources) != 1: raise LiveSourceCatalogError('Shared source is unavailable')
    source = sources[0]
    if source.playback_options or source.resource_source_ids != (route.resource_source_id,):
        raise LiveSourceCatalogError('Canary requires an exact single feed')
    binding = default_dispatcharr_channel_binding_registry().resolve(target_id)
    if (binding is None or binding.dispatcharr_channel_id != route.dispatcharr_channel_id
            or binding.dispatcharr_channel_uuid != route.dispatcharr_channel_uuid
            or default_live_tv_binding_registry().resolve(target_id) != route.jellyfin_item_id):
        raise LiveSourceCatalogError('Shared publication binding changed')
    resources = [row for row in lifecycle_sources if row.source_id == route.resource_source_id]
    if (len(resources) != 1 or resources[0].backend_reference != f'dispatcharr:m3u:{route.dispatcharr_account_id}'
            or resources[0].max_connections != route.capacity):
        raise LiveSourceCatalogError('Shared resource identity changed')
    # Reuse the existing native verifier and its bounded authentication/backoff.
    # This temporary option exists only in memory, never in the catalog/UI.
    option = LivePlaybackOption('primary', route.resource_source_id, source.stream_url,
        route.dispatcharr_channel_id, route.dispatcharr_channel_uuid, route.dispatcharr_stream_id)
    verify_configured_playback_option(replace(source, playback_options=(option,)), 'primary', lifecycle_sources)
    return {'target_id': target_id, 'fingerprint': route.fingerprint}
