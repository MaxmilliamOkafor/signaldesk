"""Citation validator: real spans pass, fabricated spans are flagged."""

from app.schemas import Extraction
from app.validate import span_in_source, validate_citation


def test_real_span_passes():
    src = "Apple beats earnings expectations as iPhone sales surge"
    assert span_in_source("beats earnings", src)


def test_fabricated_span_flagged():
    src = "Apple beats earnings expectations"
    assert not span_in_source("missed badly", src)


def test_whitespace_and_case_normalised():
    src = "Tesla   shares  PLUNGE after delivery miss"
    assert span_in_source("shares plunge", src)


def test_validate_sets_flag():
    good = Extraction(
        id="1",
        tickers=["AAPL"],
        sentiment=0.5,
        rationale="r",
        source_span="beats",
        source_text="Apple beats today",
    )
    bad = Extraction(
        id="2",
        tickers=["AAPL"],
        sentiment=0.5,
        rationale="r",
        source_span="collapses",
        source_text="Apple beats today",
    )
    assert validate_citation(good).citation_ok is True
    assert validate_citation(bad).citation_ok is False
