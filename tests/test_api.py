"""
End-to-end tests over the HTTP functions themselves.

These call each function's `main(req)` directly with a real
azure.functions.HttpRequest, so routing, status codes, validation and the JSON
contract are all exercised without needing the Functions host running.
"""

import json

import azure.functions as func
import pytest

from shared.config import get_settings
from shared.repository import get_repository


@pytest.fixture(autouse=True)
def fresh_store(clean_env):
    """Every test starts against an empty in-memory repository."""
    get_repository(clean_env, refresh=True)
    return clean_env


def request(method, url, body=None, params=None, route_params=None, headers=None):
    return func.HttpRequest(
        method=method,
        url=url,
        body=json.dumps(body).encode("utf-8") if body is not None else None,
        params=params or {},
        route_params=route_params or {},
        headers=headers or {},
    )


def body_of(response):
    return json.loads(response.get_body().decode("utf-8"))


VALID = {
    "name": "Aiman Rahman",
    "email": "aiman@example.com",
    "title": "Cannot access campus Wi-Fi",
    "description": "I cannot connect to the campus Wi-Fi from my laptop.",
    "priority": "Medium",
}


def create(payload=None):
    import tickets
    return tickets.main(request("POST", "/api/tickets", body=payload or dict(VALID)))


# ---------------------------------------------------------------------------
# POST /api/tickets
# ---------------------------------------------------------------------------

def test_create_returns_201_with_a_classified_ticket():
    response = create()
    assert response.status_code == 201
    ticket = body_of(response)
    assert ticket["category"] == "IT Support"
    assert ticket["status"] == "Categorised"
    assert ticket["classificationMethod"] == "keyword-rules"
    assert ticket["id"]


def test_create_sets_a_location_header():
    response = create()
    assert response.headers["Location"] == f"/api/tickets/{body_of(response)['id']}"


def test_create_rejects_an_invalid_payload_with_field_errors():
    response = create({"name": "", "email": "nope", "title": "", "description": "short"})
    assert response.status_code == 400
    payload = body_of(response)
    assert set(payload["fields"]) >= {"name", "email", "title", "description"}


def test_create_rejects_a_non_json_body():
    import tickets
    response = tickets.main(func.HttpRequest(
        method="POST", url="/api/tickets", body=b"this is not json", headers={}, params={}))
    assert response.status_code == 400


def test_create_honours_a_user_supplied_category():
    response = create(dict(VALID, category="Facilities"))
    ticket = body_of(response)
    assert ticket["category"] == "Facilities"
    assert ticket["suggestedCategory"] == "IT Support"
    assert ticket["categorySource"] == "user"


# ---------------------------------------------------------------------------
# GET /api/tickets
# ---------------------------------------------------------------------------

def test_list_is_empty_to_begin_with():
    import tickets
    response = tickets.main(request("GET", "/api/tickets"))
    assert response.status_code == 200
    assert body_of(response) == {"count": 0, "items": []}


def test_list_returns_created_tickets():
    import tickets
    create()
    create(dict(VALID, title="Aircon broken in B2",
                description="The air conditioning in lecture hall B2 is not working."))
    payload = body_of(tickets.main(request("GET", "/api/tickets")))
    assert payload["count"] == 2


def test_list_filters_by_category():
    import tickets
    create()
    create(dict(VALID, title="Aircon broken in B2",
                description="The air conditioning in lecture hall B2 is not working."))
    payload = body_of(tickets.main(
        request("GET", "/api/tickets", params={"category": "Facilities"})))
    assert payload["count"] == 1
    assert payload["items"][0]["category"] == "Facilities"


def test_list_filters_by_search_text():
    import tickets
    create()
    payload = body_of(tickets.main(request("GET", "/api/tickets", params={"q": "wi-fi"})))
    assert payload["count"] == 1
    payload = body_of(tickets.main(request("GET", "/api/tickets", params={"q": "zzzz"})))
    assert payload["count"] == 0


def test_list_rejects_a_non_numeric_limit():
    import tickets
    response = tickets.main(request("GET", "/api/tickets", params={"limit": "many"}))
    assert response.status_code == 400


def test_list_clamps_an_oversized_limit():
    import tickets
    create()
    response = tickets.main(request("GET", "/api/tickets", params={"limit": "100000"}))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET / PATCH /api/tickets/{id}
# ---------------------------------------------------------------------------

def test_get_one_ticket():
    import ticket_item
    created = body_of(create())
    response = ticket_item.main(request("GET", "/api/tickets/x", route_params={"id": created["id"]}))
    assert response.status_code == 200
    assert body_of(response)["id"] == created["id"]


