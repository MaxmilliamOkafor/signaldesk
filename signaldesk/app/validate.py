"""Citation validation — the anti-hallucination guard.

A rationale is only trustworthy if the span it quotes really exists in the
source. We normalise whitespace/case before checking so trivial formatting
differences don't cause false rejections, but a fabricated span is flagged.
"""

from __future__ import annotations

import re

from .schemas import Extraction

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def span_in_source(span: str, source: str) -> bool:
    """True iff ``span`` is a (whitespace/case-normalised) substring of ``source``."""
    if not span:
        return False
    return _norm(span) in _norm(source)


def validate_citation(ext: Extraction) -> Extraction:
    """Set ``citation_ok`` based on whether the span is grounded in the source."""
    ext.citation_ok = span_in_source(ext.source_span, ext.source_text)
    return ext
