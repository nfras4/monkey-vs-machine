"""Streamlit dashboard — LEGACY. One-shot batch experiment view.

This is the original single-shot Streamlit dashboard from v1 of the project.
It works against the batch `run_experiment` path (see `mvm.runner`) and is
kept for LOCAL DIAGNOSTICS ONLY — it does NOT read the perpetual-mode SQLite
state.

For the public, perpetual dashboard, see `dashboard/` (SvelteKit + D1).
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _safe_link(url: str) -> str:
    """Return URL if it's an http(s) absolute URL, else empty string."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return url
    return ""


def _safe_md_text(text: str) -> str:
    """Strip characters that could break markdown link parsing."""
    if not text:
        return ""
    return (
        text.replace("[", "(")
        .replace("]", ")")
        .replace("\n", " ")
        .strip()
    )

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.config import DEFAULT_N_MONKEYS, DEFAULT_TOP_K, DEFAULT_UNIVERSE_SIZE, DEFAULT_YEARS  # noqa: E402
from mvm.data.news import fetch_headlines_for  # noqa: E402
from mvm.data.sentiment import mean_compound  # noqa: E402
from mvm.runner import ExperimentResult, run_experiment  # noqa: E402

st.set_page_config(page_title="Monkey vs Machine", page_icon=":monkey:", layout="wide")


@st.cache_data(show_spinner=False)
def cached_run(universe_size: int, years: int, n_monkeys: int, top_k: int, refresh: bool):
    return run_experiment(
        universe_size=universe_size,
        years=years,
        n_monkeys=n_monkeys,
        top_k=top_k,
        refresh=refresh,
    )


def race_chart(result: ExperimentResult) -> go.Figure:
    fig = go.Figure()
    ai_eq = result.ai_backtest["equity"]
    fig.add_trace(go.Scatter(x=ai_eq.index, y=ai_eq.values, name="AI trader", line=dict(color="#22c55e", width=3)))

    if result.spy_backtest is not None:
        spy_eq = result.spy_backtest["equity"]
        fig.add_trace(go.Scatter(x=spy_eq.index, y=spy_eq.values, name="SPY buy & hold", line=dict(color="#94a3b8", width=2, dash="dash")))

    pct = result.monkeys.percentile_history
    # median monkey
    fig.add_trace(go.Scatter(x=pct.index, y=pct["p50"].values, name="Median monkey", line=dict(color="#f59e0b", width=2)))
    # 5-95 band
    fig.add_trace(go.Scatter(
        x=list(pct.index) + list(pct.index[::-1]),
        y=list(pct["p95"].values) + list(pct["p5"].values[::-1]),
        fill="toself", fillcolor="rgba(245, 158, 11, 0.12)",
        line=dict(width=0), name="Monkey 5–95% band", hoverinfo="skip",
    ))
    # best monkey path (the top one we tracked)
    top_paths = result.monkeys.top_equity_history
    if not top_paths.empty:
        best_col = top_paths.iloc[-1].idxmax()
        fig.add_trace(go.Scatter(
            x=top_paths.index, y=top_paths[best_col].values,
            name=f"Best monkey ({best_col})",
            line=dict(color="#ef4444", width=2),
        ))

    fig.update_layout(
        title="Equity over time",
        xaxis_title="Date", yaxis_title="Portfolio value ($)",
        hovermode="x unified",
        height=520,
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def monkey_dist_chart(result: ExperimentResult) -> go.Figure:
    final = result.monkeys.final_equity
    ai_final = float(result.ai_backtest["equity"].iloc[-1])
    spy_final = float(result.spy_backtest["equity"].iloc[-1]) if result.spy_backtest is not None else None

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=final, nbinsx=80, name="Monkey final equity", marker_color="#f59e0b"))
    fig.add_vline(x=ai_final, line_width=3, line_color="#22c55e", annotation_text="AI", annotation_position="top")
    if spy_final is not None:
        fig.add_vline(x=spy_final, line_width=2, line_dash="dash", line_color="#94a3b8", annotation_text="SPY", annotation_position="top")
    fig.update_layout(
        title="Distribution of 100k monkey outcomes",
        xaxis_title="Final equity ($)", yaxis_title="Number of monkeys",
        height=420,
    )
    return fig


def feature_imp_chart(result: ExperimentResult) -> go.Figure:
    imp = result.ai.feature_importance
    items = sorted(imp.items(), key=lambda kv: kv[1])
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    fig = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color="#22c55e"))
    fig.update_layout(title="AI permutation importance", height=420, xaxis_title="Score drop when feature is shuffled")
    return fig


def percentile_of(value: float, sample: np.ndarray) -> float:
    return float((sample < value).mean()) * 100


