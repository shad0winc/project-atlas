MANIFEST = '{"apps/channels/models.py": "64a3c662b627edeffc80782ea9b7bfed5c99eff7c29887d1491b3afe11f45e21", "apps/m3u/connection_pool.py": "82d2b9697b902021abbb589de5a41fb785f77ab9e3ab1c5f08d0d2fd6e058cc3", "apps/proxy/live_proxy/client_manager.py": "04504f8ff943fa825ac5f7810bcf14d0913b24adca3a07ecfd9903dce8c425e3", "apps/proxy/live_proxy/input/buffer.py": "6c513885a5fa960b31d3014dabadd7efb2ad1baff2cd49067cd844b36bcf4313", "apps/proxy/live_proxy/input/http_streamer.py": "3186ce477cbacbe4d0b8c1f1acc3c87095e995c1e72dd5aaa0182a835c321833", "apps/proxy/live_proxy/input/manager.py": "66757524026f672c1d5e78006bf04a00f7ec0d6a1cbfb5c42f5b535bdf9a2ffd", "apps/proxy/live_proxy/output/fmp4/buffer.py": "149e4a90858344c59388185a59778f3bcd029c64bad126f68fa756a4064869aa", "apps/proxy/live_proxy/output/fmp4/generator.py": "dd3782e9dfedc62a9c0498183b309b8db94126a557885873d1fe055b850a58bc", "apps/proxy/live_proxy/output/fmp4/manager.py": "bfafa5ded996471174cf2a47ee0a5f967faae8d25659dda1f3122ea29f52b8a2", "apps/proxy/live_proxy/output/profile/manager.py": "b09276e8aee35c06d4a75503811c98c3e5d0eb93ef98dd4e10fdfda16e1663cb", "apps/proxy/live_proxy/output/ts/generator.py": "d105af31aac977cc927a1f5326e5a41f7811345c86d7cd5c7d97b60458375b9d", "apps/proxy/live_proxy/redis_keys.py": "a4dc6310efc3962a6c73068f864ef62654372c5c5e781fd1b7f39c8b6cf26858", "apps/proxy/live_proxy/server.py": "104a12f402860671c8f816c0fdac2b38c9afe20d69154fab3a55bb62fcc3e9e2", "apps/proxy/live_proxy/services/channel_service.py": "6d77dcee57445ff95cf98e3ae27e08737fbbbb80e563068171eb90b010e1b9c7", "apps/proxy/live_proxy/url_utils.py": "9eca9ebb20f6b402716f3d98bb4068ddab505bfba0aa7b1d62c6e7de994cb0fc", "apps/proxy/live_proxy/views.py": "0234a6a8adb7a8cbb1396a8a2637fc9cc5bfac0409ba98943f36e474c2496398", "apps/proxy/vod_proxy/multi_worker_connection_manager.py": "0a9f5600f4ec95d714803dd0985f8f1485f876092f7c761bb098e324338f700f", "apps/timeshift/views.py": "c9f2995b2910502503c1a2047f28b2a04d635df9dfacc2b52dff22177c993ec0"}'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(MANIFEST)
root = Path("/app" if len(sys.argv) == 1 else sys.argv[1])
for name, expected in manifest.items():
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise SystemExit("source unavailable: " + name)
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise SystemExit("source drift: " + name)
    compile(content, name, "exec")
print("verified_source_files=", len(manifest))
