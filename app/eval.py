"""Eval harness — the trust differentiator.

Runs the active backend over a hand-labelled set and reports:

* hallucination_rate  — fraction of items whose cited span is NOT in the source.
* citation_precision  — 1 - hallucination_rate.
* sentiment_f1        — macro-F1 of sign(sentiment) vs. labelled direction.
* sentiment_corr      — Pearson correlation of predicted vs. labelled score.
* ticker_jaccard      — mean Jaccard overlap of predicted vs. labelled tickers.
* latency / throughput.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from .config import Settings, get_settings
from .llm import extract_one
from .schemas import EvalResult

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _sign(x: float) -> int:
    return 1 if x > 0.1 else -1 if x < -0.1 else 0


def _macro_f1(y_true: list[int], y_pred: list[int]) -> float:
    labels = {-1, 0, 1}
    f1s = []
    for lab in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == lab and p == lab)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t != lab and p == lab)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=False) if t == lab and p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    return sum(f1s) / len(f1s)


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=False))
    da = sum((x - ma) ** 2 for x in a) ** 0.5
    db = sum((y - mb) ** 2 for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def load_labeled(path: Path | None = None) -> list[dict]:
    path = path or (DATA_DIR / "eval_labeled.csv")
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    return rows


def run_eval(settings: Settings | None = None, path: Path | None = None) -> EvalResult:
    """Score the active backend against the labelled set."""
    s = settings or get_settings()
    rows = load_labeled(path)

    y_true_sign, y_pred_sign = [], []
    true_score, pred_score = [], []
    jaccards = []
    halluc = 0
    latencies = []

    t_all = time.perf_counter()
    for r in rows:
        t0 = time.perf_counter()
        ext = extract_one(r["id"], r["text"], s)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        y_true_sign.append(int(r["label_direction"]))
        y_pred_sign.append(_sign(ext.sentiment))
        true_score.append(float(r["label_sentiment"]))
        pred_score.append(ext.sentiment)

        true_tickers = {
            t.strip().upper() for t in r.get("label_tickers", "").split("|") if t.strip()
        }
        jaccards.append(_jaccard(true_tickers, set(ext.tickers)))

        if not ext.citation_ok:
            halluc += 1

    wall = time.perf_counter() - t_all
    n = len(rows)
    return EvalResult(
        n=n,
        hallucination_rate=round(halluc / n, 4) if n else 0.0,
        citation_precision=round(1 - halluc / n, 4) if n else 1.0,
        sentiment_f1=round(_macro_f1(y_true_sign, y_pred_sign), 4),
        sentiment_corr=round(_pearson(true_score, pred_score), 4),
        ticker_jaccard=round(sum(jaccards) / n, 4) if n else 0.0,
        mean_latency_ms=round(sum(latencies) / n, 3) if n else 0.0,
        throughput_per_s=round(n / wall, 1) if wall else 0.0,
    )


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(run_eval().model_dump(), indent=2))
