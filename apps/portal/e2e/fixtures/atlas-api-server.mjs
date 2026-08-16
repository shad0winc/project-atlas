import http from "node:http";

const HOST = "127.0.0.1";
const PORT = 18080;

const ACCESS_TOKEN = "atlas-e2e-access-token";
const REFRESH_TOKEN = "atlas-e2e-refresh-token";
const USER_ID = `usr_${"a".repeat(32)}`;
const REQUEST_ID = `req_${"c".repeat(32)}`;
const JELLYFIN_ITEM_ID = "jf-interstellar";
const FAVORITE_ID = `fav_${"d".repeat(32)}`;

const SPORTS_PROVIDER = "thesportsdb";
const SPORTS_EVENT_ID = "atlas-sports-event-001";
const SPORTS_SUBSCRIPTION_ID = `sub_${"e".repeat(32)}`;

let favoriteCreated = false;
let sportsRequested = false;

function sendJson(response, status, payload) {
  const body = JSON.stringify(payload);

  response.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(body),
    "Cache-Control": "no-store"
  });

  response.end(body);
}

async function readRequestJsonBody(request) {
  const chunks = [];

  for await (const chunk of request) {
    chunks.push(chunk);
  }

  const body = Buffer.concat(chunks).toString("utf8");

  return body ? JSON.parse(body) : {};
}

async function readJson(request) {
  let body = "";

  for await (const chunk of request) {
    body += chunk;
  }

  return body.length === 0 ? {} : JSON.parse(body);
}

