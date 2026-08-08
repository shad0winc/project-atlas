# Atlas Production Stack

The Atlas Production Stack defines the infrastructure required to operate
Project Atlas in a secure production environment.

## Networks

### atlas-ingress

Public-facing ingress network.

Only the reverse proxy and explicitly published web applications should attach
to this network.

### atlas-backend

Private application network.

Atlas services and trusted supporting applications use this network for
internal communication.

### atlas-management

Private administrative network.

Reserved for monitoring, observability, diagnostics, and operational tooling.

## Planned Compose Files

- `ingress.yml` — Caddy and public ingress
- `atlas.yml` — Atlas application services
- `media.yml` — Media services
- `monitoring.yml` — Monitoring and observability
- `development.yml` — Local development overrides

## Security Principles

- Only the reverse proxy publishes public HTTP and HTTPS ports.
- Administrative applications remain private.
- Secrets must never be committed to Git.
- Public services must use HTTPS.
- Backend communication should use dedicated Docker networks.
