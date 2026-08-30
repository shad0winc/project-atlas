from fastapi.routing import APIRoute
from atlas_api.routes.v1 import admin_roles

def test_assignable_catalog_route_exists() -> None:
    routes={(r.path, tuple(sorted(r.methods or ()))) for r in admin_roles.router.routes if isinstance(r, APIRoute)}
    assert ("/admin/roles/assignable", ("GET",)) in routes
