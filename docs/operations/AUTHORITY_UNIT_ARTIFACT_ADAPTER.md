# Held authority unit artifact adapter

The source-generation adapter can now delegate the authority-unit surface to a
bounded file adapter. The only final filename is atlas-maintenance-control.service.
A unique hidden staged file is prepared on the same filesystem as the unit. It is
flushed and atomically renamed without replacement. Installed bytes must match the
pinned proposal and have the expected owner, group, single link, and mode 0644.

Rollback requires the delegated authority-inactive guard and moves the installed
file to a unique hidden retained filename. It never deletes that evidence or
replaces a foreign file. Partial preparation, foreign paths, links, changed bytes,
metadata, or ambiguous namespaces refuse retry and remain available for review.
A retained artifact cannot be reapplied under its old plan.

Journal confirmation reflushes a visible renamed unit before accepting completion
or changing direction after interruption. The source is retained only after the
unit has been retained and the remaining runtime adapter proves inactivity.

This stage runs actual file transitions only in private fixture directories. It
also tests the accepted production proposal bytes there. No systemctl command,
service installation, daemon reload, enable/start/stop, production directory
preparation, or Docker action is performed. Service lifecycle, systemd precedence
and drop-in inspection, socket ownership, component replacement and operational
rollback remain pending. These tests do not establish physical power-loss safety.
