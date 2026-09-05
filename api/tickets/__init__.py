"""
GET  /api/tickets   list tickets, with optional filters
POST /api/tickets   submit a new ticket (classified on the way in)
"""

import logging

import azure.functions as func

from shared.classifier import classify
from shared.config import get_settings
from shared.http import error_response, json_response, read_json
from shared.models import build_ticket, validate_new_ticket
from shared.repository import get_repository

log = logging.getLogger("tickettriage.tickets")


def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    repo = get_repository(settings)

    # route GET
    if req.method == "GET":
        try:
            limit = int(req.params.get("limit") or settings.max_page_size)
        except ValueError:
            return error_response("limit must be a whole number.", 400)
        limit = max(1, min(limit, settings.max_page_size))  # clamp the limit

        #  query with filters
        items = repo.list(
            category=req.params.get("category", "").strip(),
            status=req.params.get("status", "").strip(),
            email=req.params.get("email", "").strip(),
            search=req.params.get("q", "").strip(),
            limit=limit,
        )
        # return the ticket list
        return json_response({"count": len(items), "items": items})

    # ---- POST -------------------------------------------------------
    try:
        body = read_json(req)
    except ValueError as exc:
        return error_response(str(exc), 400)

    cleaned, errors = validate_new_ticket(body)
    if errors:
        return error_response("Please correct the highlighted fields.", 400, errors)

    classification = classify(cleaned["title"], cleaned["description"], settings)
    ticket = build_ticket(cleaned, classification)

    try:
        created = repo.create(ticket)
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to persist ticket")
        return error_response(f"Could not save the ticket: {exc}", 500)

    return json_response(created, 201, {"Location": f"/api/tickets/{created['id']}"})