def test_get_unknown_ticket_is_404():
    import ticket_item
    response = ticket_item.main(request("GET", "/api/tickets/x", route_params={"id": "nope"}))
    assert response.status_code == 404


def test_patch_updates_status_and_records_history():
    import ticket_item
    created = body_of(create())
    response = ticket_item.main(request(
        "PATCH", "/api/tickets/x", body={"status": "In Progress", "note": "Network team notified"},
        route_params={"id": created["id"]}))
    assert response.status_code == 200
    updated = body_of(response)
    assert updated["status"] == "In Progress"
    assert updated["statusHistory"][-1]["note"] == "Network team notified"


def test_patch_can_recategorise():
    import ticket_item
    created = body_of(create())
    updated = body_of(ticket_item.main(request(
        "PATCH", "/api/tickets/x", body={"category": "Facilities"},
        route_params={"id": created["id"]})))
    assert updated["category"] == "Facilities"
    assert updated["categorySource"] == "admin"


def test_patch_rejects_an_unknown_status():
    import ticket_item
    created = body_of(create())
    response = ticket_item.main(request(
        "PATCH", "/api/tickets/x", body={"status": "Finished"},
        route_params={"id": created["id"]}))
    assert response.status_code == 400


def test_patch_with_an_empty_body_is_rejected():
    import ticket_item
    created = body_of(create())
    response = ticket_item.main(request(
        "PATCH", "/api/tickets/x", body={}, route_params={"id": created["id"]}))
    assert response.status_code == 400


def test_the_update_actually_persists():
    import ticket_item
    created = body_of(create())
    ticket_item.main(request("PATCH", "/api/tickets/x", body={"status": "Resolved"},
                             route_params={"id": created["id"]}))
    reread = body_of(ticket_item.main(
        request("GET", "/api/tickets/x", route_params={"id": created["id"]})))
    assert reread["status"] == "Resolved"


# ---------------------------------------------------------------------------
# Admin authorisation
# ---------------------------------------------------------------------------

def test_patch_requires_the_admin_key_when_one_is_configured(monkeypatch):
    import ticket_item
    created = body_of(create())

    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    settings = get_settings(refresh=True)
    get_repository(settings)  # keep the same in-memory store

    denied = ticket_item.main(request("PATCH", "/api/tickets/x", body={"status": "Resolved"},
                                      route_params={"id": created["id"]}))
    assert denied.status_code == 401

    allowed = ticket_item.main(request("PATCH", "/api/tickets/x", body={"status": "Resolved"},
                                       route_params={"id": created["id"]},
                                       headers={"x-admin-key": "s3cret"}))
    assert allowed.status_code == 200

    get_settings(refresh=True)


def test_admin_verification_requires_the_configured_key(monkeypatch):
    import admin_verify

    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    get_settings(refresh=True)

    denied = admin_verify.main(request("GET", "/api/admin/verify"))
    assert denied.status_code == 401

    allowed = admin_verify.main(request(
        "GET",
        "/api/admin/verify",
        headers={"x-admin-key": "s3cret"},
    ))
    assert allowed.status_code == 200
    assert body_of(allowed)["authorised"] is True

    get_settings(refresh=True)


def test_reading_a_ticket_never_requires_the_admin_key(monkeypatch):
    import ticket_item
    created = body_of(create())
    monkeypatch.setenv("ADMIN_API_KEY", "s3cret")
    get_settings(refresh=True)
    response = ticket_item.main(request("GET", "/api/tickets/x", route_params={"id": created["id"]}))
    assert response.status_code == 200
    get_settings(refresh=True)


# ---------------------------------------------------------------------------
# Reference and health endpoints
# ---------------------------------------------------------------------------

def test_categories_endpoint_matches_the_brief():
    import categories as categories_fn
    payload = body_of(categories_fn.main(request("GET", "/api/categories")))
    assert payload["categories"] == [
        "IT Support", "Facilities", "Course Registration",
        "Student Finance", "Library Services", "General Enquiry",
    ]
    assert payload["statuses"] == ["New", "Categorised", "In Progress", "Resolved"]


def test_health_reports_the_active_backends_and_warnings():
    import health
    payload = body_of(health.main(request("GET", "/api/health")))
    assert payload["status"] == "ok"
    assert payload["storage"] == "in-memory"
    assert payload["classifierChain"] == ["keyword-rules"]
    assert payload["languageConfigured"] is False
    assert any("in-memory" in w for w in payload["warnings"])
    assert any("Admin endpoints are unauthenticated" in w for w in payload["warnings"])


def test_health_counts_tickets():
    import health
    create()
    payload = body_of(health.main(request("GET", "/api/health")))
    assert payload["stats"]["total"] == 1
