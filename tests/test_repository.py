"""In-memory repository behaviour: CRUD, filters, ordering, isolation."""

import pytest

from shared.models import build_ticket, validate_new_ticket
from shared.repository import InMemoryTicketRepository


def make(title="Wi-Fi down", description="Cannot connect to the campus Wi-Fi at all.",
         email="a@example.com", category="IT Support", status="Categorised", name="Aiman"):
    cleaned, errors = validate_new_ticket({
        "name": name, "email": email, "title": title,
        "description": description, "priority": "Medium", "category": "",
    })
    assert errors == {}
    ticket = build_ticket(cleaned, {"category": category, "confidence": 0.8,
                                    "method": "keyword-rules", "evidence": []})
    ticket["status"] = status
    return ticket


@pytest.fixture()
def repo():
    return InMemoryTicketRepository()


def test_create_then_get_round_trips(repo):
    created = repo.create(make())
    fetched = repo.get(created["id"])
    assert fetched["title"] == "Wi-Fi down"


def test_get_missing_returns_none(repo):
    assert repo.get("does-not-exist") is None


def test_replace_missing_raises(repo):
    with pytest.raises(KeyError):
        repo.replace(make())


def test_replace_updates_the_stored_copy(repo):
    created = repo.create(make())
    stored = repo.get(created["id"])
    stored["status"] = "Resolved"
    repo.replace(stored)
    assert repo.get(created["id"])["status"] == "Resolved"


def test_repository_stores_a_copy_not_a_reference(repo):
    """Mutating the object you passed in must not silently change the store."""
    ticket = make()
    repo.create(ticket)
    ticket["title"] = "Mutated after the fact"
    assert repo.get(ticket["id"])["title"] == "Wi-Fi down"


def test_filter_by_category(repo):
    repo.create(make(category="IT Support"))
    repo.create(make(category="Facilities", title="Aircon broken"))
    assert len(repo.list(category="Facilities")) == 1
    assert len(repo.list(category="IT Support")) == 1
    assert len(repo.list()) == 2


def test_filter_by_status(repo):
    repo.create(make(status="New"))
    repo.create(make(status="Resolved", title="Old one"))
    assert len(repo.list(status="Resolved")) == 1


def test_filter_by_partial_email_is_case_insensitive(repo):
    repo.create(make(email="aiman@example.com"))
    repo.create(make(email="grace.tan@example.com", title="Fees"))
    assert len(repo.list(email="AIMAN@")) == 1
    assert len(repo.list(email="example.com")) == 2


def test_free_text_search_covers_title_and_description(repo):
    repo.create(make(title="Wi-Fi down", description="Cannot connect to the campus network here."))
    repo.create(make(title="Aircon broken", description="Lecture hall is far too hot to sit in."))
    assert len(repo.list(search="aircon")) == 1
    assert len(repo.list(search="campus network")) == 1
    assert len(repo.list(search="nothing here")) == 0


def test_filters_combine_with_and_not_or(repo):
    repo.create(make(category="IT Support", status="New"))
    repo.create(make(category="IT Support", status="Resolved", title="Other"))
    assert len(repo.list(category="IT Support", status="Resolved")) == 1


def test_limit_is_honoured(repo):
    for i in range(10):
        repo.create(make(title=f"Ticket number {i}"))
    assert len(repo.list(limit=3)) == 3


def test_listing_is_newest_first(repo):
    """
    No fixture surgery here on purpose. Timestamps carry microseconds, so
    tickets created back to back really do sort correctly. An earlier version
    of this test forced a distinct createdAt, which hid the fact that
    second-resolution timestamps made ordering meaningless for bulk inserts.
    """
    created = [repo.create(make(title=f"Ticket number {i} here")) for i in range(8)]
    rows = repo.list()
    assert [r["id"] for r in rows] == [c["id"] for c in reversed(created)]


def test_timestamps_are_distinct_for_rapid_inserts(repo):
    stamps = [repo.create(make(title=f"Ticket number {i} here"))["createdAt"] for i in range(20)]
    assert len(set(stamps)) == 20


def test_stats_counts_by_status_and_category(repo):
    repo.create(make(category="IT Support", status="New"))
    repo.create(make(category="IT Support", status="Resolved", title="Two"))
    repo.create(make(category="Facilities", status="New", title="Three"))
    stats = repo.stats()
    assert stats["total"] == 3
    assert stats["byStatus"]["New"] == 2
    assert stats["byCategory"]["IT Support"] == 2
