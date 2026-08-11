"""GET /api/categories - the reference lists the frontend builds its menus from."""

import azure.functions as func

from shared.categories import CATEGORIES
from shared.http import json_response
from shared.models import PRIORITIES, STATUSES


def main(req: func.HttpRequest) -> func.HttpResponse:
    return json_response({
        "categories": CATEGORIES,
        "statuses": STATUSES,
        "priorities": PRIORITIES,
    })
