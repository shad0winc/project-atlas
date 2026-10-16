# Sports recovery ownership correction

## Observed CT100 container contract

Read-only observation on 2026-10-16 at canonical source `45786a57` and active
deployment `update-20261015T211211Z-632971` found the following. All observed
containers stayed running with unchanged image/start timestamps during the probe.

| Surface/consumer | Container path | Observed numeric UID:GID | Observed mode |
| --- | --- | --- | --- |
| Dispatcharr PostgreSQL 17 process and cluster | /data/db | 1000:1000 | 0700 directory; PG_VERSION 0600 |
| Dispatcharr JWT | /data/jwt | 0:0 | 0600 |
| Teamarr process | /app/data | 0:0 | 0750 data directory |
| Teamarr database | /app/data/teamarr.db | 0:0 | 0644 |
| Private Sports writer process | Metadata paths absent | 1000:1000 | No metadata mounts deployed |
| Atlas API process | Not a native-state owner | 999:999 | Supplementary groups 20000, 20001 |
| Sports controller and notifications | Not native-state owners | 1000:1000 | Supplementary group 20000 |

Dispatcharr `/data` is a writable bind from `/mnt/storage/configs/dispatcharr`.
Teamarr `/app/data` is a writable bind from `/mnt/storage/configs/teamarr`.
Both containers have an empty configured User and execute the probe as root;
Dispatcharr's actual application/PostgreSQL children run as UID/GID 1000.
Configured container User alone therefore cannot establish artifact ownership.

Pinned observed Dispatcharr image:
`sha256:e5d4b045b51519be4142a7baf7da6750ad33f80dcb0a77b8832c2ce930c6fe12`.
Pinned observed Teamarr image:
`sha256:ecec625df0a029cddecf72fcb86d0d2eb9c16ce14f9377b1ddc0954bba4e2ec7`.

These are container namespace identities, not certification of host UID mapping.
Host path metadata, user-namespace mapping and image/init behavior still need
validation before any production ownership conversion. No credential values,
database contents or JWT bytes were read by this observation.

## Corrected prepared bundle contract

The original plan grouped Dispatcharr's database and JWT under one identity.
The observed root-owned 0600 JWT disproves that assumption for this deployment.
Preparation now requires four independent numeric identities:

```python
identities = {
    "dispatcharr": [1000, 1000],       # PostgreSQL cluster consumer
    "dispatcharr_jwt": [0, 0],        # JWT startup/identity artifact
    "teamarr": [0, 0],
    "writer": [1000, 1000],
}
```

These values illustrate the observation, not an automatic production config.
There is no default or inferred JWT owner. BUNDLE.json is now version 2;
prepared version-1 bundles are rejected and must be regenerated, then associated
and staged again. Do not edit an old prepared receipt to upgrade it. Backup
archive format numbers and metadata recovery manifest versions are unchanged.

Prepared artifacts still belong to the staging operator with 0700 directories
and 0600 files. Publication owner/mode fields remain intentions only; there is
no chown of existing production or prepared objects. The intended Teamarr file
mode remains private 0600, distinct from observed deployed 0644. That choice
still needs real restart/readability acceptance. Metadata policy retains root
ownership with the writer GID, planned directory 0750 and file 0640.

## Remaining stop and live integration boundary

All six observed containers reported no explicit stop timeout and default
SIGTERM. This reports configuration only; it is not a stop/restart rehearsal.
Dispatcharr runs PostgreSQL and application workers in one container. Its
entrypoint shutdown and the clean cold-cluster postcondition must be exercised
in isolation before authorizing production cold-copy acquisition.

The deployed writer has no metadata database/policy mounts. Their absence is
expected for the old active deployment, not evidence to delete state or infer
a successful future provisioning/restore. Existing writer quiescence, live
format-2/3 blocks and isolated publication scope remain unchanged.
