# Immutable maintenance source generation

The preparer creates only an inactive `source-staging` tree in the new repair's
namespace. The planned `source` path remains absent. It does not change Caddy
binds, install/start the authority, recreate containers, advance canonical Git,
write a deployment/current pointer or release maintenance/recovery ownership.

Preparation verifies the retained archive digest and Git commit marker, every
regular tracked blob and executable bit, and the reconstructed Git tree. Path
traversal, duplicate members, symlinks, hardlinks, special files, file/directory
collisions and untracked empty archive directories refuse. Source bytes stream
through bounded chunks, including large maintenance images.

The new repair directory is private to the preparing host identity. Production
uses root UID/GID; tests use their own non-root identity. Prepared source
directories become mode 0555 and files mode 0444/0555 according to Git executable
bits. Files and directories are flushed before the manifest marker is created
and its parent is flushed. An existing complete exact preparation can be verified
and flushed again. Partial, foreign or changed staging evidence is retained and
refused; it is never filled in or overwritten automatically.

Two internal namespace primitives are supplied for the pending rollout adapter.
`publish` requires a proven held context and atomically moves `source-staging` to
`source`. `retain` requires both a held context and proof that Caddy and the host
authority no longer use the generation, and moves `source` to `source-retained`.
The latter preserves all source and recovery evidence. Both transitions use Linux
renameat2 with RENAME_NOREPLACE and parent fsync. Unsupported or failed no-replace
operations refuse. An existing foreign target, including an empty directory,
cannot be replaced by a race. Exact completed transitions can be flushed/resumed
without replacing source inodes.

The guards are callbacks for a pinned future host coordinator. They must validate
original ownership, maintenance, protected evidence, inherited execution exclusion
and actual runtime inactivity. A caller assertion is not production admission.
There is no CLI or ordinary-update entry point in this module.

Private tests cover real filesystem modes, archive refusals, complete and partial
preparation after SIGKILL, and publish/retain process-death boundaries. The CT100
staging runner executes only prepare/inspect against the real planned repair and
independently checks its source bytes with the accepted live provenance verifier.
It does not call either namespace transition against production.

A staged generation is an asset, not a deployed component, an expanded publication
candidate, private/public acceptance, an operational backup restore or proof of
physical power-loss recovery. The production action adapter, release CI and held
acceptance/finalizer integration remain separate required gates.
