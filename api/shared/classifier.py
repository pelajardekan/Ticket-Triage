"""
Ticket category classification.

The classifier is a three-stage cascade. Each stage is tried in order and the
first one that produces a usable answer wins. Any stage may fail (missing
configuration, network error, exhausted free-tier quota) without breaking
ticket submission -- the cascade simply falls through to the next stage.

    1. azure-ai-language-custom     Custom Text Classification, a model you
                                    trained on your own labelled tickets.
                                    Highest quality, needs training. Optional.

    2. azure-ai-language-keyphrase  Prebuilt Key Phrase Extraction. No training
                                    at all: the service pulls the salient
                                    phrases out of the ticket, and those phrases
                                    are scored against the category ontology
                                    with extra weight. This is the default
                                    Azure AI path.

    3. keyword-rules                Pure offline scoring over the ontology.
                                    Always available, costs nothing, and is the
                                    reason the app still works on a plane.

Every result records which stage produced it, so the admin UI (and your demo)
can show exactly how each ticket was categorised.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from .categories import CATEGORIES, GENERAL, confidence_from_scores, score_text
from .config import Settings, get_settings

log = logging.getLogger("tickettriage.classifier")

# Key phrases are a stronger signal than raw prose, so their ontology score is
# multiplied by this factor before being added to the raw-text score.
KEYPHRASE_WEIGHT = 1.5


def _result(category: str, confidence: float, method: str,
            evidence: Optional[List[str]] = None, note: str = "") -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "category": category,
        "confidence": round(float(confidence), 2),
        "method": method,
        "evidence": evidence or [],
    }
    if note:
        payload["note"] = note
    return payload


# ---------------------------------------------------------------------------
# Stage 3: keyword rules (always available)
# ---------------------------------------------------------------------------

def classify_with_keywords(text: str) -> Dict[str, Any]:
    scored = score_text(text)
    plain = {c: int(v["score"]) for c, v in scored.items()}
    best = max(plain, key=lambda c: plain[c])

    if plain[best] == 0:
        return _result(GENERAL, 0.30, "keyword-rules", [],
                       "No category keywords matched; defaulted to General Enquiry.")

    return _result(best, confidence_from_scores(plain), "keyword-rules",
                   list(scored[best]["matched"]))


# ---------------------------------------------------------------------------
# Stage 2: Azure AI Language, prebuilt Key Phrase Extraction
# ---------------------------------------------------------------------------

def extract_key_phrases(text: str, settings: Settings) -> List[str]:
    """Call the prebuilt Key Phrase Extraction endpoint. Raises on failure."""
    url = f"{settings.language_endpoint}/language/:analyze-text"
    response = requests.post(
        url,
        params={"api-version": settings.language_api_version},
        headers={
            "Ocp-Apim-Subscription-Key": settings.language_key,
            "Content-Type": "application/json",
        },
        json={
            "kind": "KeyPhraseExtraction",
            "parameters": {"modelVersion": "latest"},
            "analysisInput": {
                "documents": [{"id": "1", "language": "en", "text": text[:5000]}]
            },
        },
        timeout=settings.language_timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    documents = body.get("results", {}).get("documents", [])
    if not documents:
        return []
    return list(documents[0].get("keyPhrases", []))


def classify_with_key_phrases(text: str, settings: Settings) -> Dict[str, Any]:
    phrases = extract_key_phrases(text, settings)
    if not phrases:
        raise ValueError("Key Phrase Extraction returned no phrases.")

    text_scores = score_text(text)
    phrase_scores = score_text(" . ".join(phrases))

    combined: Dict[str, float] = {}
    evidence: Dict[str, List[str]] = {}
    for category in CATEGORIES:
        combined[category] = (
            float(text_scores[category]["score"])
            + KEYPHRASE_WEIGHT * float(phrase_scores[category]["score"])
        )
        merged = list(dict.fromkeys(
            list(text_scores[category]["matched"]) + list(phrase_scores[category]["matched"])
        ))
        evidence[category] = merged

    best = max(combined, key=lambda c: combined[c])
    if combined[best] == 0:
        # The service worked, it just found nothing we recognise.
        return _result(GENERAL, 0.35, "azure-ai-language-keyphrase",
                       [f"key phrase: {p}" for p in phrases[:6]],
                       "Key phrases extracted but none mapped to a known category.")

    rounded = {c: int(round(v)) for c, v in combined.items()}
    confidence = confidence_from_scores(rounded)
    detail = [f"key phrase: {p}" for p in phrases[:6]] + evidence[best][:6]
    return _result(best, confidence, "azure-ai-language-keyphrase", detail)


# ---------------------------------------------------------------------------
# Stage 1: Azure AI Language, Custom Text Classification (optional)
# ---------------------------------------------------------------------------

def classify_with_custom_model(text: str, settings: Settings) -> Dict[str, Any]:
    """
    Submit a CustomSingleLabelClassification job and poll for the result.

    This is an asynchronous API: the POST returns 202 plus an
    `operation-location` header that you poll until status is `succeeded`.
    """
    submit_url = f"{settings.language_endpoint}/language/analyze-text/jobs"
    submit = requests.post(
        submit_url,
        params={"api-version": settings.ctc_api_version},
        headers={
            "Ocp-Apim-Subscription-Key": settings.language_key,
            "Content-Type": "application/json",
        },
        json={
            "displayName": "TicketTriage classification",
            "analysisInput": {
                "documents": [{"id": "1", "language": "en", "text": text[:5000]}]
            },
            "tasks": [{
                "kind": "CustomSingleLabelClassification",
                "taskName": "TicketCategory",
                "parameters": {
                    "projectName": settings.ctc_project,
                    "deploymentName": settings.ctc_deployment,
                },
            }],
        },
        timeout=settings.language_timeout_seconds,
    )
    submit.raise_for_status()

    operation_url = submit.headers.get("operation-location")
    if not operation_url:
        raise ValueError("Custom classification job did not return an operation-location header.")

    deadline = time.time() + max(settings.language_timeout_seconds, 10)
    payload: Dict[str, Any] = {}
    while time.time() < deadline:
        poll = requests.get(
            operation_url,
            headers={"Ocp-Apim-Subscription-Key": settings.language_key},
            timeout=settings.language_timeout_seconds,
        )
        poll.raise_for_status()
        payload = poll.json()
        state = str(payload.get("status", "")).lower()
        if state == "succeeded":
            break
        if state in {"failed", "cancelled"}:
            raise ValueError(f"Custom classification job {state}: {payload.get('errors')}")
        time.sleep(1.0)
    else:
        raise TimeoutError("Custom classification job did not finish in time.")

    items = payload.get("tasks", {}).get("items", [])
    if not items:
        raise ValueError("Custom classification job returned no task items.")
    documents = items[0].get("results", {}).get("documents", [])
    if not documents:
        raise ValueError("Custom classification job returned no documents.")
    classes = documents[0].get("class", [])
    if not classes:
        raise ValueError("Custom classification job returned no class prediction.")

    top = max(classes, key=lambda c: c.get("confidenceScore", 0.0))
    label = top.get("category", GENERAL)
    score = float(top.get("confidenceScore", 0.0))

    if label not in CATEGORIES:
        raise ValueError(f"Model returned unknown class '{label}'.")
    if score < settings.ctc_min_confidence:
        raise ValueError(f"Model confidence {score:.2f} below threshold {settings.ctc_min_confidence:.2f}.")

    return _result(label, score, "azure-ai-language-custom",
                   [f"model class: {label} ({score:.2f})"])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def classify(title: str, description: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    settings = settings or get_settings()
    text = f"{title}. {description}".strip()

    if settings.ctc_configured:
        try:
            return classify_with_custom_model(text, settings)
        except Exception as exc:  # noqa: BLE001 - never block ticket creation
            log.warning("Custom Text Classification unavailable, falling through: %s", exc)

    if settings.language_configured:
        try:
            return classify_with_key_phrases(text, settings)
        except Exception as exc:  # noqa: BLE001
            log.warning("Key Phrase Extraction unavailable, falling through: %s", exc)

    return classify_with_keywords(text)
