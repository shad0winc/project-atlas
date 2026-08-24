# Backup and Recovery — Legacy Entry Point

This path is retained for backward-compatible documentation links and historical
navigation.

The complete and canonical Project Atlas v1 backup and state-restore procedure is:

`docs/guides/BACKUP_RESTORE_GUIDE.md`

Do not execute a live restore from abbreviated or historical instructions in this
path. Atlas restore is a controlled state transaction with archive verification,
isolated staging, explicit planning, production authorization, maintenance
isolation, writer quiescence, post-apply verification, and fail-closed
resume/abort behavior.

Deployment rollback is a different transaction. Use:

`docs/guides/ROLLBACK_GUIDE.md`

For diagnosis before choosing a recovery transaction, use:

`docs/guides/TROUBLESHOOTING_GUIDE.md`

For routine administrator workflows, use:

`docs/guides/ADMINISTRATOR_GUIDE.md`

Historical implementation and controlled-production evidence remains available in
Git history and release documentation; it is not duplicated here as an alternate
procedure owner.