function authorized(request) {
  return request.headers.authorization === `Bearer ${ACCESS_TOKEN}`;
}

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", `http://${HOST}:${PORT}`);

    if (request.method === "GET" && url.pathname === "/_atlas_e2e/health") {
      sendJson(response, 200, { status: "ok" });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/v1/auth/login") {
      const payload = await readJson(request);

      if (payload.username !== "atlas-e2e-user" || payload.password !== "atlas-e2e-password") {
        sendJson(response, 401, {
          detail: "Username or password is incorrect."
        });
        return;
      }

      sendJson(response, 200, {
        access_token: ACCESS_TOKEN,
        refresh_token: REFRESH_TOKEN,
        token_type: "bearer"
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/auth/me") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        user_id: USER_ID,
        username: "atlas-e2e-user",
        display_name: "Atlas E2E User",
        roles: ["member"],
        provider: "e2e",
        granted_permission_patterns: [
          "media.*",
          "requests.*",
          "favorites.*",
          "sports.read",
          "sports.events.request",
          "system.health.read"
        ],
        denied_permission_patterns: []
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/media/discover") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        items: [],
        page: 1,
        total_pages: 0,
        next_page: null
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/media/search") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      if (
        url.searchParams.get("query") !== "Interstellar" ||
        url.searchParams.get("page") !== "1"
      ) {
        sendJson(response, 400, {
          detail: "Unexpected deterministic media search."
        });
        return;
      }

      sendJson(response, 200, {
        items: [
          {
            provider_media_id: "157336",
            media_type: "movie",
            title: "Interstellar",
            year: 2014,
            overview: "Space.",
            poster_path: null,
            availability: "not_tracked",
            request_eligible: true
          }
        ],
        page: 1,
        total_pages: 1,
        next_page: null
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/v1/requests") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      const payload = await readJson(request);

      const expected = {
        media_type: "movie",
        provider_media_id: "157336",
        title: "Interstellar",
        year: 2014
      };

      if (
        payload.media_type !== expected.media_type ||
        payload.provider_media_id !== expected.provider_media_id ||
        payload.title !== expected.title ||
        payload.year !== expected.year ||
        Object.prototype.hasOwnProperty.call(payload, "season_number")
      ) {
        sendJson(response, 400, {
          detail: "Unexpected deterministic media-request payload."
        });
        return;
      }

      sendJson(response, 201, {
        request_id: REQUEST_ID,
        user_id: USER_ID,
        media_type: "movie",
        provider: "jellyseerr",
        provider_media_id: "157336",
        title: "Interstellar",
        year: 2014,
        season_number: null,
        status: "pending",
        terminal: false,
        active: true,
        can_cancel: true,
        recovery_required: false,
        created_at: "2026-08-16T00:00:00Z",
        updated_at: "2026-08-16T00:00:00Z",
        available_at: null
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/media/catalog") {
      sendJson(response, 200, {
        provider: "jellyfin",
        page: 1,
        page_size: 24,
        total: 1,
        items: [
          {
            provider: "jellyfin",
            item_id: JELLYFIN_ITEM_ID,
            media_type: "movie",
            title: "Interstellar",
            year: 2014,
            library: "Movies"
          }
        ]
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/v1/favorites") {
      const authorization = request.headers.authorization ?? "";

      const body = await readRequestJsonBody(request);

      if (
        authorization !== `Bearer ${ACCESS_TOKEN}` ||
        body.provider !== "jellyfin" ||
        body.item_id !== JELLYFIN_ITEM_ID
      ) {
        sendJson(response, 400, {
          detail: "Favorite E2E contract did not match."
        });
        return;
      }

      favoriteCreated = true;

      sendJson(response, 201, {
        schema_version: 1,
        favorite_id: FAVORITE_ID,
        user_id: USER_ID,
        provider: "jellyfin",
        item_id: JELLYFIN_ITEM_ID,
        media_type: "movie",
        title: "Interstellar",
        metadata: {
          year: 2014,
          library: "Movies"
        },
        created_at: "2026-08-16T00:00:00Z",
        updated_at: "2026-08-16T00:00:00Z"
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/favorites") {
      sendJson(response, 200, {
        favorites: favoriteCreated
          ? [
              {
                schema_version: 1,
                favorite_id: FAVORITE_ID,
                user_id: USER_ID,
                provider: "jellyfin",
                item_id: JELLYFIN_ITEM_ID,
                media_type: "movie",
                title: "Interstellar",
                metadata: {
                  year: 2014,
                  library: "Movies"
                },
                created_at: "2026-08-16T00:00:00Z",
                updated_at: "2026-08-16T00:00:00Z"
              }
            ]
          : []
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/sports/events") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      if (url.searchParams.get("provider") !== SPORTS_PROVIDER) {
        sendJson(response, 400, {
          detail: "Unexpected deterministic Sports provider."
        });
        return;
      }

      sendJson(response, 200, {
        events: [
          {
            provider: SPORTS_PROVIDER,
            provider_event_id: SPORTS_EVENT_ID,
            name: "Atlas United vs Atlas City",
            sport: "Soccer",
            league: "Atlas Test League",
            start_at: "2026-08-17T20:00:00Z",
            status: "scheduled",
            requested: sportsRequested
          }
        ]
      });
      return;
    }

    if (request.method === "POST" && url.pathname === "/api/v1/sports/subscriptions") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      const payload = await readRequestJsonBody(request);

      const keys = Object.keys(payload).sort();

      const expectedKeys = ["provider", "provider_event_id"];

      if (JSON.stringify(keys) !== JSON.stringify(expectedKeys)) {
        sendJson(response, 400, {
          detail: "Sports request crossed the server-owned identity boundary."
        });
        return;
      }

      if (payload.provider !== SPORTS_PROVIDER || payload.provider_event_id !== SPORTS_EVENT_ID) {
        sendJson(response, 400, {
          detail: "Unexpected deterministic Sports event request."
        });
        return;
      }

      const created = !sportsRequested;

      sportsRequested = true;

      sendJson(response, created ? 201 : 200, {
        subscription_id: SPORTS_SUBSCRIPTION_ID,
        type: "event",
        provider: SPORTS_PROVIDER,
        provider_event_id: SPORTS_EVENT_ID,
        name: "Atlas United vs Atlas City",
        user_id: USER_ID,
        enabled: true,
        created_at: "2026-08-16T20:00:00Z"
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        count: 2,
        services: [
          {
            identifier: "jellyfin",
            name: "Jellyfin",
            provider: "docker-compose",
            enabled: true
          },
          {
            identifier: "sonarr",
            name: "Sonarr",
            provider: "docker-compose",
            enabled: true
          }
        ]
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services/health") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        health: {
          status: "degraded",
          score: 75,
          total_services: 2,
          counts: {
            healthy: 1,
            degraded: 1,
            unhealthy: 0,
            unknown: 0
          },
          services: [
            {
              service: {
                identifier: "jellyfin",
                name: "Jellyfin",
                provider: "docker-compose",
                enabled: true
              },
              health: {
                status: "healthy",
                score: 100
              },
              requires_attention: false
            },
            {
              service: {
                identifier: "sonarr",
                name: "Sonarr",
                provider: "docker-compose",
                enabled: true
              },
              health: {
                status: "degraded",
                score: 50
              },
              requires_attention: true
            }
          ],
          evaluated_at: "2026-08-16T20:30:00Z"
        }
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services/summary") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        summary: {
          provider: "docker-compose",
          compose_project: "project-atlas",
          total_services: 2,
          runtime_counts: {
            running: 2,
            stopped: 0,
            restarting: 0,
            failed: 0,
            unknown: 0
          },
          services: [
            {
              service: {
                identifier: "jellyfin",
                name: "Jellyfin",
                provider: "docker-compose",
                enabled: true
              },
              runtime: {
                state: "running",
                health: "healthy"
              },
              category: "running"
            },
            {
              service: {
                identifier: "sonarr",
                name: "Sonarr",
                provider: "docker-compose",
                enabled: true
              },
              runtime: {
                state: "running",
                health: "healthy"
              },
              category: "running"
            }
          ],
          evaluated_at: "2026-08-16T20:30:00Z"
        }
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services/updates") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        report: {
          status: "updates-available",
          provider: "docker-compose",
          total_services: 2,
          counts: {
            current: 1,
            "update-available": 1,
            "mutable-tag": 0,
            unknown: 0,
            unsupported: 0
          },
          requires_attention: true,
          attention: [
            {
              service_identifier: "sonarr",
              service_name: "Sonarr",
              status: "update-available"
            }
          ],
          updates: [
            {
              service_identifier: "jellyfin",
              service_name: "Jellyfin",
              status: "current",
              available_image: null,
              details: {
                registry_comparison: true
              }
            },
            {
              service_identifier: "sonarr",
              service_name: "Sonarr",
              status: "update-available",
              available_image: {
                repository: "lscr.io/linuxserver/sonarr",
                tag: "latest",
                digest: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
              },
              details: {
                registry_comparison: true
              }
            }
          ],
          evaluated_at: "2026-08-16T20:30:00Z"
        }
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services/history") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        report: {
          provider: "docker-compose",
          generated_at: "2026-08-16T20:35:00Z",
          total_records: 2,
          counts: {
            success: 1,
            partial: 0,
            failed: 1,
            skipped: 0,
            unknown: 0
          },
          requires_attention: true,
          latest_record: null,
          latest_success: null,
          latest_failure: null,
          records: [
            {
              service_identifier: "sonarr",
              service_name: "Sonarr",
              provider: "docker-compose",
              action: "update",
              result: "failed",
              succeeded: false,
              failed: true,
              started_at: "2026-08-16T20:32:00Z",
              completed_at: "2026-08-16T20:32:10Z",
              duration_seconds: 10,
              summary: "Update failed"
            },
            {
              service_identifier: "jellyfin",
              service_name: "Jellyfin",
              provider: "docker-compose",
              action: "restart",
              result: "success",
              succeeded: true,
              failed: false,
              started_at: "2026-08-16T20:31:00Z",
              completed_at: "2026-08-16T20:31:05Z",
              duration_seconds: 5,
              summary: "Restart completed"
            }
          ]
        }
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/api/v1/services/jellyfin") {
      if (!authorized(request)) {
        sendJson(response, 401, {
          detail: "Authentication credentials were not provided."
        });
        return;
      }

      sendJson(response, 200, {
        service: {
          identifier: "jellyfin",
          name: "Jellyfin",
          provider: "docker-compose",
          enabled: true,
          container_name: "jellyfin"
        }
      });
      return;
    }

    sendJson(response, 404, {
      detail: `Unhandled E2E fixture route: ${request.method} ${url.pathname}`
    });
  } catch (error) {
    sendJson(response, 500, {
      detail: error instanceof Error ? error.message : "Unknown E2E fixture error."
    });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Atlas deterministic E2E API fixture listening on http://${HOST}:${PORT}`);
});

function shutdown() {
  server.close(() => process.exit(0));
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
