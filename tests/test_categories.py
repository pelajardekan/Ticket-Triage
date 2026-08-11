"""The ontology itself: structure, scoring, and confidence maths."""

import pytest

from shared.categories import (CATEGORIES, GENERAL, ONTOLOGY,
                               confidence_from_scores, score_text)


def test_every_category_has_an_ontology_entry():
    assert set(ONTOLOGY) == set(CATEGORIES)


def test_general_is_the_only_empty_category():
    for category, buckets in ONTOLOGY.items():
        total = sum(len(v) for v in buckets.values())
        if category == GENERAL:
            assert total == 0
        else:
            assert total > 20, f"{category} looks thin"


def test_no_duplicate_terms_within_a_category():
    for category, buckets in ONTOLOGY.items():
        terms = [t for bucket in buckets.values() for t in bucket]
        duplicates = {t for t in terms if terms.count(t) > 1}
        assert not duplicates, f"{category} repeats {duplicates}"


def test_terms_are_lowercase_and_stripped():
    for category, buckets in ONTOLOGY.items():
        for bucket, terms in buckets.items():
            for term in terms:
                assert term == term.strip().lower(), f"{category}/{bucket}: {term!r}"


def test_genuinely_ambiguous_terms_appear_in_more_than_one_category():
    """`printer` is claimed to be ambiguous in the teaching notes. Keep it true."""
    scores = score_text("the printer is broken")
    assert scores["IT Support"]["score"] > 0
    assert scores["Facilities"]["score"] > 0


def test_scoring_respects_word_boundaries():
    # "pay" must not fire on "payload"; "book" must not fire on "bookkeeping".
    assert score_text("payload")["Student Finance"]["score"] == 0
    assert score_text("bookkeeping")["Library Services"]["score"] == 0
    assert score_text("I need to pay")["Student Finance"]["score"] > 0


def test_scoring_is_case_insensitive():
    assert score_text("CAMPUS WIFI")["IT Support"]["score"] == \
           score_text("campus wifi")["IT Support"]["score"]


def test_hyphenated_terms_match():
    assert score_text("the wi-fi is down")["IT Support"]["score"] > 0


def test_empty_text_scores_zero_everywhere():
    scores = score_text("")
    assert all(v["score"] == 0 for v in scores.values())


@pytest.mark.parametrize("scores,expected_range", [
    ({"a": 0, "b": 0}, (0.30, 0.30)),
    ({"a": 12, "b": 0}, (0.99, 1.00)),   # lots of evidence, uncontested
    ({"a": 3, "b": 3}, (0.40, 0.70)),    # a genuine tie scores low
])
def test_confidence_bounds(scores, expected_range):
    value = confidence_from_scores(scores)
    assert expected_range[0] <= value <= expected_range[1]


def test_confidence_always_within_zero_and_one():
    for top in range(0, 40):
        for second in range(0, top + 1):
            value = confidence_from_scores({"a": top, "b": second})
            assert 0.0 <= value <= 1.0
