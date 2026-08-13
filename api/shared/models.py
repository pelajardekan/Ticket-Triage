"""Ticket data model, validation and serialisation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .categories import CATEGORIES, GENERAL

STATUSES: List[str] = ["New", "Categorised", "In Progress", "Resolved"]
PRIORITIES: List[str] = ["Low", "Medium", "High"]

# Deliberately permissive: good enough to catch typos, not a spec-complete
# RFC 5322 implementation. Students should not hand-roll stricter than this.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

MAX_NAME = 100
MAX_EMAIL = 200
MAX_TITLE = 150
MAX_DESCRIPTION = 4000

# Global tracker to guarantee distinct timestamps during rapid loop inserts on Windows
_last_dt: Optional[datetime] = None


# Microsecond resolution matters. At second resolution a seeding script that
# posts eighteen tickets in a second gives them all the same createdAt, and
# "newest first" silently stops meaning anything.
def utc_now_iso() -> str:
    global _last_dt
    now = datetime.now(timezone.utc)
    if _last_dt is not None and now <= _last_dt:
        now = _last_dt + timedelta(microseconds=1)
    _last_dt = now
    return now.isoformat(timespec="microseconds").replace("+00:00", "Z")


class ValidationError(ValueError):
    """Raised when a submitted payload fails validation."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{k}: {v}" for k, v in errors.items()))


def _text(payload: Dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None:
        return ""
    return str(value).strip()


def validate_new_ticket(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Validate an incoming ticket submission.

    Returns (cleaned, errors). `cleaned` is only meaningful when errors is empty.
    """
    errors: Dict[str, str] = {}

    name = _text(payload, "name")
    email = _text(payload, "email")
    title = _text(payload, "title")
    description = _text(payload, "description")
    priority = _text(payload, "priority") or "Medium"
    category = _text(payload, "category")

    if not name:
        errors["name"] = "Name is required."
    elif len(name) > MAX_NAME:
        errors["name"] = f"Name must be {MAX_NAME} characters or fewer."

    if not email:
        errors["email"] = "Email is required."
    elif len(email) > MAX_EMAIL:
        errors["email"] = f"Email must be {MAX_EMAIL} characters or fewer."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Email format looks invalid."

    if not title:
        errors["title"] = "Title is required."
    elif len(title) > MAX_TITLE:
        errors["title"] = f"Title must be {MAX_TITLE} characters or fewer."

    if not description:
        errors["description"] = "Description is required."
    elif len(description) < 10:
        errors["description"] = "Please describe the issue in at least 10 characters."
    elif len(description) > MAX_DESCRIPTION:
        errors["description"] = f"Description must be {MAX_DESCRIPTION} characters or fewer."

    if priority not in PRIORITIES:
        errors["priority"] = f"Priority must be one of: {', '.join(PRIORITIES)}."

    if category and category not in CATEGORIES:
        errors["category"] = f"Category must be one of: {', '.join(CATEGORIES)}."

    cleaned = {
        "name": name,
        "email": email.lower(),
        "title": title,
        "description": description,
        "priority": priority,
        "category": category,
    }
    return cleaned, errors


def build_ticket(cleaned: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the document that gets persisted."""
    user_supplied = bool(cleaned.get("category"))
    final_category = cleaned["category"] if user_supplied else classification.get("category", GENERAL)
    now = utc_now_iso()

    # Both statuses in the brief must be reachable and mean something.
    # A ticket the classifier actually scored arrives Categorised. A ticket that
    # matched nothing falls back to General Enquiry at 0.30 confidence, and that
    # arrives as New: it still needs a human to triage it.
    scored = float(classification.get("confidence", 0.0)) >= 0.40
    initial_status = "Categorised" if (user_supplied or scored) else "New"

    return {
        "id": str(uuid.uuid4()),
        "name": cleaned["name"],
        "email": cleaned["email"],
        "title": cleaned["title"],
        "description": cleaned["description"],
        "priority": cleaned["priority"],
        "category": final_category,
        "suggestedCategory": classification.get("category", GENERAL),
        "categorySource": "user" if user_supplied else "auto",
        "classificationMethod": classification.get("method", "keyword-rules"),
        "classificationConfidence": classification.get("confidence", 0.0),
        "classificationEvidence": classification.get("evidence", [])[:12],
        "status": initial_status,
        "createdAt": now,
        "updatedAt": now,
        "statusHistory": [{"status": initial_status, "at": now, "by": "system"}],
    }


def validate_status_update(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    errors: Dict[str, str] = {}
    status = _text(payload, "status")
    category = _text(payload, "category")
    note = _text(payload, "note")

    if not status and not category:
        errors["status"] = "Provide a status, a category, or both."
    if status and status not in STATUSES:
        errors["status"] = f"Status must be one of: {', '.join(STATUSES)}."
    if category and category not in CATEGORIES:
        errors["category"] = f"Category must be one of: {', '.join(CATEGORIES)}."
    if len(note) > 500:
        errors["note"] = "Note must be 500 characters or fewer."

    return {"status": status, "category": category, "note": note}, errors


def apply_status_update(ticket: Dict[str, Any], update: Dict[str, Any], actor: str = "admin") -> Dict[str, Any]:
    now = utc_now_iso()
    if update.get("status"):
        ticket["status"] = update["status"]
        history = list(ticket.get("statusHistory") or [])
        entry: Dict[str, Any] = {"status": update["status"], "at": now, "by": actor}
        if update.get("note"):
            entry["note"] = update["note"]
        history.append(entry)
        ticket["statusHistory"] = history[-25:]
    # Only claim an admin set the category if the value actually changed. The
    # admin form posts both selects on every save, so a plain status change
    # would otherwise erase the record of who chose the category.
    new_category = update.get("category")
    if new_category and new_category != ticket.get("category"):
        ticket["category"] = new_category
        ticket["categorySource"] = "admin"
    ticket["updatedAt"] = now
    return ticket


def public_view(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Cosmos DB system fields (_rid, _etag, _ts ...) before returning."""
    return {k: v for k, v in ticket.items() if not k.startswith("_")}
