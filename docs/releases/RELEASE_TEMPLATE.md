# Atlas Release Template

**Document Status:** Template
**Applies To:** All Atlas Releases
**Document Owner:** Project Atlas Engineering
**Last Updated:** 2026-08-02

---

# 1. Release Information

Record the identifying information for the release.

| Field | Value |
| --- | --- |
| Release Version | __________________ |
| Release Type | Major / Minor / Patch / Hotfix |
| Release Date | __________________ |
| Milestone | __________________ |
| Branch | __________________ |
| Commit | __________________ |
| Tag | __________________ |
| Release Manager | __________________ |

---

# 2. Executive Summary

Provide a concise summary of the release.

Include:

- overall purpose;
- primary improvements;
- intended audience;
- significant operational impact.

~~~text
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
~~~

---

# 3. Release Scope

Document what is included and intentionally excluded.

## Included

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

## Explicitly Excluded

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

---

# 4. New Features

| Feature | Description | Notes |
| --- | --- | --- |
| | | |

---

# 5. Improvements

| Area | Improvement | Notes |
| --- | --- | --- |
| | | |

---

# 6. Bug Fixes

| Issue | Resolution | Notes |
| --- | --- | --- |
| | | |

---

# 7. Breaking Changes

| Change | Impact | Mitigation |
| --- | --- | --- |
| | | |

Enter `None` when the release has no breaking changes.

---

# 8. Known Limitations

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

---

# 9. Upgrade Notes

Include backups, migrations, configuration updates, service restarts, and
post-upgrade validation.

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

---

# 10. Validation Summary

| Validation | Result | Evidence |
| --- | --- | --- |
| Engineering | | |
| Repository | | |
| Runtime | | |
| Operations | | |
| User Acceptance | | |
| Administrator Acceptance | | |
| Security | | |
| Backup and Recovery | | |
| Documentation | | |

---

# 11. Compatibility

Record supported upgrade paths, dependencies, deprecations, and migration
requirements.

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

---

# 12. Release Metrics

| Metric | Value |
| --- | --- |
| Files Changed | |
| Commits | |
| Contributors | |
| Tests Executed | |
| Automated Tests Passed | |
| Runtime Checks Passed | |
| Release Duration | |

---

# 13. Rollback Guidance

Include rollback triggers, procedure, data considerations, configuration
considerations, post-rollback validation, and irreversible changes.

~~~text
______________________________________________________________________
______________________________________________________________________
~~~

---

# 14. Approval

## Approval Decision

- [ ] Approved
- [ ] Rejected
- [ ] Deferred pending corrective work

## Approval Record

| Field | Value |
| --- | --- |
| Approver | |
| Recorded Approval | |
| Date | |
| Notes | |

---

# 15. References

- [`README.md`](README.md);
- [`V1_RELEASE_PLAN.md`](V1_RELEASE_PLAN.md);
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md);
- [`USER_ACCEPTANCE.md`](USER_ACCEPTANCE.md);
- [`../../ROADMAP.md`](../../ROADMAP.md);
- [`../../CHANGELOG.md`](../../CHANGELOG.md);
- [`../BUILD_LOG.md`](../BUILD_LOG.md).

---

# Template Completion

This template becomes a permanent release record only after:

- all placeholders are completed;
- non-applicable sections explicitly record `Not Applicable`;
- release validation is finished;
- known limitations are documented;
- certification is approved;
- the document is committed with the release;
- the repository accurately reflects the released software.

Do not silently remove sections. Record why a section does not apply.
