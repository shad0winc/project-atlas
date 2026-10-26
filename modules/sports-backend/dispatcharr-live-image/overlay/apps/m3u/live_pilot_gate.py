"""Opt-in live-only Sports pilot boundary; no provider or Redis operations."""
from functools import wraps
import os

MODE_VARIABLE = 'ATLAS_SPORTS_PILOT_MODE'

def pilot_enabled():
    return os.environ.get(MODE_VARIABLE, 'off') != 'off'

def pilot_ready():
    return (os.environ.get(MODE_VARIABLE) == 'live-only'
            and os.environ.get('ATLAS_VERIFIED_LIVE_MODE') == 'strict'
            and os.environ.get('ATLAS_RESERVATION_LEDGER_MIGRATED') == '1')

def unavailable():
    from django.http import JsonResponse
    response = JsonResponse({'error': 'This playback is unavailable during the live Sports pilot.'}, status=503)
    response['Cache-Control'] = 'no-store'
    return response

def blocked_path(path):
    if not isinstance(path, str):
        return True
    prefixes = ('/proxy/vod/', '/proxy/catchup/', '/proxy/hls/',
                '/movie/', '/series/', '/timeshift/', '/api/vod/', '/api/catchup/')
    return (any(path == prefix[:-1] or path.startswith(prefix) for prefix in prefixes)
            or path.rstrip('/') == '/streaming/timeshift.php')

class LiveSportsPilotMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if pilot_enabled() and (not pilot_ready() or blocked_path(request.path_info)):
            return unavailable()
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not pilot_enabled():
            return None
        # Class/module checks also cover aliases that resolve to these views.
        module = getattr(view_func, '__module__', '')
        cls = getattr(view_func, 'cls', None)
        modules = (module, getattr(cls, '__module__', ''))
        if any(value.startswith(('apps.proxy.vod_proxy.', 'apps.timeshift.',
                                 'apps.proxy.hls_proxy.')) for value in modules):
            return unavailable()
        if not pilot_ready():
            return unavailable()
        return None

def wrap_live_view(view, *, network_allowed, get_object, channel_type, server_factory):
    @wraps(view)
    def guarded(request, channel_id, *args, **kwargs):
        if not pilot_enabled():
            return view(request, channel_id, *args, **kwargs)
        if not pilot_ready():
            return unavailable()
        # Preserve the existing network denial and allocation-free HEAD/OPTIONS
        # dispatch. No new lookup or private policy request occurs for these.
        if request.method != 'GET' or not network_allowed(request, 'STREAMS'):
            return view(request, channel_id, *args, **kwargs)
        channel = get_object(channel_id)
        if not isinstance(channel, channel_type):
            return unavailable()
        server = server_factory()
        classifier = getattr(server, '_managed_channel_classifier', None)
        policy = getattr(server, '_verified_live_policy_builder', None)
        if not callable(getattr(classifier, 'classify', None)) or not callable(policy):
            return unavailable()
        # The original handler classifies this exact channel and invokes
        # owner_route(), which rejects managed=False when the pilot is enabled.
        return view(request, channel_id, *args, **kwargs)
    return guarded
