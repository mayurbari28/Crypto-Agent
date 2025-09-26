# Description: Configure strategy parameters, confidence model weights, allocation, and risk.

import streamlit as st
from services.signals import SignalService
from services.portfolio import PortfolioService

# Preset parameter configs
PRESETS = {
    "BalancedDefault": {
        "ema_fast": 20, "ema_slow": 50, "rsi_length": 14, "atr_length": 14,
        "breakout_lookback": 55, "rr_target": 1.8,
        "trend_use_atr": True, "trend_k_atr": 1.5, "trend_k_pct": 0.02,
        "rsi_center": 58.0, "rsi_width": 30.0,
        "macd_k_atr": 1.0, "macd_k_pct_close": 0.01,
        "adx_trend_threshold": 20.0,
        "w_trend": 0.40, "w_rsi": 0.20, "w_macd": 0.25, "w_breakout": 0.15,
        "weights_trending": {"trend": 0.42, "rsi": 0.18, "macd": 0.25, "breakout": 0.15},
        "weights_ranging": {"trend": 0.25, "rsi": 0.30, "macd": 0.20, "breakout": 0.25},
    },
    "FasterSwing": {
        "ema_fast": 12, "ema_slow": 36, "rsi_length": 9, "atr_length": 14,
        "breakout_lookback": 40, "rr_target": 2.0,
        "trend_use_atr": True, "trend_k_atr": 1.2, "trend_k_pct": 0.02,
        "rsi_center": 58.0, "rsi_width": 28.0,
        "macd_k_atr": 0.8, "macd_k_pct_close": 0.01,
        "adx_trend_threshold": 18.0,
        "w_trend": 0.40, "w_rsi": 0.20, "w_macd": 0.25, "w_breakout": 0.15,
        "weights_trending": {"trend": 0.45, "rsi": 0.15, "macd": 0.25, "breakout": 0.15},
        "weights_ranging": {"trend": 0.20, "rsi": 0.35, "macd": 0.15, "breakout": 0.30},
    },
    "SlowerSwing": {
        "ema_fast": 20, "ema_slow": 55, "rsi_length": 14, "atr_length": 14,
        "breakout_lookback": 60, "rr_target": 1.8,
        "trend_use_atr": True, "trend_k_atr": 2.0, "trend_k_pct": 0.02,
        "rsi_center": 58.0, "rsi_width": 32.0,
        "macd_k_atr": 1.2, "macd_k_pct_close": 0.01,
        "adx_trend_threshold": 20.0,
        "w_trend": 0.40, "w_rsi": 0.20, "w_macd": 0.25, "w_breakout": 0.15,
        "weights_trending": {"trend": 0.42, "rsi": 0.18, "macd": 0.25, "breakout": 0.15},
        "weights_ranging": {"trend": 0.25, "rsi": 0.30, "macd": 0.20, "breakout": 0.25},
    },
    "ChoppyRange": {
        "ema_fast": 14, "ema_slow": 50, "rsi_length": 14, "atr_length": 14,
        "breakout_lookback": 25, "rr_target": 1.6,
        "trend_use_atr": True, "trend_k_atr": 1.5, "trend_k_pct": 0.02,
        "rsi_center": 55.0, "rsi_width": 26.0,
        "macd_k_atr": 1.0, "macd_k_pct_close": 0.01,
        "adx_trend_threshold": 20.0,
        "w_trend": 0.20, "w_rsi": 0.35, "w_macd": 0.15, "w_breakout": 0.30,
        "weights_trending": {"trend": 0.35, "rsi": 0.25, "macd": 0.25, "breakout": 0.15},
        "weights_ranging": {"trend": 0.20, "rsi": 0.35, "macd": 0.15, "breakout": 0.30},
    },
}

