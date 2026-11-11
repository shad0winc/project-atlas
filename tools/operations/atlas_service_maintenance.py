"""Host authority for fresh Services scans and the reviewed Bazarr workflow."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import stat
import struct
import subprocess
import tempfile
import threading
import time
from uuid import uuid4

SNAPSHOT = Path("/mnt/storage/configs/atlas/runtime/services/latest.json")
ROOT = Path("/var/lib/atlas-service-maintenance")
SOCKET = Path("/run/atlas-maintenance-control/services.sock")
BAZARR = Path("/var/lib/atlas-service-updates/bazarr/bazarr-ls371-1c267431e51a")
RUNNER = Path("/usr/local/libexec/atlas-bazarr-update-ls371/atlas_bazarr_update.py")
AUTHORIZATION_PATH = Path("/etc/atlas/service-maintenance/bazarr-review.sha256")
MARKER = Path("/mnt/storage/configs/atlas/maintenance/enabled")
DEPLOYMENT_LOCK = Path("/mnt/storage/configs/atlas/deployment-scheduler.lock")
BAZARR_PUBLICATION = "baseline-bazarr-preview-126003355a07"
LIMIT = 16 * 1024 * 1024
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
LOCK = threading.RLock()


def require(value, code):
    if not value:
        raise RuntimeError(code)


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path):
    require(path.resolve(strict=True) == path and path.stat().st_size <= LIMIT, "input_path_or_budget")
    return json.loads(path.read_bytes())


def atomic_json(path, value, gid=None):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    require(len(raw) <= LIMIT, "output_budget")
    fd, temporary = tempfile.mkstemp(prefix=".services-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            if gid is not None:
                os.fchown(stream.fileno(), 0, gid)
                os.fchmod(stream.fileno(), 0o640)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, timeout=25, check=False)
    require(result.returncode == 0 and len(result.stdout) <= LIMIT, "docker_observation_failed")
    return result.stdout


def container(name):
    require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name),
            "invalid_container_name")
    return json.loads(docker("inspect", "--type", "container", name))[0]


def image_reference(reference, digest=None):
    require(isinstance(reference, str) and not any(character.isspace() for character in reference),
            "invalid_image_reference")
    source = reference.split("@", 1)[0]
    slash, colon = source.rfind("/"), source.rfind(":")
    repository, tag = (source[:colon], source[colon + 1:]) if colon > slash else (source, None)
    if source.startswith("sha256:"):
        repository, tag = source, None
    canonical = repository + (":" + tag if tag else "") + ("@" + digest if digest else "")
    return {"repository": repository, "tag": tag, "digest": digest, "raw_reference": canonical,
            "canonical_reference": canonical, "is_mutable": tag == "latest"}


def version_key(label):
    if not isinstance(label, str):
        return None
    matched = re.fullmatch(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)(?:-ls([0-9]+))?", label)
    return tuple(int(value or 0) for value in matched.groups()) if matched else None


def registry(reference, platform):
    manifest = json.loads(docker("buildx", "imagetools", "inspect", reference,
                                 "--format", "{{json .Manifest}}"))
    digest = manifest.get("digest")
    if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
        description = docker("buildx", "imagetools", "inspect", reference).decode()
        matches = re.findall(r"(?m)^Digest:\s+(sha256:[a-f0-9]{64})\s*$", description)
        require(len(matches) == 1, "registry_digest_unverified")
        digest = matches[0]
    children = [row.get("digest") for row in manifest.get("manifests", [])
                if (row.get("platform", {}).get("os") or "") + "/" +
                row.get("platform", {}).get("architecture", "") == platform]
    return digest, children


def remote_version(reference, platform):
    template = "{{json (index .Image " + json.dumps(platform) + ")}}"
    config = json.loads(docker("buildx", "imagetools", "inspect", reference, "--format", template))
    require(isinstance(config, dict), "registry_platform_unavailable")
    labels = (config.get("config") or {}).get("Labels") or (config.get("config") or {}).get("labels") or {}
    return labels.get("org.opencontainers.image.version")


def scan_entry(entry):
    result = deepcopy(entry)
    service = result["service"]
    identifier, name = service["identifier"], service["name"]
    timestamp = now()
    try:
        row = container(service.get("container_name") or identifier)
    except RuntimeError as error:
        if str(error) != "docker_observation_failed":
            raise
        reference = image_reference(result["runtime"]["image"]["reference"])
        result["runtime"] = {
            "state": "missing", "health": "unknown", "image": {
                "reference": reference["raw_reference"], "repository": reference["repository"],
                "tag": reference["tag"], "digest": None, "image_id": None, "created_at": None,
            }, "restart_count": 0, "started_at": None, "finished_at": None,
            "exit_code": None, "status_message": "The container could not be inspected.",
        }
        result["health"] = {
            "status": "unavailable", "score": 0, "warnings": [],
            "errors": ["The container could not be inspected."], "details": {},
            "evaluated_at": timestamp,
        }
        result["update"] = {
            "service_identifier": identifier, "service_name": name,
            "current_image": reference, "available_image": None, "status": "unknown",
            "reason": "No current container observation is available.",
            "details": {"source": "atlas-host", "registry_comparison": False},
            "evaluated_at": timestamp,
        }
        return result
    local = json.loads(docker("image", "inspect", row["Image"]))[0]
    configured = (row["Config"].get("Labels") or {}).get("io.project-atlas.configured-image") or row["Config"]["Image"]
    reference = image_reference(configured)
    local_digest = (local.get("Descriptor") or {}).get("digest")
    if not isinstance(local_digest, str) or not DIGEST.fullmatch(local_digest):
        candidates = [value.rsplit("@", 1)[1] for value in local.get("RepoDigests") or []
                      if value.startswith(reference["repository"] + "@")]
        local_digest = candidates[0] if candidates else None
    health = (row["State"].get("Health") or {}).get("Status", "unknown")
    running = row["State"]["Running"]
    image = {"reference": configured, "repository": reference["repository"], "tag": reference["tag"],
             "digest": local_digest, "image_id": row["Image"], "created_at": local.get("Created")}
    result["runtime"] = {
        "state": row["State"]["Status"], "health": health, "image": image,
        "restart_count": row["RestartCount"], "started_at": row["State"].get("StartedAt"),
        "finished_at": row["State"].get("FinishedAt"), "exit_code": row["State"].get("ExitCode"),
        "status_message": None,
    }
    service["compose_project"] = (row["Config"].get("Labels") or {}).get("com.docker.compose.project")
    state = "healthy" if running and health == "healthy" else "degraded" if running else "unavailable"
    if health == "unhealthy":
        state = "unhealthy"
    result["health"] = {
        "status": state, "score": 100 if state == "healthy" else 90 if state == "degraded" else 0,
        "warnings": ["Container has no Docker health check."] if running and health == "unknown" else [],
        "errors": [] if running else ["Container is not running."],
        "details": {"service_identifier": identifier, "docker_health": health},
        "evaluated_at": timestamp,
    }
    current_label = (local["Config"].get("Labels") or {}).get("org.opencontainers.image.version")
    details = {
        "source": "atlas-host", "configured_reference": configured, "local_image_id": row["Image"],
        "local_descriptor_digest": local_digest, "local_image_created_at": local.get("Created"),
        "current_version_label": current_label, "registry_comparison": False,
    }
    update = {"service_identifier": identifier, "service_name": name,
              "current_image": image_reference(configured, local_digest), "available_image": None,
              "status": "unknown", "reason": "Registry comparison is unavailable.",
              "details": details, "evaluated_at": timestamp}
    public_repository = "/" in reference["repository"] or reference["repository"] in ("redis", "nginx", "node")
    if reference["tag"] and public_repository:
        try:
            platform = local["Os"] + "/" + local["Architecture"]
            digest, children = registry(reference["repository"] + ":" + reference["tag"], platform)
            details.update(remote_manifest_digest=digest,
                           registry_comparison=local_digest is not None)
            if local_digest == digest or local_digest in children:
                update.update(status="current", reason="The running image matches the registry for this platform.")
                details["available_version_label"] = current_label
            elif local_digest:
                target = reference["repository"] + "@" + digest
                label = remote_version(target, platform)
                details["available_version_label"] = label
                current_key, target_key = version_key(current_label), version_key(label)
                if current_key is not None and target_key is not None and target_key <= current_key:
                    update["reason"] = "The registry image differs, but its version is not newer than the running build."
                    details["version_order"] = "older-or-equal"
                else:
                    update.update(status="update-available",
                                  reason="A different registry image is available for review.",
                                  available_image=image_reference(configured, digest))
                    details["version_order"] = "newer" if current_key is not None and target_key is not None else "unverified"
        except (RuntimeError, ValueError, subprocess.SubprocessError):
            update["reason"] = "The registry could not be checked. Retry the scan."
            update["status"] = "unknown"
            update["available_image"] = None
            details["registry_comparison"] = False
    result["update"] = update
    after = container(service.get("container_name") or identifier)
    require((row["Id"], row["Image"], row["State"]["StartedAt"], row["RestartCount"])
            == (after["Id"], after["Image"], after["State"]["StartedAt"], after["RestartCount"]),
            "runtime_changed_during_scan")
    return result


def maintenance_history(previous):
    records = deepcopy((previous.get("history") or {}).get("records") or [])
    for filename, action, summary in (
        ("completed.json", "other", "Updated Bazarr to v1.6.2-ls371."),
        ("rolled-back.json", "rollback", "Restored the retained Bazarr container and configuration."),
    ):
        path = BAZARR / filename
        if not path.is_file():
            continue
        receipt = read_json(path)
        key = str(BAZARR.name) + ":" + action
        records = [row for row in records if (row.get("details") or {}).get("operation_id") != key]
        completed = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        started_path = BAZARR / ("rollback-requested.json" if action == "rollback" else "inputs.json")
        started = datetime.fromtimestamp(started_path.stat().st_mtime, timezone.utc).isoformat()
        records.append({
            "service_identifier": "bazarr", "service_name": "Bazarr", "provider": "atlas-host",
            "action": action, "result": "success", "started_at": started, "completed_at": completed,
            "summary": summary, "details": {"operation_id": key, "image": receipt.get("image")},
        })
    records.sort(key=lambda row: row.get("completed_at") or row["started_at"], reverse=True)
    return {"provider": "atlas-host", "generated_at": now(), "records": records[:100]}


def publish_scan(progress):
    lock = os.open(DEPLOYMENT_LOCK, os.O_RDONLY | os.O_NOFOLLOW)
    candidate = None
    try:
        deadline = time.monotonic() + 90
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                require(time.monotonic() < deadline, "deployment_busy")
                time.sleep(1)
        docker("version", "--format", "{{.Server.APIVersion}}")
        original = read_json(SNAPSHOT)
        original_sha = sha256(SNAPSHOT.read_bytes()).hexdigest()
        require(original.get("schema_version") == 1 and isinstance(original.get("services"), list),
                "snapshot_schema_changed")
        require(0 < len(original["services"]) <= 100, "service_inventory_budget")
        result = deepcopy(original)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(scan_entry, entry) for entry in original["services"]]
            entries = []
            for index, future in enumerate(futures):
                entries.append(future.result())
                progress(f"Checked {index + 1} of {len(futures)} services")
        result.update(services=entries, generated_at=now(), history=maintenance_history(original))
        require(SNAPSHOT.parent.resolve(strict=True) == SNAPSHOT.parent, "snapshot_directory_changed")
        candidate = SNAPSHOT.parent / (".scan-" + uuid4().hex + ".json")
        atomic_json(candidate, result, gid=20000)
        validation = (
            "from pathlib import Path; import sys;"
            "from atlas.service_lifecycle.providers.runtime_snapshot import RuntimeSnapshotProvider;"
            "p=RuntimeSnapshotProvider(Path(sys.argv[1]));"
            "rows=p.list_services();"
            "[(p.inspect_runtime(s.identifier),p.inspect_health(s.identifier),p.inspect_update(s.identifier)) for s in rows];"
            "p.inspect_history();print(len(rows))"
        )
        count = int(docker("exec", "atlas-api", "python3", "-I", "-B", "-c", validation, str(candidate)))
        require(count == len(entries), "api_snapshot_validation_failed")
        require(sha256(SNAPSHOT.read_bytes()).hexdigest() == original_sha, "snapshot_changed_during_scan")
        atomic_json(ROOT / "previous-snapshot.json", original)
        os.replace(candidate, SNAPSHOT)
        candidate = None
        directory = os.open(SNAPSHOT.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return {"generated_at": result["generated_at"], "service_count": count}
    finally:
        os.close(lock)
        if candidate is not None:
            candidate.unlink(missing_ok=True)


def bazarr_authorization():
    info = AUTHORIZATION_PATH.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and stat.S_IMODE(info.st_mode) == 0o600
            and AUTHORIZATION_PATH.resolve(strict=True) == AUTHORIZATION_PATH
            and info.st_size <= 65, "private_review_authorization_required")
    value = AUTHORIZATION_PATH.read_text().strip()
    require(re.fullmatch(r"[a-f0-9]{64}", value), "private_review_authorization_required")
    return value


def bazarr_context_matches():
    """Match the existing runner's admission context without executing it."""
    try:
        inputs = read_json(BAZARR / "inputs.json")
        atlas = MARKER.parents[1]
        if (atlas / "deployments/current").read_bytes() != (BAZARR_PUBLICATION + "\n").encode():
            return False
        if sha256((atlas / "deployments/records" / BAZARR_PUBLICATION / "MANIFEST.sha256").read_bytes()).hexdigest() != inputs["baseline_manifest_sha256"]:
            return False
        info = MARKER.lstat()
        if (MARKER.is_symlink() or not MARKER.is_file()
                or [info.st_dev, info.st_ino] != inputs["maintenance_inode"]
                or sha256(MARKER.read_bytes()).hexdigest() != inputs["maintenance_sha256"]):
            return False
        if not RUNNER.is_file() or RUNNER.is_symlink():
            return False
        paths = sorted(RUNNER.parent.glob("*.py"))
        if any(not path.is_file() or path.is_symlink() for path in paths):
            return False
        sources = {path.name: sha256(path.read_bytes()).hexdigest() for path in paths}
        if sources != inputs["source_pins"]:
            return False
        ids = docker("ps", "--all", "--quiet", "--no-trunc").decode().split()
        rows = json.loads(docker("inspect", "--type", "container", *ids)) if ids else []
        original_id = inputs["original"]["Id"]
        observed = {}
        for row in rows:
            labels = row["Config"].get("Labels") or {}
            if row["Id"] == original_id or (
                row["Name"] == "/bazarr"
                and labels.get("io.project-atlas.service-update") == BAZARR.name
                and labels.get("io.project-atlas.original-container") == original_id
            ):
                continue
            observed[row["Id"]] = {
                "name": row["Name"], "image": row["Image"],
                "started_at": row["State"]["StartedAt"], "running": row["State"]["Running"],
                "restart_count": row["RestartCount"], "paused": row["State"].get("Paused", False),
            }
        return observed == inputs["protected"]
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError):
        return False


