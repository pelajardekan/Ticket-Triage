"""Validation, ticket assembly and status transitions."""

import pytest

from shared.models import (PRIORITIES, STATUSES, apply_status_update, build_ticket,
                           public_view, validate_new_ticket, validate_status_update)

VALID = {
    "name": "Aiman Rahman",
    "email": "Aiman@Example.com",
    "title": "Cannot access campus Wi-Fi",
    "description": "I cannot connect to the campus Wi-Fi from my laptop.",
    "priority": "Medium",
    "category": "",
}


def test_valid_payload_passes_and_normalises_email():
    cleaned, errors = validate_new_ticket(dict(VALID))
    assert errors == {}
    assert cleaned["email"] == "aiman@example.com"


@pytest.mark.parametrize("field", ["name", "email", "title", "description"])
def test_missing_required_fields_are_reported(field):
    payload = dict(VALID)
    payload[field] = "   "
    _, errors = validate_new_ticket(payload)
    assert field in errors


@pytest.mark.parametrize("email", ["not-an-email", "missing@domain", "@example.com", "a b@example.com"])
def test_bad_emails_are_rejected(email):
    payload = dict(VALID, email=email)
    _, errors = validate_new_ticket(payload)
    assert "email" in errors


def test_short_description_is_rejected():
    _, errors = validate_new_ticket(dict(VALID, description="too short"))
    assert "description" in errors


def test_over_length_fields_are_rejected():
    _, errors = validate_new_ticket(dict(VALID, title="x" * 200))
    assert "title" in errors


def test_unknown_priority_and_category_are_rejected():
    _, errors = validate_new_ticket(dict(VALID, priority="Urgent", category="Parking"))
    assert "priority" in errors and "category" in errors


def test_priority_defaults_to_medium_when_blank():
    cleaned, errors = validate_new_ticket(dict(VALID, priority=""))
    assert errors == {} and cleaned["priority"] == "Medium"


def test_build_ticket_uses_the_suggestion_when_user_left_category_blank():
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": ["wifi"]})
    assert ticket["category"] == "IT Support"
    assert ticket["categorySource"] == "auto"
    assert ticket["suggestedCategory"] == "IT Support"
    assert ticket["status"] == "Categorised"
    assert ticket["statusHistory"][0]["status"] == "Categorised"


def test_build_ticket_respects_a_user_chosen_category_but_keeps_the_suggestion():
    cleaned, _ = validate_new_ticket(dict(VALID, category="Facilities"))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    assert ticket["category"] == "Facilities"
    assert ticket["suggestedCategory"] == "IT Support"
    assert ticket["categorySource"] == "user"


def test_an_unclassifiable_ticket_arrives_as_new():
    """Both statuses in the brief must be reachable, and mean something."""
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "General Enquiry", "confidence": 0.30,
                                    "method": "keyword-rules", "evidence": []})
    assert ticket["status"] == "New"
    assert ticket["statusHistory"][0]["status"] == "New"


def test_a_status_only_update_does_not_rewrite_category_provenance():
    """The admin form posts both selects every time; that must not fake an edit."""
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    assert ticket["categorySource"] == "auto"

    update, _ = validate_status_update({"status": "In Progress", "category": "IT Support"})
    updated = apply_status_update(ticket, update)
    assert updated["status"] == "In Progress"
    assert updated["categorySource"] == "auto"


def test_timestamps_carry_sub_second_precision():
    cleaned, _ = validate_new_ticket(dict(VALID))
    classification = {"category": "IT Support", "confidence": 0.8, "method": "keyword-rules", "evidence": []}
    stamps = {build_ticket(cleaned, classification)["createdAt"] for _ in range(20)}
    assert len(stamps) == 20


def test_every_ticket_gets_a_unique_id():
    cleaned, _ = validate_new_ticket(dict(VALID))
    classification = {"category": "IT Support", "confidence": 0.8, "method": "keyword-rules", "evidence": []}
    ids = {build_ticket(cleaned, classification)["id"] for _ in range(50)}
    assert len(ids) == 50


def test_status_update_validation():
    _, errors = validate_status_update({"status": "Resolved"})
    assert errors == {}
    _, errors = validate_status_update({})
    assert "status" in errors
    _, errors = validate_status_update({"status": "Done"})
    assert "status" in errors


def test_apply_status_update_appends_history_and_touches_timestamp():
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    before = ticket["updatedAt"]
    update, _ = validate_status_update({"status": "In Progress", "note": "Assigned to network team"})
    updated = apply_status_update(ticket, update)

    assert updated["status"] == "In Progress"
    assert updated["statusHistory"][-1]["note"] == "Assigned to network team"
    assert updated["statusHistory"][-1]["by"] == "admin"
    assert updated["updatedAt"] >= before


def test_admin_category_change_is_recorded_as_admin_sourced():
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    update, _ = validate_status_update({"category": "Facilities"})
    updated = apply_status_update(ticket, update)
    assert updated["category"] == "Facilities"
    assert updated["categorySource"] == "admin"


def test_status_history_is_capped():
    cleaned, _ = validate_new_ticket(dict(VALID))
    ticket = build_ticket(cleaned, {"category": "IT Support", "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    for _ in range(60):
        update, _ = validate_status_update({"status": "In Progress"})
        ticket = apply_status_update(ticket, update)
    assert len(ticket["statusHistory"]) <= 25


def test_public_view_strips_cosmos_system_fields():
    view = public_view({"id": "1", "_rid": "x", "_etag": "y", "_ts": 1, "title": "t"})
    assert view == {"id": "1", "title": "t"}


def test_reference_lists_are_what_the_brief_specifies():
    assert STATUSES == ["New", "Categorised", "In Progress", "Resolved"]
    assert PRIORITIES == ["Low", "Medium", "High"]
