# Project Atlas Configuration

## Purpose

Project Atlas uses environment variables to keep local machine settings and secrets out of Docker Compose files.

## Files

| File | Purpose | Commit to Git? |
|---|---|---|
| `.env` | Real local settings and secrets | No |
| `.env.example` | Safe template | Yes |
| `docs/Configuration.md` | Explanation of variables | Yes |

## Important Variables

### System

| Variable | Example | Purpose |
|---|---|---|
| `TZ` | `America/New_York` | Timezone |
| `PUID` | `1000` | Container user ID |
| `PGID` | `1000` | Container group ID |
| `LXC_IP` | `192.168.1.50` | LXC IP for dashboard links |

### Storage

| Variable | Path |
|---|---|
| `DATA_DIR` | `/mnt/storage` |
| `DOWNLOADS` | `/mnt/storage/downloads` |
| `MEDIA` | `/mnt/storage/media` |
| `CONFIG` | `/mnt/storage/configs` |
| `BACKUPS` | `/mnt/storage/backups` |

### VPN

| Variable | Purpose |
|---|---|
| `WINDSCRIBE_USER` | Windscribe OpenVPN username |
| `WINDSCRIBE_PASSWORD` | Windscribe OpenVPN password |
| `VPN_REGION` | VPN region, currently Switzerland |

Never commit the real `.env` file.
