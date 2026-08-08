# Apply Tools

This directory is reserved for active, reviewable engineering-sprint helpers.

An apply tool should:

- verify the repository and expected branch;
- validate required source state before editing;
- create rollback copies when changing existing files;
- prefer guarded heredocs or deterministic structural edits;
- select the repository virtual environment;
- run focused validation;
- avoid commits and pushes;
- avoid Docker or platform mutations unless the sprint explicitly requires them.

One-off apply tools should be removed or archived after their feature is
validated and committed.