def bazarr_status():
    completed = read_json(BAZARR / "completed.json") if (BAZARR / "completed.json").is_file() else None
    rolled_back = (BAZARR / "rolled-back.json").is_file()
    recovery_required = (BAZARR / "rollback-requested.json").is_file() and not rolled_back
    assets = False
    if completed and not rolled_back:
        try:
            original = json.loads(docker("inspect", "--type", "container", completed["retained_original_id"]))[0]
            active = container("bazarr")
            assets = (not original["State"]["Running"] and active["Id"] == completed["container_id"]
                      and (BAZARR / "fresh-backup.json").is_file())
        except (RuntimeError, subprocess.SubprocessError):
            pass
    context_matches = bazarr_context_matches()
    return {
        "status": "rolled-back" if rolled_back else "updated" if completed else "prepared" if BAZARR.is_dir() else "unprepared",
        "version_label": completed.get("version_label") if completed and not rolled_back else None,
        "can_apply": BAZARR.is_dir() and not completed and not rolled_back and context_matches,
        "can_rollback": (assets or recovery_required) and MARKER.is_file() and context_matches,
        "blocked_reason": "deployment_context_changed" if BAZARR.is_dir() and not context_matches else None,
        "recovery_required": recovery_required,
        "maintenance_enabled": MARKER.is_file(),
    }


