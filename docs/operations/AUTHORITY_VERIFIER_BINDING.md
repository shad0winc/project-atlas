# Authority verifier binding

The binding consumes checksum-pinned native schema-2 verifier bytes and an
unchanged manifest-covered offline record. Source is compiled from the verified
bytes rather than reopened through an import loader. Both verifier modules are
bound together explicitly; their later extension lookup cannot reload a changed
helper. The offline validator must accept the complete schema-2 record before a
native authority probe is constructed.

Every probe operation checks source checksums, record inventory, the manifest and
all record file checksums again. Symlinks, hardlinks, writable files/directories,
wrong ownership, partial inventories and drift refuse. The command boundary is
restricted to two exact local systemd show queries with a clean environment and a
bounded timeout. It cannot start or stop a service, inspect Docker or send an
authority operation. Active process/socket verification remains the existing
native verifier's responsibility.

The initial host observation proves only an inactive, absent authority boundary.
It does not prove real systemd start/stop, active socket lifecycle, production
rollout, publication, owner release or acceptance. The existing schema-2 ordinary
update, inheritance and restore refusals remain unchanged. The remaining
coordinator must bind this probe to source/unit/service/container adapters and an
admitted plan under the original recovery owner's real scheduler flock.
