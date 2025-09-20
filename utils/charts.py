#Description: Plotly chart helpers.

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
#TODO check
from services.market_data import MarketDataService

def equity_chart(df: pd.DataFrame):
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Scatter(x=df["ts"], y=df["equity"], mode="lines", name="Equity"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def exposure_pie(df: pd.DataFrame):
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Pie(labels=df["asset"], values=df["exposure"], hole=0.4))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def positions_table(df: pd.DataFrame):
    return df

def mini_price_chart(df: pd.DataFrame, symbol: str):
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Candlestick(x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name=symbol))
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
    return fig

def backtest_equity_chart(df: pd.DataFrame):
    fig = go.Figure()
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Scatter(x=df["ts"], y=df["equity"], mode="lines", name="Backtest Equity"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10))
    return fig

def signal_chart(signal):
    mkt = MarketDataService.instance()
    df = mkt.get_candles_df(signal.symbol, signal.timeframe, limit=400)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    if df is None or df.empty:
        return fig
    fig.add_trace(go.Candlestick(x=df["ts"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name=signal.symbol), row=1, col=1)
    fig.add_hline(y=signal.entry, line_color="blue", annotation_text="Entry", row=1, col=1)
    fig.add_hline(y=signal.tp, line_color="green", annotation_text="TP", row=1, col=1)
    fig.add_hline(y=signal.sl, line_color="red", annotation_text="SL", row=1, col=1)
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df["ts"], y=df["rsi"], name="RSI"), row=2, col=1)
        fig.add_hrect(y0=30, y1=70, fillcolor="lightgray", opacity=0.2, line_width=0, row=2, col=1)
    fig.update_layout(height=500, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
    return fig
