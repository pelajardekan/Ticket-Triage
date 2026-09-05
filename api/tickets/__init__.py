"""
GET  /api/tickets   list tickets, with optional filters
POST /api/tickets   submit a new ticket (classified on the way in)
"""

import logging

import azure.functions as func
from opentelemetry.trace import SpanKind, Status, StatusCode

from shared.classifier import classify
from shared.config import get_settings
from shared.http import error_response, json_response, read_json
from shared.models import build_ticket, validate_new_ticket
from shared.repository import get_repository
from shared.telemetry import configure_telemetry, get_tracer

log = logging.getLogger("tickettriage.tickets")


def main(req: func.HttpRequest) -> func.HttpResponse:
    configure_telemetry()
    settings = get_settings()
    repo = get_repository(settings)

    if req.method == "GET":
        try:
            limit = int(req.params.get("limit") or settings.max_page_size)
        except ValueError:
            return error_response("limit must be a whole number.", 400)
        limit = max(1, min(limit, settings.max_page_size))

        items = repo.list(
            category=req.params.get("category", "").strip(),
            status=req.params.get("status", "").strip(),
            email=req.params.get("email", "").strip(),
            search=req.params.get("q", "").strip(),
            limit=limit,
        )
        return json_response({"count": len(items), "items": items})

    # ---- POST -------------------------------------------------------
    try:
        body = read_json(req)
    except ValueError as exc:
        return error_response(str(exc), 400)

    cleaned, errors = validate_new_ticket(body)
    if errors:
        return error_response("Please correct the highlighted fields.", 400, errors)

    tracer = get_tracer()
    with tracer.start_as_current_span("classify-ticket", kind=SpanKind.CLIENT) as span:
        classification = classify(cleaned["title"], cleaned["description"], settings)
        span.set_attribute("operation.stage", "classification")
        span.set_attribute("ticket.category", classification["category"])
        span.set_attribute("classification.method", classification["method"])
        span.set_attribute("classification.confidence", classification["confidence"])
        span.set_status(Status(StatusCode.OK))

    ticket = build_ticket(cleaned, classification)

    try:
        with tracer.start_as_current_span("save-ticket", kind=SpanKind.CLIENT) as span:
            span.set_attribute("operation.stage", "storage")
            span.set_attribute("storage.type", repo.mode)
            span.set_attribute("ticket.id", ticket["id"])
            created = repo.create(ticket)
            span.set_status(Status(StatusCode.OK))
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to persist ticket")
        return error_response(f"Could not save the ticket: {exc}", 500)

    return json_response(created, 201, {"Location": f"/api/tickets/{created['id']}"})
