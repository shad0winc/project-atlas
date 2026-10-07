"""Hash-guarded HEAD compatibility for the immutable Dispatcharr base."""
import ast
import hashlib
from pathlib import Path

UPSTREAM_SHA256 = "0234a6a8adb7a8cbb1396a8a2637fc9cc5bfac0409ba98943f36e474c2496398"
PATCHED_SHA256 = '2770bf6146c231393af78045d8de44d5be452d5e785c652cda8c43e56bb52ff2'
METHOD_ANCHOR = '@api_view(["GET"])\n@permission_classes([AllowAny])\ndef stream_ts'
BODY_ANCHOR = '    """Stream TS data to client with immediate response and keep-alive packets during initialization"""'
HEAD_BRANCH = '    if request.method == "HEAD":\n        # Resolve identity only: HEAD must never select an upstream or a client.\n        get_stream_object(channel_id)\n        # Keep Content-Length unspecified for this live resource. The empty\n        # streaming iterator performs no acquisition or publication.\n        response = StreamingHttpResponse((), content_type="video/mp2t")\n        response["Cache-Control"] = "no-store"\n        return response\n\n'

def patched_source(raw, *, expected_sha256=UPSTREAM_SHA256):
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Dispatcharr upstream source checksum changed")
    text = raw.decode("utf-8")
    if text.count(METHOD_ANCHOR) != 1 or text.count(BODY_ANCHOR) != 1:
        raise ValueError("Dispatcharr HEAD patch anchors changed")
    candidate = text.replace(METHOD_ANCHOR, METHOD_ANCHOR.replace('["GET"]', '["GET", "HEAD"]')).replace(BODY_ANCHOR, HEAD_BRANCH + BODY_ANCHOR)
    ast.parse(candidate)
    return candidate.encode("utf-8")

def main():
    path = Path("/app/apps/proxy/live_proxy/views.py")
    if not path.is_file() or path.is_symlink():
        raise ValueError("Dispatcharr source is missing or a symlink")
    raw = path.read_bytes()
    candidate = patched_source(raw)
    if hashlib.sha256(candidate).hexdigest() != PATCHED_SHA256:
        raise ValueError("Dispatcharr patched source checksum changed")
    backup = Path("/tmp/atlas-dispatcharr-views.before.py")
    if backup.exists() or backup.is_symlink():
        raise ValueError("Build backup already exists")
    backup.write_bytes(raw)
    path.write_bytes(candidate)

if __name__ == "__main__":
    main()
