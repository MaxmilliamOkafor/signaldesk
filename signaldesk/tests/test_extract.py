"""Local backend extraction behaviour and schema guarantees."""

from app.config import Settings
from app.llm import extract_one

LOCAL = Settings(llm_backend="local")


def test_positive_headline():
    e = extract_one("t1", "Apple beats earnings as iPhone sales surge", LOCAL)
    assert e.sentiment > 0
    assert "AAPL" in e.tickers
    assert e.citation_ok is True
    assert e.source_span.lower() in e.source_text.lower()


def test_negative_headline():
    e = extract_one("t2", "Tesla shares plunge after delivery miss", LOCAL)
    assert e.sentiment < 0
    assert "TSLA" in e.tickers


def test_cashtag_resolution():
    e = extract_one("t3", "$AMD rallies on strong data center demand", LOCAL)
    assert "AMD" in e.tickers


def test_neutral_headline_has_valid_span():
    e = extract_one("t4", "Markets await the central bank decision", LOCAL)
    assert -0.2 <= e.sentiment <= 0.2
    assert e.citation_ok is True


def test_sentiment_bounded():
    e = extract_one("t5", "surge surge surge beats tops rally bullish record", LOCAL)
    assert -1.0 <= e.sentiment <= 1.0
