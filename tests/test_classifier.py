"""The classification cascade, including both Azure AI Language stages."""

from unittest.mock import MagicMock, patch

import pytest

from shared.categories import GENERAL
from shared.classifier import (classify, classify_with_custom_model,
                               classify_with_key_phrases, classify_with_keywords)
from shared.config import Settings


# ---------------------------------------------------------------------------
# Stage 3: keyword rules
# ---------------------------------------------------------------------------

def test_keyword_classifier_agrees_with_every_seed_label(seeds):
    """The offline baseline must get all 18 hand-labelled seed tickets right."""
    misses = []
    for seed in seeds:
        result = classify_with_keywords(f"{seed['title']}. {seed['description']}")
        if result["category"] != seed["expected"]:
            misses.append((seed["title"], seed["expected"], result["category"]))
    assert not misses, f"Keyword baseline regressed on: {misses}"


@pytest.mark.parametrize("text,expected", [
    ("I need to apply for a student loan", "Student Finance"),
    ("I want to renew my book loan at the library", "Library Services"),
    ("There is a late fee on my tuition invoice", "Student Finance"),
    ("I have an overdue library fine for a book", "Library Services"),
])
def test_ambiguous_terms_resolve_via_phrases(text, expected):
    """'loan' and 'fine' collide across categories; phrases break the tie."""
    assert classify_with_keywords(text)["category"] == expected


def test_unmatched_text_falls_back_to_general():
    result = classify_with_keywords("Hello, I have a question about something.")
    assert result["category"] == GENERAL
    assert result["confidence"] == 0.30
    assert result["method"] == "keyword-rules"


def test_result_shape_is_stable():
    result = classify_with_keywords("campus wifi is down")
    assert set(result) >= {"category", "confidence", "method", "evidence"}
    assert isinstance(result["evidence"], list)
    assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Stage 2: Key Phrase Extraction
# ---------------------------------------------------------------------------

def _language_settings(**overrides) -> Settings:
    settings = Settings()
    settings.language_endpoint = "https://fake.cognitiveservices.azure.com"
    settings.language_key = "fake-key"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _keyphrase_response(phrases):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "kind": "KeyPhraseExtractionResults",
        "results": {"documents": [{"id": "1", "keyPhrases": phrases, "warnings": []}], "errors": []},
    }
    return response


def test_key_phrase_stage_uses_phrases_to_pick_a_category():
    settings = _language_settings()
    with patch("shared.classifier.requests.post",
               return_value=_keyphrase_response(["tuition fee", "outstanding balance"])):
        result = classify_with_key_phrases("I have a problem with my account", settings)
    assert result["category"] == "Student Finance"
    assert result["method"] == "azure-ai-language-keyphrase"
    assert any("key phrase" in e for e in result["evidence"])


def test_key_phrase_stage_reports_general_when_nothing_maps():
    settings = _language_settings()
    with patch("shared.classifier.requests.post",
               return_value=_keyphrase_response(["graduation ceremony", "guests"])):
        result = classify_with_key_phrases("When is graduation", settings)
    assert result["category"] == GENERAL
    assert result["method"] == "azure-ai-language-keyphrase"


def test_key_phrase_stage_raises_on_empty_phrases():
    settings = _language_settings()
    with patch("shared.classifier.requests.post", return_value=_keyphrase_response([])):
        with pytest.raises(ValueError):
            classify_with_key_phrases("anything", settings)


def test_cascade_falls_back_to_keywords_when_language_call_fails():
    settings = _language_settings()
    with patch("shared.classifier.requests.post", side_effect=RuntimeError("429 quota exceeded")):
        result = classify("Cannot access campus Wi-Fi",
                          "I cannot connect to the campus Wi-Fi from my laptop.", settings)
    assert result["method"] == "keyword-rules"
    assert result["category"] == "IT Support"


def test_cascade_uses_keywords_when_nothing_is_configured(clean_env):
    result = classify("Air conditioning broken",
                      "The air conditioning in lecture hall B2 is not working.", clean_env)
    assert result["method"] == "keyword-rules"
    assert result["category"] == "Facilities"


# ---------------------------------------------------------------------------
# Stage 1: Custom Text Classification
# ---------------------------------------------------------------------------

def _ctc_settings(**overrides) -> Settings:
    return _language_settings(ctc_project="TicketTriage", ctc_deployment="production", **overrides)


def _ctc_submit_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.headers = {"operation-location": "https://fake/jobs/123?api-version=2023-04-01"}
    return response


def _ctc_poll_response(category, score, status="succeeded"):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "status": status,
        "tasks": {"items": [{"results": {"documents": [
            {"id": "1", "class": [{"category": category, "confidenceScore": score}]}
        ]}}]},
    }
    return response


def test_custom_model_stage_returns_the_predicted_class():
    settings = _ctc_settings()
    with patch("shared.classifier.requests.post", return_value=_ctc_submit_response()), \
         patch("shared.classifier.requests.get", return_value=_ctc_poll_response("Facilities", 0.93)):
        result = classify_with_custom_model("The lift is stuck", settings)
    assert result["category"] == "Facilities"
    assert result["confidence"] == 0.93
    assert result["method"] == "azure-ai-language-custom"


def test_custom_model_below_threshold_is_rejected():
    settings = _ctc_settings(ctc_min_confidence=0.8)
    with patch("shared.classifier.requests.post", return_value=_ctc_submit_response()), \
         patch("shared.classifier.requests.get", return_value=_ctc_poll_response("Facilities", 0.41)):
        with pytest.raises(ValueError, match="below threshold"):
            classify_with_custom_model("something vague", settings)


def test_custom_model_unknown_class_is_rejected():
    settings = _ctc_settings()
    with patch("shared.classifier.requests.post", return_value=_ctc_submit_response()), \
         patch("shared.classifier.requests.get", return_value=_ctc_poll_response("Parking Fines", 0.99)):
        with pytest.raises(ValueError, match="unknown class"):
            classify_with_custom_model("something", settings)


def test_cascade_skips_custom_model_and_lands_on_key_phrases():
    """A low-confidence custom model must not stop the key phrase stage running."""
    settings = _ctc_settings(ctc_min_confidence=0.9)

    def post_router(url, **kwargs):
        if "analyze-text/jobs" in url:
            return _ctc_submit_response()
        return _keyphrase_response(["library book", "overdue"])

    with patch("shared.classifier.requests.post", side_effect=post_router), \
         patch("shared.classifier.requests.get", return_value=_ctc_poll_response("Facilities", 0.20)):
        result = classify("Overdue book", "I returned my library book but still have a fine.", settings)

    assert result["method"] == "azure-ai-language-keyphrase"
    assert result["category"] == "Library Services"
