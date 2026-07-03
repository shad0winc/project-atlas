# Maintainerr 72-hour cleanup

Create a rule:

```text
Watched = true
AND
Last watched older than 72 hours
```

Actions:

```text
Delete files
Unmonitor in Sonarr/Radarr
Remove request from Jellyseerr when available
```

Recommended:

```text
Dry run first
Exclude favorites
Exclude items added less than 7 days ago
Run daily
```
