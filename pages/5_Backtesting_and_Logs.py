#Description: Quick backtesting with included sample data; displays metrics and logs.

import streamlit as st
#import pandas as pd
from services.signals import SignalService
from services.market_data import MarketDataService
from utils.charts import backtest_equity_chart

st.title("Backtesting & Logs")

sig = SignalService.instance()
market = MarketDataService.instance()

col1, col2 = st.columns(2)
with col1:
    symbol = st.selectbox("Symbol", options=["BTCUSDT","ETHUSDT"])
with col2:
    timeframe = st.selectbox("Timeframe", options=["1h","4h","1d"], index=1)

run = st.button("Run Backtest")
if run:
    df = market.get_candles_df(symbol, timeframe, source="csv", limit=1000)
    bt = sig.quick_backtest(df)
    st.plotly_chart(backtest_equity_chart(bt["equity_curve"]), use_container_width=True)
    st.write("Summary")
    st.json(bt["summary"])

st.subheader("System Logs")

for line in sig.get_recent_logs(100):
    st.write(line)
