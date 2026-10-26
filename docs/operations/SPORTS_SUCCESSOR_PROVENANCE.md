# Sports successor provenance

Schema 3 describes independent backend and writer image origins without changing
the schema-2 maintenance publication or pretending that Core, notifications,
Ingress applications, or the Sports controller moved to a newer revision.

The successor copies every sealed base artifact byte for byte except metadata
and the effective image manifest. It links the original schema-2 record by its
identifier and manifest digest. The inherited service ledger describes historical
recipes. The native validator returns an effective ledger with explicit writer
and backend overrides. Historical acceptance remains historical evidence.

New supplements bind a complete Git source archive and reconstructed tree, exact
successful push CI, image identities, installed code maps, original image-build
origins and validation-receipt digests. An older writer image may be reused only
when its required build inputs match the verified source archive. Its build
revision is recorded separately from the revision against which those inputs
were verified. New image references are immutable image IDs.

This change provides record validation, downgrade protection, and refusal guards.
It supplies no current-pointer publisher, maintenance release, recovery-owner
recreation, registry mutation, or application action. Ordinary schema-3 live
inspection deliberately refuses. A separate held provenance API, described in
SPORTS_HELD_RUNTIME.md, requires trusted host exclusion/configuration callbacks
and verifies source and image identity without granting runtime acceptance. Ordinary updates,
inheritance and restores also refuse this schema before modifying a destination.

The ordinary publication-completion verifier retains its current-pointer
requirement. A separate `inspect_completed_history` method verifies only a fully
completed maintenance handoff after a native-verified successor becomes current.
Its mandatory verifier callback must use the schema-3 `successor_proof` validator;
it binds both manifest digests and checks the current pointer before and after.
It preserves archived fence identities and grants no runtime acceptance or
production execution. Completion and handoff mutation APIs cannot use this path.

Writer build-input evidence must cover the Dockerfile and every file selected by
its COPY instructions, including non-Python configuration. The one shared input
outside modules/sports is atlas/sports_shared_admission_config.py; this exact path
is allowed, while unrelated Atlas modules remain refused. Installed destinations
and bytes are independently derived from the verified source archive. The real
accepted writer Dockerfile is used in regression fixtures with synthetic contents.
