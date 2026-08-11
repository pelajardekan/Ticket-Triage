"""
GET /api/health

Reports which storage backend and which classifier stage are actually live.
Screenshot this endpoint for your free-tier evidence: it proves the app is
wired to the services you claim, and it warns when admin endpoints are open.
"""

import azure.functions as func

from shared.config import get_settings
from shared.http import json_response
from shared.models import utc_now_iso
from shared.repository import get_repository


def main(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    repo = get_repository(settings)

    warnings = []
    if repo.mode == "in-memory":
        warnings.append("Storage is in-memory: tickets are lost when the function app restarts.")
    if not settings.language_configured:
        warnings.append("Azure AI Language is not configured; classification is using keyword rules only.")
    if not settings.admin_api_key and settings.allow_anonymous_admin:
        warnings.append("Admin endpoints are unauthenticated. Set ADMIN_API_KEY before any public demo.")

    try:
        stats = repo.stats()
    except Exception as exc:  # noqa: BLE001
        stats = {"error": str(exc)}

    return json_response({
        "status": "ok",
        "time": utc_now_iso(),
        "storage": repo.mode,
        "classifierChain": settings.classifier_chain(),
        "languageConfigured": settings.language_configured,
        "customModelConfigured": settings.ctc_configured,
        "stats": stats,
        "warnings": warnings,
    })