def apply_preset_to_session(preset: dict):
    # Basic strategy params and weights
    for k in [
        "ema_fast","ema_slow","rsi_length","atr_length","breakout_lookback","rr_target",
        "w_trend","w_rsi","w_macd","w_breakout",
        "trend_use_atr","trend_k_atr","trend_k_pct",
        "rsi_center","rsi_width","macd_k_atr","macd_k_pct_close","adx_trend_threshold",
    ]:
        if k in preset:
            st.session_state[k] = preset[k]

    # Regime weights (optional)
    wt = preset.get("weights_trending")
    wr = preset.get("weights_ranging")
    if isinstance(wt, dict) and isinstance(wr, dict):
        st.session_state["use_regime_weights"] = True
        st.session_state["wt_trend"] = wt.get("trend", st.session_state.get("w_trend", 0.35))
        st.session_state["wt_rsi"] = wt.get("rsi", st.session_state.get("w_rsi", 0.25))
        st.session_state["wt_macd"] = wt.get("macd", st.session_state.get("w_macd", 0.25))
        st.session_state["wt_breakout"] = wt.get("breakout", st.session_state.get("w_breakout", 0.15))

        st.session_state["wr_trend"] = wr.get("trend", st.session_state.get("w_trend", 0.35))
        st.session_state["wr_rsi"] = wr.get("rsi", st.session_state.get("w_rsi", 0.25))
        st.session_state["wr_macd"] = wr.get("macd", st.session_state.get("w_macd", 0.25))
        st.session_state["wr_breakout"] = wr.get("breakout", st.session_state.get("w_breakout", 0.15))
    else:
        st.session_state["use_regime_weights"] = False

st.title("Strategy Configuration")

sig = SignalService.instance()
port = PortfolioService.instance()

# Preset loader (outside the form so it updates immediately)
st.subheader("Presets")
pc1, pc2, pc3 = st.columns([2, 1, 1])
with pc1:
    preset_name = st.selectbox("Select Preset", list(PRESETS.keys()), key="preset_select")
with pc2:
    if st.button("Load Preset"):
        apply_preset_to_session(PRESETS[preset_name])
        st.success(f"Loaded preset: {preset_name}")
        st.rerun()

