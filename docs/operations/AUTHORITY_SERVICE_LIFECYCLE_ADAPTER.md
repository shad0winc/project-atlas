# Held authority service lifecycle adapter

The authority service surface now has bounded command construction and journal
integration. Commands are restricted to systemctl --system daemon-reload and
start/stop of atlas-maintenance-control.service. The executor uses a clean
environment, no shell, no prompts, and a 30-second command timeout. It does not
enable, disable, restart, or kill services.

The native probe delegates active process, exact source command, credentials,
capabilities, socket permissions and listener ownership to the accepted native
provenance verifier. It additionally rejects shadow units, generic/dash-prefix
and unit-specific drop-ins, and unexpected boot enablement. The coordinator must
supply that verifier from checksum-verified sealed source and validated records;
coordinator admission and real systemd execution remain pending.

Initial inactive, unit-installed inactive, and restored inactive states have no
service identity. Active identities bind the exact systemd process incarnation
and socket inode. Immediately before start/stop the expected observation is
checked again. Uncertain command results leave the journal intent for explicit
inspection/resume. They do not trigger blind stop or replacement. A recognized
socket-not-yet-ready state has a bounded wait; contract failures do not.

Rollback stops the exact authority before retaining its unit. Unit confirmation
then reloads systemd and proves the manager no longer has that unit loaded. Only
after those boundaries may the source be retained. Resume repeats confirmation
without repeating a completed start or stop.

Tests use actual private source/unit files and file-backed systemd fixtures.
The default executor is inspected through a mocked subprocess boundary. No host
systemctl command is run, no production service is activated, and real systemd
or operational rollback success is not claimed. Docker actions remain pending.
