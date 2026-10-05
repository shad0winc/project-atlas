# Offline native acquisition policy plan

`atlas.media_requests.providers.native_policy_plan.build_native_policy_plan` constructs a review candidate from a complete, credential-free native snapshot. It performs no HTTP calls, file writes, native installation, schema migration, request submission or activation. The existing acquisition factory and its default-off behavior are unchanged.

## Ownership boundary

Produce three new, distinctly named `[Atlas v1]` profiles per instance: `english_preferred`, `english_required`, and `original_subbed`. Do not edit or reassign the existing guide profile 7, existing guide custom-format definitions, media, monitoring or searches. New profiles score only newly owned custom formats; existing guide custom formats receive zero in those profiles. Baseline rules with nonzero scores are copied into separately named Atlas definitions, with a source-definition fingerprint. This isolates candidate rules and scores from later guide definition updates.

A native service may automatically append zero-score rows to existing profiles when custom formats are created. Preservation must compare pre-existing scores and settings, and require all newly appended rows to be zero; byte-for-byte profile equality would incorrectly reject that native behavior. Existing titles stay on their original profiles.

This boundary does **not** establish Recyclarr safety. Current readbacks identify four guide-backed names matching native profile 7 and score resets enabled without exceptions. Cached guide identity, other automation and destructive pruning remain unverified. A later installer must require a proven ownership/no-pruning contract before modifying production. Do not run manual Recyclarr sync against newly installed profiles until that contract is established. This candidate sets `activation_allowed`, `native_ids_allocated`, cached ownership and pruning proof to false.

## Candidate ordering

The input profile 7 supplies release-tier, source, codec and other baseline scores. `Language: Not Original`, `Dubs Only`, and `Anime Dual Audio` scores are neutralized in the new profiles so they do not contradict the explicit mode. Existing hard exclusion rules remain hard exclusions.

All supported 720p, 1080p and 2160p qualities occupy one equality group. Unknown, Raw-HD, disc images, camera recordings and screener qualities are not admitted. An explicit `allow_anime_sd=True` can include supported SD anime qualities; it defaults to false and does not enable activation. SD fallback stays gated on truthful UI/readiness disclosure.

Let P be the sum of positive baseline scores and N the absolute sum of baseline penalties strictly between -10000 and zero. Resolution step S=P+N+1, English candidate bonus=4S, and hard rejection=-(4S+3S+P+1). Subject to native matching at most one resolution band, resolution beats every baseline tie score and an English candidate beats an original-language 4K candidate with every positive baseline score. A hard rejection cannot be rescued by the allowed positive scores. Integer overflow is rejected.

An English candidate requires both native English language matching and the reviewed positive English audio title hint. English Required also hard rejects missing English language or missing hint. Original Subbed hard rejects non-original language and has no English bonus. This is conservative acquisition evidence, **not** proof of actual imported spoken audio. Original Subbed separately requires full-dialogue English subtitles at readiness; the profile cannot establish that condition.

Radarr candidate language is Any so the original-language setting on profile 7 cannot independently reject an English dub. Both regular and anime candidates support up to 4K; actual hardware and player evidence remain open.

## Instance-wide PROPER/REPACK policy

The plan lists `doNotPrefer` as a separately reviewed prerequisite. This affects the whole native instance, including titles still on profile 7. The previous read-only impact observation found seven monitored titles across the four instances; it is not a guarantee about future upgrade behavior. No management setting is changed by this planner. A native installation transaction must preserve unrelated management settings and consider this effect explicitly; it must not start searches, run sync or reassign existing titles.

## Execution remains gated

The output uses symbolic custom-format keys and profile descriptions, not POST-ready bodies or guessed profile IDs. Any installer needs native-version/schema verification, current baseline and ownership guards, private recovery data, durable per-operation intent and receipts, uncertain-result reconciliation without blind POST retries, explicit native ID allocation/readback, and exact immutable factory maps. Existing negative IDs for native language meanings are not profile or server IDs.

Focused tests cover input immutability, isolated ownership, complete identities and score rows, conflicting or partial inventories, arithmetic bounds, mode guards, default-off SD and activation behavior. They do not claim new native ranking, matching, Recyclarr coexistence or media E2E proof. Historical installers and passed staging suites are not rerun by this change.

Semantic fingerprints hash sorted compact JSON without a terminal newline. Packet/file hashes cover exact bytes and file modes separately. Acquisition recovery/schema activation, exact episodes/future follows/readiness, retention, Sports sharing/capacity, global management impact and the separately agreed release reset stay independent release gates.
