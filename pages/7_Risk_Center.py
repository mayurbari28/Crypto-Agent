#Description: Global risk controls and circuit breakers.

import streamlit as st
from services.monitor import MonitorService
from services.portfolio import PortfolioService

st.title("Risk Center")

monitor = MonitorService.instance()
portfolio = PortfolioService.instance()

with st.form("risk_form"):
    st.subheader("Global Limits")
    max_daily_loss_pct = st.slider("Max Daily Loss (%)", 1.0, 20.0, value=float(monitor.config["max_daily_loss_pct"]), step=0.5)
    per_asset_cap_pct = st.slider("Per-Asset Cap (% of Equity)", 1.0, 50.0, value=float(monitor.config["per_asset_cap_pct"]), step=1.0)
    corr_cap = st.slider("Correlation Cap", 0.0, 1.0, value=float(monitor.config["correlation_cap"]), step=0.05)
    cb_vol_spike = st.slider("Circuit Breaker Volatility Spike (ATRx)", 1.0, 5.0, value=float(monitor.config["vol_spike_atr_mult"]), step=0.5)
    save = st.form_submit_button("Save Risk Settings")
    if save:
        monitor.update_config(dict(
            max_daily_loss_pct=max_daily_loss_pct,
            per_asset_cap_pct=per_asset_cap_pct,
            correlation_cap=corr_cap,
            vol_spike_atr_mult=cb_vol_spike,
        ))
        st.success("Risk settings updated.")

st.subheader("Kill Switch")
st.write("Immediate disable of new orders and optional cancel of open ones.")
if st.button("Activate Kill Switch"):
    monitor.set_kill_switch(True)
    st.success("Kill Switch activated.")

st.subheader("Diagnostics")
st.json(monitor.get_status())
