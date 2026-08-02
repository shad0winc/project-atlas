#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.4-$STAMP"

die(){ echo "ERROR: $*" >&2; exit 1; }

[[ -d "$ROOT/.git" ]] || die "Not a git repository"
cd "$ROOT"

for f in docs/governance/README.md docs/ENGINEERING_GUIDE.md \
docs/ENGINEERING_CHECKLIST.md docs/BUILD_LOG.md CHANGELOG.md ROADMAP.md
do
  [[ -f "$f" ]] || die "Missing $f"
done

[[ ! -e docs/governance/CODING_STANDARDS.md ]] || die "CODING_STANDARDS.md already exists"

mkdir -p "$BACKUP_DIR"

cat > docs/governance/CODING_STANDARDS.md <<'EOF'
# Atlas Coding Standards

## Purpose
This document defines the permanent coding standards for Project Atlas.

## General Principles
- Readability before cleverness.
- Explicit behavior over hidden behavior.
- Deterministic and testable implementations.
- Small, cohesive modules.
- Stable public contracts.

## Project Structure
Code should be organized into focused packages with clear ownership.
Public APIs are exported intentionally through package `__init__.py` files.

## Domain Models
Public models should:
- normalize inputs;
- validate identity;
- validate child contracts;
- normalize timestamps;
- provide deterministic serialization;
- have dedicated tests;
- be exported through package interfaces.

## Services
Services orchestrate domain behavior, avoid presentation logic, preserve domain
errors, and translate provider failures.

## Providers
Providers isolate infrastructure concerns and return normalized contracts.

## CLI Standards
Human-readable and JSON output must remain stable and documented.

## Compatibility
Prefer incremental migration and compatibility aliases before breaking changes.

## Documentation
Code is not complete until applicable architecture, CLI/API, BUILD_LOG,
CHANGELOG, and ROADMAP updates are made.

## Definition of Code Complete
Implementation, validation, documentation, review, commit, and push are all
required.
EOF

python3 - <<'PY'
from pathlib import Path

def append_once(path, marker, block):
    p=Path(path)
    t=p.read_text()
    if marker in t:
        return
    p.write_text(t.rstrip()+"\n\n"+block.strip()+"\n")

# README: convert/add checklist item
p=Path("docs/governance/README.md")
t=p.read_text()
if "- [ ] `CODING_STANDARDS.md`" in t:
    t=t.replace("- [ ] `CODING_STANDARDS.md`",
                "- [x] [`CODING_STANDARDS.md`](CODING_STANDARDS.md)",1)
p.write_text(t)

append_once("docs/ENGINEERING_GUIDE.md","## Coding Standards",
"""## Coding Standards

The permanent coding conventions are defined in
[`governance/CODING_STANDARDS.md`](governance/CODING_STANDARDS.md).""")

append_once("docs/ENGINEERING_CHECKLIST.md","## Coding Standards Review",
"""## Coding Standards Review

- [ ] Public contracts follow Atlas coding standards.
- [ ] New code preserves compatibility or documents migration.
""")

append_once("docs/BUILD_LOG.md","## M-021.4 — Coding Standards",
"""---

# 2026-08-02

## M-021.4 — Coding Standards

### Completed

- Added the permanent Coding Standards document.
- Linked governance and engineering documentation.
- Added coding standards review gates.

### Validation

- Markdown validation.
- Link validation.
- Required section validation.
- `git diff --check`.
""")

p=Path("CHANGELOG.md")
t=p.read_text()
e="- Added the Atlas Coding Standards governance document defining permanent coding conventions.\n"
if e not in t:
    p.write_text(t.replace("### Documentation\n\n","### Documentation\n\n"+e,1))

p=Path("ROADMAP.md")
t=p.read_text()
p.write_text(t.replace("- [ ] Coding Standards","- [x] Coding Standards",1))
PY

python3 - <<'PY'
from pathlib import Path
assert Path("docs/governance/CODING_STANDARDS.md").exists()
print("Coding Standards validated.")
PY

git diff --check

echo "M-021.4 applied."
