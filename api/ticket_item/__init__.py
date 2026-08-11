"""
GET   /api/tickets/{id}   read one ticket
PATCH /api/tickets/{id}   admin updates status and/or category
"""

import logging

import azure.functions as func

from shared.config import get_settings
from shared.http import error_response, json_response, read_json, require_admin
from shared.models import apply_status_update, public_view, validate_status_update
from shared.repository import get_repository

log = logging.getLogger("tickettriage.ticket_item")


def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    repo = get_repository(settings)

    ticket_id = req.route_params.get("id", "").strip()
    if not ticket_id:
        return error_response("Ticket id is required.", 400)

    ticket = repo.get(ticket_id)
    if ticket is None:
        return error_response("Ticket not found.", 404)

    if req.method == "GET":
        return json_response(public_view(ticket))

    # ---- PATCH / PUT: admin only ------------------------------------
    denied = require_admin(req, settings)
    if denied is not None:
        return denied

    try:
        body = read_json(req)
    except ValueError as exc:
        return error_response(str(exc), 400)

    update, errors = validate_status_update(body)
    if errors:
        return error_response("Please correct the highlighted fields.", 400, errors)

    updated = apply_status_update(ticket, update)
    try:
        saved = repo.replace(updated)
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to update ticket %s", ticket_id)
        return error_response(f"Could not update the ticket: {exc}", 500)

    return json_response(saved)
