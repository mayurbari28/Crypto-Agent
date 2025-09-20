#Description: Streamlit multi-page root. Initializes services, scheduler, and shared state.

import os
import time
import streamlit as st

from utils.config import settings
from utils.context import get_app_context
from services.scheduler import start_scheduler, get_scheduler
from utils.logging import logger
from models.db import init_db

st.set_page_config(
    page_title="Agentic AI CoinDCX Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize DB and services once
if "app_initialized" not in st.session_state:
    init_db()
    ctx = get_app_context()
    # Start background scheduler
    start_scheduler()
    st.session_state["app_initialized"] = True
    st.session_state["kill_switch"] = False
    st.session_state["auto_trade"] = False
    st.session_state["confidence_threshold"] = settings.CONFIDENCE_THRESHOLD
    logger.info("App initialized")

st.title("Agentic AI Trading System - CoinDCX")
st.subheader("Live Dashboard and Controls")

# Global controls
col1, col2, col3, col4 = st.columns([1,1,2,2])

with col1:
    st.session_state["kill_switch"] = st.toggle("Kill Switch", value=st.session_state["kill_switch"])
with col2:
    st.session_state["auto_trade"] = st.toggle("Auto-Trade", value=st.session_state["auto_trade"])
with col3:
    st.session_state["confidence_threshold"] = st.slider(
        "Confidence Threshold", min_value=0.5, max_value=0.95,
        value=float(st.session_state["confidence_threshold"]), step=0.01
    )
with col4:
    st.write(f"Mode: {settings.MODE.upper()} | Spot {int(settings.SPOT_ALLOCATION_PCT*100)}% | Fut {int(settings.FUTURES_ALLOCATION_PCT*100)}%")

st.info("Use the pages sidebar to access Screener, Strategy Config, Portfolio, Backtesting, API & Keys, and Risk Center.")

st.divider()

# Quick overview (embed dashboard preview)
from services.portfolio import PortfolioService
from services.market_data import MarketDataService
from services.monitor import MonitorService
from utils.charts import equity_chart, positions_table, exposure_pie

portfolio = PortfolioService.instance()
market = MarketDataService.instance()
monitor = MonitorService.instance()

# Update auto-trade and kill-switch in services
portfolio.set_auto_trade(st.session_state["auto_trade"])
monitor.set_kill_switch(st.session_state["kill_switch"])
portfolio.set_confidence_threshold(st.session_state["confidence_threshold"])

st.divider()

# Quick overview (embed dashboard preview)
from services.portfolio import PortfolioService
from services.market_data import MarketDataService
from services.monitor import MonitorService
from utils.charts import equity_chart, positions_table, exposure_pie

portfolio = PortfolioService.instance()
market = MarketDataService.instance()
monitor = MonitorService.instance()

# Update auto-trade and kill-switch in services
portfolio.set_auto_trade(st.session_state["auto_trade"])
monitor.set_kill_switch(st.session_state["kill_switch"])
portfolio.set_confidence_threshold(st.session_state["confidence_threshold"])

# Equity and exposure
colA, colB = st.columns([2,1])
with colA:
    eq_df = portfolio.get_equity_curve()
    st.plotly_chart(equity_chart(eq_df), use_container_width=True)
with colB:
    exp_df = portfolio.get_exposure_snapshot()
    st.plotly_chart(exposure_pie(exp_df), use_container_width=True)

# Open positions
st.subheader("Open Positions")
st.dataframe(positions_table(portfolio.get_open_positions_df()), use_container_width=True)

# Logs preview
st.subheader("Recent Events")
for log in portfolio.get_recent_events(limit=10):
    st.write(f"{log['ts']} [{log['level']}] {log['message']}")