# Strategy form
with st.form("strategy_form", clear_on_submit=False):
    st.subheader("Strategy Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        ema_fast = st.number_input("EMA Fast", 5, 100, value=sig.params.get("ema_fast", 20), key="ema_fast")
        ema_slow = st.number_input("EMA Slow", 10, 400, value=sig.params.get("ema_slow", 50), key="ema_slow")
    with col2:
        rsi_len = st.number_input("RSI Length", 5, 50, value=sig.params.get("rsi_length", 14), key="rsi_length")
        atr_len = st.number_input("ATR Length", 5, 100, value=sig.params.get("atr_length", 14), key="atr_length")
    with col3:
        rr_target = st.slider("Risk-Reward Target", 1.0, 3.0, value=float(sig.params.get("rr_target", 1.8)), step=0.1, key="rr_target")
        breakout_lookback = st.number_input("Breakout Lookback", 10, 200, value=sig.params.get("breakout_lookback", 55), key="breakout_lookback")

    st.subheader("Confidence Model Weights")
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        w_trend = st.slider("Trend Weight", 0.0, 1.0, value=float(sig.params.get("w_trend", 0.35)), step=0.05, key="w_trend")
    with col5:
        w_rsi = st.slider("RSI Weight", 0.0, 1.0, value=float(sig.params.get("w_rsi", 0.25)), step=0.05, key="w_rsi")
    with col6:
        w_macd = st.slider("MACD Weight", 0.0, 1.0, value=float(sig.params.get("w_macd", 0.25)), step=0.05, key="w_macd")
    with col7:
        w_breakout = st.slider("Breakout Weight", 0.0, 1.0, value=float(sig.params.get("w_breakout", 0.15)), step=0.05, key="w_breakout")

    with st.expander("Advanced Scoring Settings", expanded=False):
        ac1, ac2 = st.columns(2)
        with ac1:
            trend_use_atr = st.checkbox("Use ATR for Trend Normalization", value=bool(sig.params.get("trend_use_atr", True)), key="trend_use_atr")
            trend_k_atr = st.number_input("Trend k * ATR", 0.1, 5.0, value=float(sig.params.get("trend_k_atr", 1.5)), step=0.1, key="trend_k_atr")
            rsi_center = st.number_input("RSI Center", 40.0, 70.0, value=float(sig.params.get("rsi_center", 58.0)), step=1.0, key="rsi_center")
            rsi_width = st.number_input("RSI Width", 10.0, 60.0, value=float(sig.params.get("rsi_width", 30.0)), step=1.0, key="rsi_width")
        with ac2:
            trend_k_pct = st.number_input("Trend % of Price Fallback", 0.002, 0.1, value=float(sig.params.get("trend_k_pct", 0.02)), step=0.002, format="%.3f", key="trend_k_pct")
            macd_k_atr = st.number_input("MACD k * ATR", 0.1, 5.0, value=float(sig.params.get("macd_k_atr", 1.0)), step=0.1, key="macd_k_atr")
            macd_k_pct_close = st.number_input("MACD % of Price Fallback", 0.001, 0.05, value=float(sig.params.get("macd_k_pct_close", 0.01)), step=0.001, format="%.3f", key="macd_k_pct_close")

    with st.expander("Regime Weights (optional)", expanded=False):
        adx_trend_threshold = st.number_input("ADX Trend Threshold", 5.0, 50.0, value=float(sig.params.get("adx_trend_threshold", 20.0)), step=1.0, key="adx_trend_threshold")
        use_regime_weights = st.checkbox("Enable Regime-specific Weights", value=("weights_trending" in sig.params or "weights_ranging" in sig.params), key="use_regime_weights")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown("Trending Weights")
            wt_trend = st.slider("Trend (Trending)", 0.0, 1.0, value=float(sig.params.get("weights_trending", {}).get("trend", sig.params.get("w_trend", 0.35))), step=0.05, key="wt_trend")
            wt_rsi = st.slider("RSI (Trending)", 0.0, 1.0, value=float(sig.params.get("weights_trending", {}).get("rsi", sig.params.get("w_rsi", 0.25))), step=0.05, key="wt_rsi")
            wt_macd = st.slider("MACD (Trending)", 0.0, 1.0, value=float(sig.params.get("weights_trending", {}).get("macd", sig.params.get("w_macd", 0.25))), step=0.05, key="wt_macd")
            wt_breakout = st.slider("Breakout (Trending)", 0.0, 1.0, value=float(sig.params.get("weights_trending", {}).get("breakout", sig.params.get("w_breakout", 0.15))), step=0.05, key="wt_breakout")
        with rc2:
            st.markdown("Ranging Weights")
            wr_trend = st.slider("Trend (Ranging)", 0.0, 1.0, value=float(sig.params.get("weights_ranging", {}).get("trend", sig.params.get("w_trend", 0.35))), step=0.05, key="wr_trend")
            wr_rsi = st.slider("RSI (Ranging)", 0.0, 1.0, value=float(sig.params.get("weights_ranging", {}).get("rsi", sig.params.get("w_rsi", 0.25))), step=0.05, key="wr_rsi")
            wr_macd = st.slider("MACD (Ranging)", 0.0, 1.0, value=float(sig.params.get("weights_ranging", {}).get("macd", sig.params.get("w_macd", 0.25))), step=0.05, key="wr_macd")
            wr_breakout = st.slider("Breakout (Ranging)", 0.0, 1.0, value=float(sig.params.get("weights_ranging", {}).get("breakout", sig.params.get("w_breakout", 0.15))), step=0.05, key="wr_breakout")

    st.subheader("Allocation & Risk")
    col8, col9, col10 = st.columns(3)
    with col8:
        max_positions = st.number_input("Max Positions", 1, 20, value=port.config["max_positions"], key="max_positions")
    with col9:
        per_trade_risk = st.slider("Risk per Trade (%)", 0.1, 2.0, value=float(port.config["risk_per_trade_pct"]*100), step=0.1, key="risk_per_trade_pct_ui")
    with col10:
        max_leverage = st.slider("Max Leverage (Futures)", 1, 10, value=port.config["max_leverage"], key="max_leverage")

    save = st.form_submit_button("Save")
    if save:
        params_to_save = dict(
            ema_fast=ema_fast, ema_slow=ema_slow, rsi_length=rsi_len, atr_length=atr_len,
            rr_target=rr_target, breakout_lookback=breakout_lookback,
            w_trend=w_trend, w_rsi=w_rsi, w_macd=w_macd, w_breakout=w_breakout,
            # Advanced scoring
            trend_use_atr=trend_use_atr, trend_k_atr=trend_k_atr, trend_k_pct=trend_k_pct,
            rsi_center=rsi_center, rsi_width=rsi_width,
            macd_k_atr=macd_k_atr, macd_k_pct_close=macd_k_pct_close,
            adx_trend_threshold=adx_trend_threshold,
            # Regime weights (optional)
            weights_trending=dict(trend=wt_trend, rsi=wt_rsi, macd=wt_macd, breakout=wt_breakout) if use_regime_weights else None,
            weights_ranging=dict(trend=wr_trend, rsi=wr_rsi, macd=wr_macd, breakout=wr_breakout) if use_regime_weights else None,
        )
        sig.update_params(params_to_save)

        port.update_config(dict(
            max_positions=max_positions,
            risk_per_trade_pct=st.session_state["risk_per_trade_pct_ui"]/100.0,
            max_leverage=max_leverage
        ))
        st.success("Strategy and risk parameters updated.")