def main() -> None:
    st.title(":monkey: Monkey vs Machine")
    st.caption("Gradient-boosting AI trader vs 100,000 random monkeys on S&P 500 history.")

    with st.sidebar:
        st.header("Run settings")
        universe_size = st.slider("Universe size (tickers)", 10, 100, DEFAULT_UNIVERSE_SIZE, step=10)
        years = st.slider("Years of history", 1, 10, DEFAULT_YEARS)
        n_monkeys = st.select_slider(
            "Monkey count",
            options=[1_000, 5_000, 20_000, 50_000, 100_000, 200_000],
            value=DEFAULT_N_MONKEYS,
        )
        top_k = st.slider("AI top-K holdings", 1, 25, DEFAULT_TOP_K)
        refresh = st.checkbox("Force-refresh price cache", value=False)
        run_clicked = st.button("Run experiment", type="primary", use_container_width=True)

    if "result" not in st.session_state and not run_clicked:
        st.info("Set parameters and hit **Run experiment**. First run downloads ~5 years of data and takes ~30s; subsequent runs are cached.")
        return

    if run_clicked:
        with st.spinner("Running data → AI → monkeys → benchmark..."):
            st.session_state["result"] = cached_run(int(universe_size), int(years), int(n_monkeys), int(top_k), bool(refresh))

    result: ExperimentResult = st.session_state["result"]

    # Headline metrics
    ai_metrics = result.ai_backtest["metrics"]
    monkey_meta = result.monkeys.metadata
    spy_metrics = result.spy_backtest["metrics"] if result.spy_backtest else None

    cols = st.columns(4)
    cols[0].metric("AI final equity", f"${ai_metrics['final_equity']:,.0f}", f"CAGR {ai_metrics['cagr']*100:.1f}%")
    cols[1].metric("AI Sharpe", f"{ai_metrics['sharpe']:.2f}", f"Max DD {ai_metrics['max_drawdown']*100:.1f}%")
    cols[2].metric("Best monkey", f"${monkey_meta['best_final']:,.0f}", f"Median ${monkey_meta['median_final']:,.0f}")
    if spy_metrics:
        cols[3].metric("SPY final equity", f"${spy_metrics['final_equity']:,.0f}", f"CAGR {spy_metrics['cagr']*100:.1f}%")
    else:
        cols[3].metric("SPY benchmark", "n/a")

    ai_pct = percentile_of(ai_metrics["final_equity"], result.monkeys.final_equity)
    st.success(f"AI finished in the **{ai_pct:.1f}th percentile** of the monkey pack. ({monkey_meta['frac_beat_starting']*100:.1f}% of monkeys ended above their starting cash.)")

    race_tab, dist_tab, ai_tab, today_tab = st.tabs(["Race", "Monkey distribution", "AI internals", "Today's read"])

    with race_tab:
        st.plotly_chart(race_chart(result), use_container_width=True)
        st.caption("Top-K AI portfolio rebalanced weekly; monkeys take random buy/sell/hold actions daily.")

    with dist_tab:
        st.plotly_chart(monkey_dist_chart(result), use_container_width=True)
        beat_ai = (result.monkeys.final_equity > ai_metrics["final_equity"]).sum()
        st.write(f"**{beat_ai:,}** monkeys beat the AI ({beat_ai/len(result.monkeys.final_equity)*100:.2f}%).")

    with ai_tab:
        st.plotly_chart(feature_imp_chart(result), use_container_width=True)
        with st.expander("Latest AI ranking (last prediction day)"):
            preds = result.ai.predictions
            if not preds.empty:
                last_row = preds.iloc[-1].dropna().sort_values(ascending=False)
                st.dataframe(last_row.rename("P(up next 5d)").to_frame())
            else:
                st.write("No predictions available.")
        with st.expander("Run metadata"):
            st.json(result.ai.metadata)

    with today_tab:
        st.write("Live yfinance headlines + VADER sentiment for the AI's current top picks. (Dashboard-only; never used in the backtest.)")
        preds = result.ai.predictions
        if preds.empty:
            st.warning("AI made no predictions in this run.")
        else:
            top_picks = preds.iloc[-1].dropna().sort_values(ascending=False).head(min(8, top_k)).index.tolist()
            with st.spinner(f"Fetching live news for {len(top_picks)} tickers..."):
                headlines_by_ticker = fetch_headlines_for(top_picks, limit_per_ticker=5)
            rows = []
            for t, items in headlines_by_ticker.items():
                titles = [h["title"] for h in items if h.get("title")]
                sentiment = mean_compound(titles) if titles else 0.0
                rows.append({
                    "ticker": t,
                    "p_up_next_5d": float(preds.iloc[-1].get(t, np.nan)),
                    "headlines": len(titles),
                    "vader_compound": round(sentiment, 3),
                })
            st.dataframe(pd.DataFrame(rows).set_index("ticker"), use_container_width=True)

            for t in top_picks:
                items = headlines_by_ticker.get(t, [])
                if not items:
                    continue
                with st.expander(f"{t} headlines"):
                    for h in items:
                        title = _safe_md_text(h.get("title", ""))
                        link = _safe_link(h.get("link") or "")
                        pub = _safe_md_text(h.get("publisher") or "")
                        when = _safe_md_text(h.get("published_at") or "")
                        if link:
                            st.markdown(f"- [{title}]({link}) — *{pub}* {when}")
                        else:
                            st.write(f"- {title} — {pub} {when}")


if __name__ == "__main__":
    main()
