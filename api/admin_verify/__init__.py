"""GET /api/admin/verify - validate access to the admin interface."""

import azure.functions as func

from shared.config import get_settings
from shared.http import json_response, require_admin


def main(req: func.HttpRequest) -> func.HttpResponse:
    denied = require_admin(req, get_settings())
    if denied is not None:
        return denied
    return json_response({"authorised": True})
