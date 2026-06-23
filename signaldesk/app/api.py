"""FastAPI surface for SignalDesk: ingest, extract, and eval."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from pydantic import BaseModel

from . import __version__
from .config import get_settings
from .eval import run_eval
from .ingest import read_replay_csv
from .llm import extract_one
from .schemas import EvalResult, Extraction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="SignalDesk", version=__version__)


class ExtractRequest(BaseModel):
    id: str = "adhoc-1"
    text: str


@app.get("/health")
def health() -> dict[str, str]:
    s = get_settings()
    return {"status": "ok", "version": __version__, "backend": s.llm_backend}


@app.post("/extract", response_model=Extraction)
def extract(req: ExtractRequest) -> Extraction:
    """Extract a structured, citation-validated signal from one headline."""
    return extract_one(req.id, req.text)


@app.get("/replay", response_model=list[Extraction])
def replay(limit: int = 25) -> list[Extraction]:
    """Run the bundled replay headlines through the active backend."""
    items = read_replay_csv()[:limit]
    return [extract_one(h.id, h.text) for h in items]


@app.get("/eval", response_model=EvalResult)
def eval_endpoint() -> EvalResult:
    """Score the active backend against the hand-labelled set."""
    return run_eval()
