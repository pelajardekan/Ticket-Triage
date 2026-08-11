"""
Category ontology and keyword scoring for TicketTriage.

This module is deliberately free of any Azure dependency so that it can be
unit tested offline and reused by the Azure AI Language code path.

Scoring model
-------------
Every category owns four buckets of evidence with different weights:

    phrases (4)  multi-word expressions that are near-decisive, e.g. "student loan"
    strong  (3)  terms that almost always mean this category, e.g. "tuition"
    medium  (2)  terms that usually mean this category, e.g. "invoice"
    weak    (1)  terms that only hint at it, e.g. "pay"

A ticket's score for a category is the sum of the weights of the distinct terms
that matched. The winning category is the highest scorer; if nothing matches at
all the ticket falls back to GENERAL.

Deliberate design note for students:
several terms are genuinely ambiguous across categories -- "loan" means one
thing in Student Finance and another in Library Services, and "fine" is the
same problem. Those collisions are resolved by putting the disambiguating
multi-word form in `phrases` at weight 4, so "student loan" beats a bare
"loan" hit on Library Services.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

IT_SUPPORT = "IT Support"
FACILITIES = "Facilities"
COURSE_REGISTRATION = "Course Registration"
STUDENT_FINANCE = "Student Finance"
LIBRARY_SERVICES = "Library Services"
GENERAL = "General Enquiry"

CATEGORIES: List[str] = [
    IT_SUPPORT,
    FACILITIES,
    COURSE_REGISTRATION,
    STUDENT_FINANCE,
    LIBRARY_SERVICES,
    GENERAL,
]

WEIGHT_PHRASE = 4
WEIGHT_STRONG = 3
WEIGHT_MEDIUM = 2
WEIGHT_WEAK = 1

ONTOLOGY: Dict[str, Dict[str, List[str]]] = {
    IT_SUPPORT: {
        "phrases": [
            "campus wifi", "campus wi-fi", "cannot log in", "can not log in",
            "cannot login", "reset my password", "password reset", "account locked",
            "locked out", "student portal", "two factor", "two-factor",
            "blue screen", "will not connect", "wont connect", "won't connect",
            "no internet", "network drive", "email not working",
        ],
        "strong": [
            "wifi", "wi-fi", "vpn", "mfa", "password", "login", "logon",
            "laptop", "malware", "virus", "outlook", "moodle", "blackboard",
            "canvas", "onedrive", "sharepoint", "username", "authentication",
        ],
        "medium": [
            "internet", "network", "computer", "pc", "software", "install",
            "portal", "browser", "server", "email", "account", "driver",
            "firewall", "bandwidth", "printing", "printer", "scanner", "webcam",
        ],
        "weak": [
            "connect", "connection", "screen", "crash", "crashed", "error",
            "reset", "system", "device", "app", "application", "slow", "freeze",
            "monitor", "keyboard", "mouse", "usb", "download", "upload",
        ],
    },
    FACILITIES: {
        "phrases": [
            "air conditioning", "air-conditioning", "lecture hall", "car park",
            "car-park", "water leak", "light bulb", "broken chair", "broken door",
            "toilet blocked", "blocked toilet", "not clean", "access card",
            "key card", "fire alarm", "waste bin", "vending machine",
        ],
        "strong": [
            "aircon", "hvac", "toilet", "washroom", "restroom", "janitor",
            "cleaner", "cleaning", "plumbing", "leaking", "elevator", "lift",
            "corridor", "hallway", "furniture", "pest", "cockroach", "rodent",
        ],
        "medium": [
            "classroom", "room", "building", "campus", "maintenance", "repair",
            "lighting", "light", "heating", "ventilation", "chair", "desk",
            "door", "window", "lock", "parking", "stairs", "roof", "floor",
        ],
        "weak": [
            "broken", "damaged", "dirty", "smell", "noise", "noisy", "cold",
            "hot", "temperature", "leak", "bulb", "bin", "rubbish", "trash",
            "printer", "projector",
        ],
    },
    COURSE_REGISTRATION: {
        "phrases": [
            "add drop", "add or drop", "drop a module", "drop a course",
            "course registration", "module registration", "class timetable",
            "study plan", "credit hours", "credit hour", "academic advisor",
            "change my section", "swap section", "waiting list", "wait list",
            "register for", "enrol in", "enroll in", "semester registration",
            "clash in my timetable", "timetable clash",
        ],
        "strong": [
            "registration", "register", "enrol", "enroll", "enrolment",
            "enrollment", "timetable", "prerequisite", "prerequisites",
            "elective", "syllabus", "curriculum", "withdraw", "withdrawal",
            "semester", "trimester", "transcript",
        ],
        "medium": [
            "course", "module", "subject", "class", "section", "credit",
            "schedule", "lecture", "tutorial", "programme", "program",
            "faculty", "cohort", "intake", "deferment",
        ],
        "weak": [
            "add", "drop", "swap", "change", "seat", "slot", "study", "academic",
        ],
    },
    STUDENT_FINANCE: {
        "phrases": [
            "student loan", "tuition fee", "tuition fees", "late fee",
            "late payment", "payment plan", "financial aid", "outstanding balance",
            "fee statement", "proof of payment", "double charged", "charged twice",
            "refund my", "my invoice", "bank transfer", "credit card",
            "instalment plan", "installment plan", "fee waiver",
        ],
        "strong": [
            "tuition", "invoice", "refund", "scholarship", "bursary", "ptptn",
            "billing", "bursar", "sponsorship", "sponsor", "instalment",
            "installment", "reimbursement", "receipt", "overpayment",
        ],
        "medium": [
            "fee", "fees", "payment", "balance", "charge", "charged", "deposit",
            "finance", "financial", "bill", "account statement", "waiver",
            "penalty", "transaction",
        ],
        "weak": [
            "pay", "paid", "money", "cost", "price", "amount", "bank", "card",
        ],
    },
    LIBRARY_SERVICES: {
        "phrases": [
            "library book", "library books", "book loan", "borrowed book",
            "renew my book", "renew my loan", "overdue book", "library fine",
            "library card", "study room", "discussion room", "reading room",
            "e-book", "e-books", "inter library", "interlibrary",
            "journal article", "research database", "past year paper",
            "return the book", "reserve a book",
        ],
        "strong": [
            "library", "librarian", "borrow", "borrowing", "overdue", "isbn",
            "catalogue", "catalog", "bibliography", "citation", "thesis",
            "dissertation", "ebook", "journal", "periodical", "archive",
        ],
        "medium": [
            "book", "books", "renew", "renewal", "return", "reserve",
            "reservation", "shelf", "database", "article", "publication",
            "reference", "reading",
        ],
        "weak": [
            "loan", "fine", "due", "copy", "print", "chapter", "author", "title",
        ],
    },
}

# GENERAL is the fallback and carries no keywords of its own.
ONTOLOGY[GENERAL] = {"phrases": [], "strong": [], "medium": [], "weak": []}

_BUCKET_WEIGHTS = {
    "phrases": WEIGHT_PHRASE,
    "strong": WEIGHT_STRONG,
    "medium": WEIGHT_MEDIUM,
    "weak": WEIGHT_WEAK,
}


def _compile() -> Dict[str, List[Tuple[re.Pattern, int, str]]]:
    """Pre-compile every term into a word-boundary regex, once at import time."""
    compiled: Dict[str, List[Tuple[re.Pattern, int, str]]] = {}
    for category, buckets in ONTOLOGY.items():
        entries: List[Tuple[re.Pattern, int, str]] = []
        for bucket, terms in buckets.items():
            weight = _BUCKET_WEIGHTS[bucket]
            for term in terms:
                # \b does not work next to a hyphen, so escape and pad manually.
                pattern = re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)
                entries.append((pattern, weight, term))
        compiled[category] = entries
    return compiled


_COMPILED = _compile()


def score_text(text: str) -> Dict[str, Dict[str, object]]:
    """
    Score a block of text against every category.

    Returns a mapping of category -> {"score": int, "matched": [term, ...]}.
    """
    if not text:
        return {c: {"score": 0, "matched": []} for c in CATEGORIES}

    results: Dict[str, Dict[str, object]] = {}
    for category, entries in _COMPILED.items():
        total = 0
        matched: List[str] = []
        for pattern, weight, term in entries:
            if pattern.search(text):
                total += weight
                matched.append(term)
        results[category] = {"score": total, "matched": matched}
    return results


def confidence_from_scores(scores: Dict[str, int]) -> float:
    """
    Turn raw keyword scores into a bounded, explainable confidence value.

        saturation -- how much total evidence the winner accumulated
        margin     -- how decisively the winner beat the runner-up

    confidence = 0.40 + 0.35 * saturation + 0.25 * margin, so the value always
    sits between 0.40 and 1.00 for a scored match. A ticket with no matches at
    all is handled by the caller and reported at 0.30.
    """
    ordered = sorted(scores.values(), reverse=True)
    top = ordered[0] if ordered else 0
    if top <= 0:
        return 0.30
    second = ordered[1] if len(ordered) > 1 else 0
    saturation = min(1.0, top / 6.0)
    margin = (top - second) / top
    return round(min(1.0, 0.40 + 0.35 * saturation + 0.25 * margin), 2)