class Jobs:
    def __init__(self):
        ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        require(ROOT.resolve(strict=True) == ROOT and ROOT.stat().st_uid == 0
                and stat.S_IMODE(ROOT.stat().st_mode) == 0o700, "private_job_directory_required")
        self.path = ROOT / "job.json"
        if self.path.exists():
            previous = read_json(self.path)
            if previous.get("status") in ("queued", "running"):
                previous.update(status="failed", error="worker_restarted", completed_at=now())
                atomic_json(self.path, previous)

    def status(self):
        with LOCK:
            job = read_json(self.path) if self.path.exists() else None
        return {"job": job, "bazarr": bazarr_status()}

    def submit(self, operation, actor):
        require(operation in ("scan", "bazarr.apply", "bazarr.rollback"), "invalid_operation")
        require(isinstance(actor, str) and 0 < len(actor) <= 128 and actor.isprintable(), "invalid_actor")
        with LOCK:
            current = read_json(self.path) if self.path.exists() else {}
            require(current.get("status") not in ("queued", "running"), "operation_busy")
            if operation != "scan":
                state = bazarr_status()
                require(state["maintenance_enabled"], "maintenance_required")
                require(state["can_apply"] if operation == "bazarr.apply" else state["can_rollback"],
                        "reviewed_operation_unavailable")
            job = {"id": uuid4().hex, "operation": operation, "actor": actor, "status": "queued",
                   "started_at": now(), "completed_at": None, "progress": "Queued", "error": None}
            atomic_json(self.path, job)
            threading.Thread(target=self.run, args=(job,), daemon=True).start()
            return job

    def update(self, job, **changes):
        with LOCK:
            job.update(changes)
            atomic_json(self.path, job)

    def run(self, job):
        try:
            self.update(job, status="running", progress="Starting")
            if job["operation"] == "scan":
                result = publish_scan(lambda value: self.update(job, progress=value))
            else:
                log = ROOT / (job["id"] + ".log")
                action = "resume" if job["operation"] == "bazarr.apply" else "rollback"
                with log.open("xb") as stream:
                    process = subprocess.run(
                        ["/usr/bin/python3", "-I", "-S", "-B", str(RUNNER), action,
                         "--authorize-review", bazarr_authorization()],
                        stdout=stream, stderr=subprocess.STDOUT, check=False,
                    )
                require(process.returncode == 0, "bazarr_operation_failed_review_host_journal")
                self.update(job, progress="Refreshing service observations")
                result = publish_scan(lambda value: self.update(job, progress=value))
            self.update(job, status="completed", completed_at=now(), progress="Completed", result=result)
        except Exception as error:
            reason = str(error)
            self.update(job, status="failed", completed_at=now(), progress="Stopped",
                        error=reason if reason.isidentifier() else "host_operation_failed")


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True

    def __init__(self, jobs):
        self.jobs = jobs
        parent = SOCKET.parent
        info = parent.stat()
        require(parent.resolve(strict=True) == parent and info.st_uid == 0
                and not stat.S_IMODE(info.st_mode) & 0o022, "control_directory_permissions")
        if SOCKET.exists():
            previous = SOCKET.lstat()
            require(stat.S_ISSOCK(previous.st_mode) and previous.st_uid == 0, "control_socket_changed")
            with socket.socket(socket.AF_UNIX) as client:
                try:
                    client.connect(str(SOCKET))
                except ConnectionRefusedError:
                    SOCKET.unlink()
                else:
                    raise RuntimeError("worker_already_running")
        super().__init__(str(SOCKET), Handler)
        self.socket_inode = SOCKET.stat().st_ino
        os.chown(SOCKET, 0, 20000)
        os.chmod(SOCKET, 0o660)

    def server_close(self):
        super().server_close()
        if SOCKET.exists() and SOCKET.lstat().st_ino == getattr(self, "socket_inode", None):
            SOCKET.unlink()


