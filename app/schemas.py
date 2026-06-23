"""Pydantic schemas for the SignalDesk extraction pipeline.

The extraction contract is intentionally strict: every rationale must quote a
``source_span`` that is a verbatim substring of the headline it was drawn from.
That invariant is what the citation validator and the eval harness check.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class Headline(BaseModel):
    """A single inbound news item."""

    id: str = Field(..., description="Stable unique id for the headline.")
    text: str = Field(..., min_length=1, description="Raw headline text.")
    source: str = Field(default="unknown", description="Feed / publisher name.")
    ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Ingest timestamp (UTC).",
    )

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class Extraction(BaseModel):
    """Structured signal extracted from a single headline."""

    id: str
    tickers: list[str] = Field(default_factory=list)
    sentiment: float = Field(..., ge=-1.0, le=1.0)
    rationale: str = Field(..., min_length=1)
    source_span: str = Field(
        ...,
        min_length=1,
        description="Verbatim substring of the source headline supporting the call.",
    )
    source_text: str = Field(..., description="The headline the span must be found in.")
    citation_ok: bool = Field(
        default=False,
        description="True iff source_span is a verbatim substring of source_text.",
    )
    backend: str = Field(default="local", description="LLM backend that produced this.")
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("tickers")
    @classmethod
    def _upper_unique(cls, v: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for t in v:
            seen.setdefault(t.upper().strip(), None)
        return list(seen.keys())


class EvalResult(BaseModel):
    """Aggregate metrics produced by the eval harness."""

    n: int
    hallucination_rate: float
    citation_precision: float
    sentiment_f1: float
    sentiment_corr: float
    ticker_jaccard: float
    mean_latency_ms: float
    throughput_per_s: float
