#Description: Screener for opportunities with scores and rationale; manual execution.

import streamlit as st
import pandas as pd

from services.signals import SignalService
from services.portfolio import PortfolioService
from services.execution import ExecutionService
from ai.crew import CrewOrchestrator
from utils.config import settings
from utils.charts import signal_chart
from utils.logging import logger

st.title("Screener & Signals")

signal_service = SignalService.instance()
#portfolio = PortfolioService.instance()
exec_service = ExecutionService.instance()
crew = CrewOrchestrator.instance()

# Controls
col1, col2, col3 = st.columns(3)
with col1:
    timeframe = st.selectbox("Timeframe", options=["15m","1h","4h","1d"], index=2)
with col2:
    universe = st.multiselect("Universe", options=signal_service.get_universe())
    #default=signal_service.get_universe()[:200]
with col3:
    st.write("Scan controls")
    run_scan = st.button("Run Scan Now")
    run_scan_all = st.button("Scan All Symbols Now")

if run_scan:
    st.info("Scanning and scoring...")
    base_signals = signal_service.scan_and_score(universe, timeframe)
    enriched = crew.enrich_signals(base_signals, timeframe=timeframe)
    st.success("Scan complete.")
    st.session_state["latest_signals"] = enriched

if run_scan_all:
    all_symbols=signal_service.get_universe()
    logger.info(f'Symbols to analyse ===> {all_symbols}')
    st.info("Scanning and scoring...")
    base_signals = signal_service.scan_and_score(all_symbols, timeframe)
    enriched = crew.enrich_signals(base_signals, timeframe=timeframe)
    st.success("Scan complete.")
    st.session_state["latest_signals"] = enriched

signals = st.session_state.get("latest_signals", [])
if not signals:
    st.warning("No signals available. Click 'Run Scan Now' to generate signals.")
else:
    df = pd.DataFrame([{
        "Symbol": s.symbol, "Market": s.market, "Time Frame": s.timeframe, "Confidence(%)": round(s.confidence,2)*100 ,
        "Entry": round(s.entry,6),"Exp. Return %": round(s.expected_return_pct,2),
        "Suggested Leverage": str(round(s.suggested_leverage))+"x", "Exp Return(+L.)%": round(s.expected_return_pct * s.suggested_leverage),
        "Target Price": round(s.tp,6), "Stop Loss": round(s.sl,6), 
        "Risk: Reward": round((s.tp - s.entry) / (s.entry - s.sl) if (s.entry - s.sl)!=0 else 0, 2),
        "Rationale": s.rationale[:160] + ("..." if len(s.rationale)>160 else "")
    } for s in signals])
    st.dataframe(df, use_container_width=True)

    st.subheader("Auto-Allocate and Execute")
    above = [s for s in signals if s.confidence >= float(st.session_state.get("confidence_threshold", settings.CONFIDENCE_THRESHOLD))]
    st.write(f"Candidates above threshold: {len(above)}")
    do_exec = st.button("Execute Orders for Candidates")
    if do_exec:
        res = exec_service.allocate_and_execute(above)
        st.success(f"Orders placed: {res['orders_placed']}, Skipped: {res['skipped']}, Errors: {res['errors']}")

    st.subheader("Chart & Edit")
    selected_symbol = st.selectbox("Symbol", options=[s.symbol for s in signals])
    sel = next(s for s in signals if s.symbol == selected_symbol)
    fig = signal_chart(sel)
    st.plotly_chart(fig, use_container_width=True, key="Symbol_chart")

    with st.expander("Manual Override & Place Order"):
        side = st.selectbox("Side", options=["BUY","SELL"], index=0)
        qty = st.number_input("Quantity", min_value=0.0, value=0.0, step=0.0001, format="%.6f")
        entry = st.number_input("Entry", value=float(sel.entry))
        tp = st.number_input("Target", value=float(sel.tp))
        sl = st.number_input("Stop", value=float(sel.sl))
        market_type = st.selectbox("Market", options=["spot","futures"], index=0)
        if st.button("Place Manual Order"):
            out = exec_service.place_manual(sel.symbol, side, qty, entry, tp, sl, market_type)
            st.write(out)