class Handler(socketserver.StreamRequestHandler):
    timeout = 5

    def handle(self):
        try:
            _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            require(uid in (0, 999), "peer_not_permitted")
            raw = self.rfile.readline(4097)
            require(len(raw) <= 4096 and raw.endswith(b"\n"), "invalid_request")
            request = json.loads(raw)
            require(isinstance(request, dict), "invalid_request")
            if request == {"operation": "status"}:
                value = self.server.jobs.status()
            else:
                require(set(request) == {"operation", "actor"}, "invalid_request")
                value = {"job": self.server.jobs.submit(request["operation"], request["actor"])}
            response = {"ok": True, "value": value}
        except Exception as error:
            reason = str(error)
            response = {"ok": False, "error": reason if reason in (
                "peer_not_permitted", "invalid_request", "invalid_operation", "invalid_actor",
                "operation_busy", "maintenance_required", "reviewed_operation_unavailable",
            ) else "control_unavailable"}
        self.wfile.write((json.dumps(response) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("serve", "scan"))
    args = parser.parse_args()
    require(os.geteuid() == 0, "root_required")
    os.umask(0o077)
    if args.action == "serve":
        with Server(Jobs()) as server:
            server.serve_forever()
    else:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(str(SOCKET))
            client.sendall(b'{"operation":"scan","actor":"scheduler"}\n')
            with client.makefile("rb") as stream:
                response = json.loads(stream.readline(65537))
            require(response.get("ok") is True or response.get("error") == "operation_busy",
                    "scan_submission_failed")


if __name__ == "__main__":
    main()
