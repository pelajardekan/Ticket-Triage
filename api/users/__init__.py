"""
GET /api/users   admin lists unique requesters (one row per email)
"""

import azure.functions as func

from shared.config import get_settings
from shared.http import error_response, json_response, require_admin
from shared.repository import get_repository


def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    denied = require_admin(req, settings)
    if denied:
        return denied

    if req.method != "GET":
        return error_response("Method not allowed.", 405)

    try:
        limit = int(req.params.get("limit") or settings.max_page_size)
    except ValueError:
        return error_response("limit must be a whole number.", 400)
    limit = max(1, min(limit, settings.max_page_size))

    repo = get_repository(settings)
    items = repo.list_users(
        search=req.params.get("q", "").strip(),
        limit=limit,
    )
    return json_response({"count": len(items), "items": items})
