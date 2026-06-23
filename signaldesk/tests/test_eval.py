"""Eval harness produces sane, bounded metrics on the labelled set."""

from app.config import Settings
from app.eval import run_eval

LOCAL = Settings(llm_backend="local")


def test_eval_runs_and_is_bounded():
    res = run_eval(LOCAL)
    assert res.n >= 30
    assert 0.0 <= res.hallucination_rate <= 1.0
    assert 0.0 <= res.citation_precision <= 1.0
    assert 0.0 <= res.sentiment_f1 <= 1.0
    assert -1.0 <= res.sentiment_corr <= 1.0


def test_local_backend_does_not_hallucinate():
    # By construction the local backend cites real spans.
    res = run_eval(LOCAL)
    assert res.hallucination_rate == 0.0


def test_sentiment_signal_is_useful():
    res = run_eval(LOCAL)
    assert res.sentiment_corr > 0.5
    assert res.sentiment_f1 > 0.5
