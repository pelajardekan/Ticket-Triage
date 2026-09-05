"""
Ticket persistence.

Two interchangeable implementations sit behind one interface:

    CosmosTicketRepository   Azure Cosmos DB for NoSQL, free tier.
    InMemoryTicketRepository Process memory. Used automatically whenever
                             COSMOS_ENDPOINT / COSMOS_KEY are not set, so the
                             whole app runs and tests offline with no Azure
                             account and no cost.

Partition key choice
--------------------
The container is partitioned on `/id`.

That means every ticket is its own logical partition, so point reads are
single-partition and cheap, and -- importantly for this app -- an admin can
change a ticket's category without hitting the "you cannot change a document's
partition key value" wall. Listing tickets becomes a cross-partition query,
which at classroom scale (hundreds of tickets) costs single-digit RUs.

`/category` is the textbook alternative and makes category filters
single-partition, but it locks the category field permanently. That trade-off
is worth explaining in your presentation.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

from .config import Settings, get_settings
from .models import public_view

log = logging.getLogger("tickettriage.repository")

def _aggregate_users(rows: List[Dict[str, Any]], search: str = "",
                     limit: int = 100) -> List[Dict[str, Any]]:
    """Collapse ticket requesters into one row per email address."""
    by_email: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        email = str(row.get("email") or "").strip().lower()
        if not email:
            continue
        created = str(row.get("createdAt") or "")
        name = str(row.get("name") or "").strip()
        existing = by_email.get(email)
        if existing is None:
            by_email[email] = {
                "email": email,
                "name": name,
                "ticketCount": 1,
                "lastSubmittedAt": created,
            }
            continue
        existing["ticketCount"] += 1
        if created > existing["lastSubmittedAt"]:
            existing["lastSubmittedAt"] = created
            if name:
                existing["name"] = name

    users = list(by_email.values())
    needle = search.strip().lower()
    if needle:
        users = [
            user for user in users
            if needle in user["email"] or needle in user["name"].lower()
        ]
    users.sort(
        key=lambda user: (user.get("lastSubmittedAt") or "", user.get("email") or ""),
        reverse=True,
    )
    return users[:limit]


class TicketRepository:
    """Interface every storage backend implements."""

    mode = "abstract"

    def create(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def get(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def replace(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def list(self, category: str = "", status: str = "", email: str = "",
             search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def stats(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    def list_users(self, search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        raise NotImplementedError



# ---------------------------------------------------------------------------
# In-memory
# ---------------------------------------------------------------------------

class InMemoryTicketRepository(TicketRepository):
    mode = "in-memory"

    def __init__(self) -> None:
        self._items: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._items[ticket["id"]] = dict(ticket)
        return public_view(ticket)

    def get(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            found = self._items.get(ticket_id)
            return dict(found) if found else None

    def replace(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if ticket["id"] not in self._items:
                raise KeyError(ticket["id"])
            self._items[ticket["id"]] = dict(ticket)
        return public_view(ticket)

    def list(self, category: str = "", status: str = "", email: str = "",
             search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [dict(v) for v in self._items.values()]

        needle = search.strip().lower()
        mail = email.strip().lower()

        def keep(row: Dict[str, Any]) -> bool:
            if category and row.get("category") != category:
                return False
            if status and row.get("status") != status:
                return False
            if mail and mail not in str(row.get("email", "")).lower():
                return False
            if needle:
                haystack = f"{row.get('title','')} {row.get('description','')}".lower()
                if needle not in haystack:
                    return False
            return True

        rows = [r for r in rows if keep(r)]
        rows.sort(key=lambda r: (r.get("createdAt", ""), r.get("id", "")), reverse=True)
        return [public_view(r) for r in rows[:limit]]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            rows = list(self._items.values())
        by_status: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        for row in rows:
            by_status[row.get("status", "?")] = by_status.get(row.get("status", "?"), 0) + 1
            by_category[row.get("category", "?")] = by_category.get(row.get("category", "?"), 0) + 1
        return {"total": len(rows), "byStatus": by_status, "byCategory": by_category}

    def list_users(self, search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = [
                {
                    "email": row.get("email"),
                    "name": row.get("name"),
                    "createdAt": row.get("createdAt"),
                }
                for row in self._items.values()
            ]
        return _aggregate_users(rows, search=search, limit=limit)




# ---------------------------------------------------------------------------
# Cosmos DB
# ---------------------------------------------------------------------------

class CosmosTicketRepository(TicketRepository):
    mode = "cosmos"

    def __init__(self, settings: Settings) -> None:
        from azure.cosmos import CosmosClient, PartitionKey  # imported lazily

        self._settings = settings
        self._client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        database = self._client.create_database_if_not_exists(id=settings.cosmos_database)
        self._container = database.create_container_if_not_exists(
            id=settings.cosmos_container,
            partition_key=PartitionKey(path="/id"),
        )

    def create(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        created = self._container.create_item(body=ticket)
        return public_view(created)

    def get(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        from azure.cosmos import exceptions

        try:
            return self._container.read_item(item=ticket_id, partition_key=ticket_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def replace(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        updated = self._container.replace_item(item=ticket["id"], body=ticket)
        return public_view(updated)

    def list(self, category: str = "", status: str = "", email: str = "",
             search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        # Parameterised query: never string-concatenate user input into SQL.
        clauses: List[str] = []
        params: List[Dict[str, Any]] = []

        if category:
            clauses.append("c.category = @category")
            params.append({"name": "@category", "value": category})
        if status:
            clauses.append("c.status = @status")
            params.append({"name": "@status", "value": status})
        if email:
            clauses.append("CONTAINS(LOWER(c.email), @email)")
            params.append({"name": "@email", "value": email.strip().lower()})
        if search:
            clauses.append("(CONTAINS(LOWER(c.title), @q) OR CONTAINS(LOWER(c.description), @q))")
            params.append({"name": "@q", "value": search.strip().lower()})

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM c{where} ORDER BY c.createdAt DESC OFFSET 0 LIMIT @limit"
        # createdAt carries microseconds, so ties (and therefore unstable
        # ordering) are effectively impossible.
        params.append({"name": "@limit", "value": int(limit)})

        rows = self._container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        )
        return [public_view(r) for r in rows]

    def stats(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        total = 0
        for row in self._container.query_items(
            query="SELECT c.status, c.category FROM c",
            enable_cross_partition_query=True,
        ):
            total += 1
            by_status[row.get("status", "?")] = by_status.get(row.get("status", "?"), 0) + 1
            by_category[row.get("category", "?")] = by_category.get(row.get("category", "?"), 0) + 1
        return {"total": total, "byStatus": by_status, "byCategory": by_category}

    def list_users(self, search: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        rows = list(self._container.query_items(
            query="SELECT c.email, c.name, c.createdAt FROM c",
            enable_cross_partition_query=True,
        ))
        return _aggregate_users(rows, search=search, limit=limit)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_repository: Optional[TicketRepository] = None
_repo_lock = threading.Lock()


def get_repository(settings: Optional[Settings] = None, refresh: bool = False) -> TicketRepository:
    """
    Return the shared repository, creating it on first use.

    Falling back to in-memory rather than crashing is intentional: a
    misconfigured Cosmos connection should degrade the demo, not kill it. The
    /api/health endpoint reports which backend is actually live.
    """
    global _repository
    settings = settings or get_settings()

    with _repo_lock:
        if _repository is not None and not refresh:
            return _repository

        if settings.cosmos_configured:
            try:
                _repository = CosmosTicketRepository(settings)
                log.info("Using Cosmos DB repository (%s)", settings.cosmos_database)
            except Exception as exc:  # noqa: BLE001
                log.error("Cosmos DB unavailable, falling back to in-memory: %s", exc)
                _repository = InMemoryTicketRepository()
        else:
            log.info("Cosmos DB not configured, using in-memory repository.")
            _repository = InMemoryTicketRepository()

        return _repository
