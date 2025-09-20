#Description: Detailed live dashboard with balances, tickers, and charts.
import streamlit as st
import pandas as pd

from services.portfolio import PortfolioService
from services.market_data import MarketDataService
from utils.charts import mini_price_chart

st.title("Dashboard (Live)")

portfolio = PortfolioService.instance()
market = MarketDataService.instance()

col1, col2, col3 = st.columns(3)
with col1:
    b = portfolio.get_balances()
    st.metric("Spot Balance (USDT)", f"{b.get('spot_usdt', 0):,.2f}")
with col2:
    st.metric("Futures Balance (USDT)", f"{b.get('futures_usdt', 0):,.2f}")
with col3:
    st.metric("Equity (USDT)", f"{portfolio.get_equity():,.2f}")

st.divider()

st.subheader("Live Tickers (Top)")
tickers = market.get_tickers(limit=10)
cols = st.columns(len(tickers))
for i, t in enumerate(tickers):
    with cols[i]:
        st.caption(t["symbol"])
        st.metric(label="", value=f'{t["last"]:.4f}', delta=f'{t["change_pct"]:.2f}%')

st.divider()
st.subheader("Mini Charts")
symbols = [t["symbol"] for t in tickers]
tabs = st.tabs(symbols)
for i, sym in enumerate(symbols):
    with tabs[i]:
        df = market.get_candles_df(sym, "1h", limit=200)
        st.plotly_chart(mini_price_chart(df, sym), use_container_width=True)
