#Description: Configure strategy parameters, confidence model weights, allocation, and risk.

import streamlit as st
from services.signals import SignalService
from services.portfolio import PortfolioService

st.title("Strategy Configuration")

sig = SignalService.instance()
port = PortfolioService.instance()

with st.form("strategy_form", clear_on_submit=False):
    st.subheader("Strategy Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        ema_fast = st.number_input("EMA Fast", 5, 100, value=sig.params["ema_fast"])
        ema_slow = st.number_input("EMA Slow", 10, 400, value=sig.params["ema_slow"])
    with col2:
        rsi_len = st.number_input("RSI Length", 5, 50, value=sig.params["rsi_length"])
        atr_len = st.number_input("ATR Length", 5, 100, value=sig.params["atr_length"])
    with col3:
        rr_target = st.slider("Risk-Reward Target", 1.0, 3.0, value=float(sig.params["rr_target"]), step=0.1)
        breakout_lookback = st.number_input("Breakout Lookback", 10, 200, value=sig.params["breakout_lookback"])

    st.subheader("Confidence Model Weights")
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        w_trend = st.slider("Trend Weight", 0.0, 1.0, value=float(sig.params["w_trend"]), step=0.05)
    with col5:
        w_rsi = st.slider("RSI Weight", 0.0, 1.0, value=float(sig.params["w_rsi"]), step=0.05)
    with col6:
        w_macd = st.slider("MACD Weight", 0.0, 1.0, value=float(sig.params["w_macd"]), step=0.05)
    with col7:
        w_breakout = st.slider("Breakout Weight", 0.0, 1.0, value=float(sig.params["w_breakout"]), step=0.05)

    st.subheader("Allocation & Risk")
    col8, col9, col10 = st.columns(3)
    with col8:
        max_positions = st.number_input("Max Positions", 1, 20, value=port.config["max_positions"])
    with col9:
        per_trade_risk = st.slider("Risk per Trade (%)", 0.1, 2.0, value=float(port.config["risk_per_trade_pct"]*100), step=0.1)
    with col10:
        max_leverage = st.slider("Max Leverage (Futures)", 1, 10, value=port.config["max_leverage"])

    save = st.form_submit_button("Save")
    if save:
        sig.update_params(dict(
            ema_fast=ema_fast, ema_slow=ema_slow, rsi_length=rsi_len, atr_length=atr_len,
            rr_target=rr_target, breakout_lookback=breakout_lookback,
            w_trend=w_trend, w_rsi=w_rsi, w_macd=w_macd, w_breakout=w_breakout
        ))
        port.update_config(dict(
            max_positions=max_positions, risk_per_trade_pct=per_trade_risk/100.0, max_leverage=max_leverage
        ))
        st.success("Strategy and risk parameters updated.")
