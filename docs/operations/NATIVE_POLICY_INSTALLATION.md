# Isolated native policy installation engine

`compile_native_installation` compiles the offline native policy plan against captured native versions and API schemas. `NativePolicyInstaller` creates unused Atlas custom formats and profiles through explicitly supplied native clients. Importing the module performs no I/O. No API route, scheduler, acquisition factory, CLI command or default provider invokes the installer. This source change supplies a tested engine, not an authorization to run a production installation.

## Schema and payload boundaries

The October 5 capture establishes Radarr 6.4.4.10685 and Sonarr 4.0.20.3014 on both regular and anime instances. The credential-free schema snapshot has SHA256 `cfa35101f6861361682c6268551159d4e9ec8204523eab9d8770bb4c3e02da19`. The compiler consumes the capture rather than hardcoding guessed native profile IDs. It rejects unsupported implementations, unknown field types, invalid select values, missing reviewed defaults, duplicate field identities and a changed custom-format catalog.

All native specification fields are supplied explicitly, including `exceptLanguage=false` when omitted by the symbolic candidate. Existing guide definitions are copied into distinct Atlas definitions. A payload contains every native quality, with unsupported qualities disabled and supported 720p/1080p/2160p qualities in one equality group. Its client-defined quality-group ID is distinct from the native-allocated profile ID. SD fallback remains excluded. Existing guide custom formats have zero scores in new profiles; new Atlas formats receive the planned mode-specific scores.

The captured production baseline and schemas compile into 183 distinct Atlas definitions and 12 profiles. Compilation proves payload construction against captured schema evidence; it does not prove native validation, matching, ranking or imported spoken audio/subtitles. Native execution and native acceptance remain release work.

## Required production caller

The engine intentionally requires caller-supplied clients bound separately to the four exact instances and a guard returning true. No default permissive guard or transport is provided. A reviewed execution runner must bind and verify private configuration, expected native image IDs, exact source/deployment generations, activation flags, request registry, Recyclarr configuration/cache identities, ownership controls, update/maintenance guards and operation scope. Native credentials and backend URLs stay in that runner's private transport; they are not journal fields or output.

The Recyclarr 8.3.2 source and current configuration/cache readbacks establish no custom-format pruning and score resets scoped to the existing guide profile 7. A subsequent all-container inventory found no Recyclarr name, image or Compose service among 28 CT100 containers, including stopped containers. This does not exclude removed one-shot containers, manual execution with another configuration or external automation. These facts are a bounded coexistence review, not a claim that every automation path has been excluded. The execution guard must establish control of writers for the installation interval; do not turn an unknown into a verified ownership flag.

Use only clients whose creation method is bound to `customformat` and `qualityprofile`. A caller must not provide methods that start searches, sync Recyclarr, reassign titles, modify monitoring or update global configuration. The installer itself calls only creation on those two resource kinds. Native profile IDs are recorded from verified native readbacks. Returning IDs does not enable routing or configure factory mappings.

## Durable recovery

The caller creates an absolute, owned 0700 journal directory. The engine rejects symlink components, non-private journal/lock files and concurrent writers. Complete raw baseline inventories, management settings and title assignments are saved privately in a 0600 journal before any native creation. The directory and journal are fsynced; operation payload and intent are persisted before POST. The writer lock is held throughout the installation; a stopped writer leaves the journal in place.

On a new operation, a case-insensitive owned-name collision stops the installation before POST. An external response ID is persisted separately before readback. The receipt must match the intended name and full policy semantics, have a new positive native ID outside the observed pre-POST inventory, and agree with any returned ID. Verified receipts are checked again on resume. Duplicate candidates, differing payloads, conflicting IDs or a changed installation plan stop without adoption.

If a timeout, interrupted receipt write or delayed readback leaves an intent, resume performs reads only for that operation. A subsequently visible exact receipt can be reconciled. If no receipt is visible, the installer stops and never repeats that POST. This includes a crash after intent but before the network call; absence is not proof that retrying is safe. There is no reset, delete, blind-retry, rollback or journal-clearing helper. A separately reviewed reconciliation decision is required for unresolved absence. The journal is private recovery data and must never be uploaded or printed.

## Preservation and activation

After creations and at completion, the engine verifies pre-existing custom-format responses are unchanged. Existing profile settings and score rows remain unchanged; native-added rows for newly created formats may be appended only with zero scores. Duplicate score identities are rejected. Previously verified Atlas policies must still match their receipts. Existing managed title profile assignments, title monitoring and season monitoring are compared; unrelated title statistics may change naturally. Native resource APIs outside policy creation are never mutation targets.

The complete instance-wide management response remains unchanged. The engine does not set `downloadPropersAndRepacks=doNotPrefer`; the impact on seven existing monitored titles and that setting's separate approval remain open. Success is `NATIVE_POLICIES_INSTALLED_NOT_ACTIVATED`, with `activation_allowed=false` and no global setting change. API/scheduler deployment, native acceptance/ranking, immutable factory maps, request schema migration, acquisition/receipt recovery activation, actual spoken audio/full English subtitles, exact/future episodes, retention, Sports upstream/license sharing and release reset remain independent gates.

## Validation

Focused behavioral tests cover complete payloads, allocated IDs, preservation, both format/profile lost responses, delayed commit, unresolved absence, conflicting/duplicate receipts, interrupted intent/receipt persistence, native/schema/baseline drift, guard failures, ownership collisions, verified-policy drift, duplicate score rows, private errors and journal/lock protection. Mock clients establish control flow and recovery invariants, not native matching or service behavior. The packet also compiles the real captured baseline/schema through normal source imports and compares the exact preview bytes. CT100 tests run in its existing canonical virtualenv with explicit review PYTHONPATH; no native HTTP call is made by test runners.
