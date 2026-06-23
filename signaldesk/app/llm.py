"""LLM extraction with a pluggable backend.

Three backends are wired behind one interface:

* ``local``  — a deterministic, dependency-free extractor (finance sentiment
  lexicon + cashtag/company ticker resolver). It runs anywhere with no keys,
  which is what makes the hosted demo, CI, and the eval harness reproducible.
* ``ollama`` — calls a local Ollama server (e.g. ``llama3``) with a strict
  JSON prompt.
* ``openai`` / ``gemini`` — API-key backends using JSON-mode prompts.

Every backend returns the SAME ``Extraction`` shape, and every result is run
through citation validation before it leaves this module.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable

from .config import Settings, get_settings
from .schemas import Extraction
from .validate import validate_citation

logger = logging.getLogger("signaldesk.llm")

# --- A compact finance sentiment lexicon (Loughran-McDonald flavoured) -------
_POSITIVE = {
    "beat": 0.7,
    "beats": 0.7,
    "surge": 0.8,
    "surges": 0.8,
    "soar": 0.85,
    "soars": 0.85,
    "jump": 0.6,
    "jumps": 0.6,
    "rally": 0.7,
    "rallies": 0.7,
    "gain": 0.5,
    "gains": 0.5,
    "rise": 0.45,
    "rises": 0.45,
    "record": 0.6,
    "upgrade": 0.7,
    "upgraded": 0.7,
    "outperform": 0.7,
    "strong": 0.55,
    "profit": 0.5,
    "profits": 0.5,
    "growth": 0.5,
    "raises": 0.55,
    "raised": 0.55,
    "boost": 0.6,
    "boosts": 0.6,
    "approval": 0.6,
    "approved": 0.6,
    "wins": 0.6,
    "tops": 0.65,
    "topped": 0.65,
    "bullish": 0.8,
    "rebound": 0.6,
    "expands": 0.45,
}
_NEGATIVE = {
    "miss": -0.7,
    "misses": -0.7,
    "missed": -0.7,
    "plunge": -0.85,
    "plunges": -0.85,
    "slump": -0.7,
    "slumps": -0.7,
    "fall": -0.5,
    "falls": -0.5,
    "drop": -0.55,
    "drops": -0.55,
    "tumble": -0.8,
    "tumbles": -0.8,
    "downgrade": -0.7,
    "downgraded": -0.7,
    "cut": -0.5,
    "cuts": -0.5,
    "loss": -0.6,
    "losses": -0.6,
    "weak": -0.55,
    "warn": -0.65,
    "warns": -0.65,
    "warning": -0.65,
    "lawsuit": -0.6,
    "probe": -0.55,
    "recall": -0.6,
    "bearish": -0.8,
    "slashes": -0.7,
    "slashed": -0.7,
    "layoffs": -0.65,
    "bankruptcy": -0.9,
    "fraud": -0.85,
    "halts": -0.5,
    "sinks": -0.75,
    "decline": -0.5,
    "declines": -0.5,
    "fears": -0.6,
}

# Minimal company -> ticker map. Extend freely; cashtags ($AAPL) work without it.
_COMPANY_TICKER = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "netflix": "NFLX",
    "intel": "INTC",
    "amd": "AMD",
    "boeing": "BA",
    "ford": "F",
    "disney": "DIS",
    "walmart": "WMT",
    "jpmorgan": "JPM",
    "goldman": "GS",
    "exxon": "XOM",
    "chevron": "CVX",
    "pfizer": "PFE",
    "moderna": "MRNA",
    "starbucks": "SBUX",
    "uber": "UBER",
    "coinbase": "COIN",
    "paypal": "PYPL",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "broadcom": "AVGO",
    "qualcomm": "QCOM",
    "micron": "MU",
    "palantir": "PLTR",
}

_CASHTAG = re.compile(r"\$([A-Z]{1,5})\b")
_WORD = re.compile(r"[A-Za-z']+")


def _resolve_tickers(text: str) -> list[str]:
    found: list[str] = []
    for m in _CASHTAG.finditer(text):
        found.append(m.group(1))
    low = text.lower()
    for name, tick in _COMPANY_TICKER.items():
        if re.search(rf"\b{re.escape(name)}\b", low):
            found.append(tick)
    # de-dup, preserve order
    seen: dict[str, None] = {}
    for t in found:
        seen.setdefault(t, None)
    return list(seen.keys())


def _best_span(text: str) -> tuple[str, float]:
    """Return the strongest sentiment-bearing token span and its score.

    The returned span is, by construction, a verbatim substring of ``text``,
    so it satisfies citation validation.
    """
    best_word = ""
    best_abs = 0.0
    score_sum = 0.0
    hits = 0
    for m in _WORD.finditer(text):
        w = m.group(0).lower()
        s = _POSITIVE.get(w, _NEGATIVE.get(w, 0.0))
        if s != 0.0:
            score_sum += s
            hits += 1
            if abs(s) > best_abs:
                best_abs = abs(s)
                # use the original-cased token from the source text
                best_word = text[m.start() : m.end()]
    if hits == 0:
        # neutral: cite the longest word as a stable, real span
        words = _WORD.findall(text)
        longest = max(words, key=len) if words else text[:8]
        return longest, 0.0
    avg = max(-1.0, min(1.0, score_sum / hits))
    return best_word, avg


def _local_extract(h_id: str, text: str) -> Extraction:
    span, sentiment = _best_span(text)
    tickers = _resolve_tickers(text)
    direction = "bullish" if sentiment > 0.1 else "bearish" if sentiment < -0.1 else "neutral"
    rationale = (
        f"Headline signals a {direction} read for "
        f"{', '.join(tickers) if tickers else 'the market'} "
        f"on the cue '{span}'."
    )
    ext = Extraction(
        id=h_id,
        tickers=tickers,
        sentiment=round(sentiment, 3),
        rationale=rationale,
        source_span=span,
        source_text=text,
        backend="local",
    )
    return validate_citation(ext)


_SYSTEM_PROMPT = (
    "You are a financial news extraction engine. For the headline, return STRICT "
    "JSON with keys: tickers (array of uppercase US tickers), sentiment (float in "
    "[-1,1]), rationale (one sentence), source_span (a VERBATIM substring of the "
    "headline that justifies the call). The source_span MUST appear character-for-"
    "character in the headline. Return only JSON."
)


def _parse_llm_json(h_id: str, text: str, raw: str, backend: str) -> Extraction:
    raw = raw.strip()
    # tolerate code fences
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{") :]
    data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
    ext = Extraction(
        id=h_id,
        tickers=[str(t) for t in data.get("tickers", [])],
        sentiment=float(data.get("sentiment", 0.0)),
        rationale=str(data.get("rationale", "")) or "n/a",
        source_span=str(data.get("source_span", "")) or text[:8],
        source_text=text,
        backend=backend,
    )
    return validate_citation(ext)


def _ollama_extract(s: Settings, h_id: str, text: str) -> Extraction:
    import requests  # local import keeps base install light

    resp = requests.post(
        f"{s.ollama_host}/api/generate",
        json={
            "model": s.ollama_model,
            "prompt": f"{_SYSTEM_PROMPT}\n\nHeadline: {text}\nJSON:",
            "stream": False,
            "format": "json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    return _parse_llm_json(h_id, text, resp.json()["response"], "ollama")


def _openai_extract(s: Settings, h_id: str, text: str) -> Extraction:
    from openai import OpenAI

    client = OpenAI(api_key=s.openai_api_key)
    resp = client.chat.completions.create(
        model=s.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Headline: {text}"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return _parse_llm_json(h_id, text, resp.choices[0].message.content, "openai")


def _gemini_extract(s: Settings, h_id: str, text: str) -> Extraction:
    import google.generativeai as genai

    genai.configure(api_key=s.gemini_api_key)
    model = genai.GenerativeModel(s.gemini_model, system_instruction=_SYSTEM_PROMPT)
    resp = model.generate_content(
        f"Headline: {text}",
        generation_config={"response_mime_type": "application/json"},
    )
    return _parse_llm_json(h_id, text, resp.text, "gemini")


def extract_one(h_id: str, text: str, settings: Settings | None = None) -> Extraction:
    """Extract a structured signal from one headline using the active backend."""
    s = settings or get_settings()
    backend = s.llm_backend.lower()
    try:
        if backend == "ollama":
            return _ollama_extract(s, h_id, text)
        if backend == "openai":
            return _openai_extract(s, h_id, text)
        if backend == "gemini":
            return _gemini_extract(s, h_id, text)
    except Exception as exc:  # noqa: BLE001 - resilient fallback for the demo
        logger.warning("backend %s failed (%s); falling back to local", backend, exc)
    return _local_extract(h_id, text)


def extract_many(
    items: Iterable[tuple[str, str]], settings: Settings | None = None
) -> list[Extraction]:
    """Extract over an iterable of ``(id, text)`` pairs."""
    s = settings or get_settings()
    return [extract_one(i, t, s) for i, t in items]
