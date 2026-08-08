#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.3-$STAMP"

die(){ echo "ERROR: $*" >&2; exit 1; }

[[ -d "$ROOT/.git" ]] || die "Not a git repository"
cd "$ROOT"

for f in \
 docs/governance/README.md \
 docs/ENGINEERING_GUIDE.md \
 docs/ENGINEERING_CHECKLIST.md \
 docs/BUILD_LOG.md \
 CHANGELOG.md ROADMAP.md
do
 [[ -f "$f" ]] || die "Missing $f"
done

[[ ! -e docs/governance/DEVELOPMENT_WORKFLOW.md ]] || die "Workflow already exists"

mkdir -p "$BACKUP_DIR"
cp -a docs/governance/README.md docs/ENGINEERING_GUIDE.md docs/ENGINEERING_CHECKLIST.md docs/BUILD_LOG.md CHANGELOG.md ROADMAP.md "$BACKUP_DIR/" 2>/dev/null || true

cat > docs/governance/DEVELOPMENT_WORKFLOW.md <<'EOF'
# Atlas Development Workflow

## Purpose

This document defines the canonical engineering workflow for Project Atlas.

## Sprint Lifecycle

```text
Repository Review
        ↓
Architecture Review
        ↓
Engineering Specification
        ↓
Scope Approval
        ↓
Implementation
        ↓
Focused Validation
        ↓
Regression Testing
        ↓
Runtime Validation (when applicable)
        ↓
Documentation Updates
        ↓
Repository Review
        ↓
Commit
        ↓
Push
```

## Scope Management

- Scope is approved before implementation.
- New ideas are deferred to future milestones unless they resolve a blocker or defect.
- One primary objective per sprint whenever practical.

## Validation Gates

Every applicable sprint includes:

- Focused validation
- Regression testing
- Runtime validation when required
- Documentation review
- Repository review
- `git diff --check`

## Completion

A sprint is complete only after implementation, validation, documentation,
repository review, commit, and push.
EOF

python3 - <<'PY'
from pathlib import Path

def append_once(path, marker, text):
    p=Path(path)
    s=p.read_text()
    if marker in s:return
    p.write_text(s.rstrip()+"\n\n"+text.strip()+"\n")

append_once("docs/governance/README.md","DEVELOPMENT_WORKFLOW.md",
"- [x] [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md)")
append_once("docs/ENGINEERING_GUIDE.md","## Development Workflow",
"""## Development Workflow

The canonical Atlas engineering workflow is documented in
[`governance/DEVELOPMENT_WORKFLOW.md`](governance/DEVELOPMENT_WORKFLOW.md).""")
append_once("docs/ENGINEERING_CHECKLIST.md","## Development Workflow Review",
"""## Development Workflow Review

- [ ] Sprint followed the approved workflow.
- [ ] Scope changes were deferred unless required by a blocker or defect.
""")
append_once("docs/BUILD_LOG.md","## M-021.3 — Development Workflow",
"""---

# 2026-08-02

## M-021.3 — Development Workflow

### Completed

- Added the permanent Atlas Development Workflow.
- Linked governance and engineering documentation.
- Added workflow review checklist.

### Validation

- Markdown validation.
- Link validation.
- `git diff --check`.
""")
for file,old,new in [("ROADMAP.md","- [ ] Development Workflow","- [x] Development Workflow")]:
 p=Path(file); t=p.read_text(); 
 if old in t: p.write_text(t.replace(old,new,1))
p=Path("CHANGELOG.md");t=p.read_text()
entry="- Added the Atlas Development Workflow governance document defining the canonical engineering sprint lifecycle.\n"
if entry not in t:
 anc="### Documentation\n\n"
 p.write_text(t.replace(anc,anc+entry,1))
PY

python3 - <<'PY'
from pathlib import Path
assert Path("docs/governance/DEVELOPMENT_WORKFLOW.md").exists()
print("Workflow document validated.")
PY

git diff --check

echo
echo "M-021.3 applied."
echo "Review:"
echo "  git status --short"
echo "  git diff --check"
echo "  git diff --stat"
