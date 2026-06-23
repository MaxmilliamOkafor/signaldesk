"""SignalDesk dashboard — live feed, per-ticker sentiment, and Model Quality.

Run locally:
    streamlit run dashboard/streamlit_app.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# Make the app package importable when run via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.eval import run_eval  # noqa: E402
from app.ingest import read_replay_csv  # noqa: E402
from app.llm import extract_one  # noqa: E402

st.set_page_config(page_title="SignalDesk", page_icon="📈", layout="wide")

st.title("📈 SignalDesk — Real-Time Market-Sentiment Engine")
st.caption(
    "LLM-extracted, citation-validated sentiment from financial news. "
    f"Active backend: **{get_settings().llm_backend}**"
)

page = st.sidebar.radio("View", ["Live feed", "Model Quality"])
speed = st.sidebar.slider("Replay pacing (s/item)", 0.0, 1.0, 0.05, 0.05)


def _color(s: float) -> str:
    return "🟢" if s > 0.1 else "🔴" if s < -0.1 else "⚪️"


if page == "Live feed":
    headlines = read_replay_csv()
    chart_area = st.empty()
    feed_area = st.container()
    rows = []

    run = st.sidebar.button("▶ Stream replay", type="primary")
    if run:
        progress = st.sidebar.progress(0.0)
        for i, h in enumerate(headlines, start=1):
            ext = extract_one(h.id, h.text)
            for tk in ext.tickers or ["MARKET"]:
                rows.append({"ticker": tk, "sentiment": ext.sentiment, "step": i})
            df = pd.DataFrame(rows)
            if not df.empty:
                chart = (
                    alt.Chart(df)
                    .mark_line(point=True)
                    .encode(
                        x="step:Q",
                        y=alt.Y("mean(sentiment):Q", scale=alt.Scale(domain=[-1, 1])),
                        color="ticker:N",
                        tooltip=["ticker", "sentiment"],
                    )
                    .properties(height=320)
                )
                chart_area.altair_chart(chart, use_container_width=True)
            with feed_area:
                badge = "✅" if ext.citation_ok else "⚠️"
                with st.expander(
                    f"{_color(ext.sentiment)} {h.text}  ·  {ext.sentiment:+.2f} {badge}"
                ):
                    st.write(f"**Tickers:** {', '.join(ext.tickers) or '—'}")
                    st.write(f"**Rationale:** {ext.rationale}")
                    st.write(f"**Cited span:** “{ext.source_span}”")
                    st.write(f"**Citation valid:** {ext.citation_ok}")
            progress.progress(i / len(headlines))
            if speed:
                time.sleep(speed)
        st.success("Replay complete.")
    else:
        st.info("Press **▶ Stream replay** in the sidebar to begin.")

else:  # Model Quality
    st.subheader("Model Quality — eval harness")
    st.write(
        "These metrics are computed live by running the active backend over a "
        "hand-labelled set of headlines."
    )
    if st.button("Run eval", type="primary"):
        with st.spinner("Scoring…"):
            res = run_eval()
        c1, c2, c3 = st.columns(3)
        c1.metric("Hallucination rate", f"{res.hallucination_rate:.1%}")
        c2.metric("Citation precision", f"{res.citation_precision:.1%}")
        c3.metric("Items", res.n)
        c4, c5, c6 = st.columns(3)
        c4.metric("Sentiment F1", f"{res.sentiment_f1:.3f}")
        c5.metric("Sentiment corr", f"{res.sentiment_corr:.3f}")
        c6.metric("Ticker Jaccard", f"{res.ticker_jaccard:.3f}")
        c7, c8 = st.columns(2)
        c7.metric("Latency / item", f"{res.mean_latency_ms:.3f} ms")
        c8.metric("Throughput", f"{res.throughput_per_s:,.0f}/s")
