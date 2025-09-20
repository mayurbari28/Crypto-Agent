#Description: Signal engine computing indicators and composite confidence; backtest utility.

import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
from threading import Lock
from utils.logging import logger
from models.schemas import SignalOut
from services.market_data import MarketDataService

class SignalService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.market = MarketDataService.instance()
        # Default parameters
        self.params = {
            "ema_fast": 20, "ema_slow": 50, "rsi_length": 14, "atr_length": 14,
            "rr_target": 1.8, "breakout_lookback": 55,
            "w_trend": 0.35, "w_rsi": 0.25, "w_macd": 0.25, "w_breakout": 0.15
        }
        self._logs = []

    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = SignalService()
        return cls._instance

    def default_universe(self):
        # Top universe placeholders (CoinDCX USDT pairs)
        return ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","SOLUSDT","MATICUSDT","DOTUSDT","LTCUSDT","TRXUSDT","LINKUSDT"]

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        p = self.params
        df = df.copy()
        df["ema_fast"] = ta.ema(df["close"], length=p["ema_fast"])
        df["ema_slow"] = ta.ema(df["close"], length=p["ema_slow"])
        df["rsi"] = ta.rsi(df["close"], length=p["rsi_length"])
        macd = ta.macd(df["close"])
        df["macd"] = macd["MACD_12_26_9"]
        df["macd_signal"] = macd["MACDs_12_26_9"]
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=p["atr_length"])
        df["breakout"] = (df["close"] >= df["close"].rolling(p["breakout_lookback"]).max()).astype(int)
        return df

    def score_row(self, row) -> float:
        p = self.params
        # Trend: EMA fast above slow and distance normalized
        trend = 0.0
        if row.get("ema_fast") and row.get("ema_slow"):
            trend = max(0.0, min(1.0, (row["ema_fast"] - row["ema_slow"]) / (0.02 * row["close"])))
        # RSI: prefer 50-65
        rsi = row.get("rsi") or 50.0
        rsi_score = max(0.0, 1.0 - abs(rsi - 60.0)/40.0)
        # MACD: above signal and positive
        macd, sig = row.get("macd") or 0.0, row.get("macd_signal") or 0.0
        macd_score = 1.0 if (macd > sig and macd > 0) else 0.0
        breakout = row.get("breakout") or 0
        # Weighted sum
        conf = p["w_trend"]*trend + p["w_rsi"]*rsi_score + p["w_macd"]*macd_score + p["w_breakout"]*breakout
        return float(max(0.0, min(1.0, conf)))

    def propose_targets(self, row) -> tuple[float, float]:
        # ATR-based SL; RR-based TP
        atr = row.get("atr") or 0.0
        entry = row["close"]
        sl = entry - 1.0 * atr
        tp = entry + self.params["rr_target"] * (entry - sl)
        # Bound SL not to drop below tiny positive
        sl = max(0.0000001, sl)
        return tp, sl

    def scan_and_score(self, universe: list[str], timeframe: str) -> list[SignalOut]:
        out: list[SignalOut] = []
        for symbol in universe:
            df = self.market.get_candles_df(symbol, timeframe, limit=400)
            df = self.compute_features(df)
            if df is None or df.empty:
                continue
            row = df.iloc[-1]
            conf = self.score_row(row)
            tp, sl = self.propose_targets(row)
            exp_ret_pct = (tp - row["close"]) / row["close"] * 100.0
            # Use spot for top pairs; map some to futures bucket alternately
            market = "spot" if hash(symbol) % 2 == 0 else "futures"
            sig = SignalOut(
                symbol=symbol, market=market, timeframe=timeframe, ts=pd.Timestamp(row["ts"]).to_pydatetime(),
                confidence=conf, expected_return_pct=exp_ret_pct, entry=row["close"], tp=tp, sl=sl, side="BUY",
                rationale=f"EMA trend: {row['ema_fast']:.2f}>{row['ema_slow']:.2f}, RSI: {row['rsi']:.1f}, MACD>Signal: {row['macd']>row['macd_signal']}."
            )
            out.append(sig)
        # Sort by confidence and expected return
        out.sort(key=lambda s: (s.confidence, s.expected_return_pct), reverse=True)
        self._logs.append(f"{datetime.utcnow()} Generated {len(out)} signals for tf={timeframe}")
        return out

    def quick_backtest(self, df: pd.DataFrame) -> dict:
        # Simple long-only: buy when score>0.7 and flat; exit on TP/SL or reverse
        df = self.compute_features(df)
        df["conf"] = df.apply(self.score_row, axis=1)
        df["tp"], df["sl"] = zip(*df.apply(self.propose_targets, axis=1))
        position = 0
        equity = 10000.0
        entry = 0.0
        units = 0.0
        eq_curve = []
        for i in range(2, len(df)):
            price = df.iloc[i]["close"]
            if position == 0 and df.iloc[i-1]["conf"] > 0.7:
                entry = price
                risk = equity * 0.01
                sl = df.iloc[i]["sl"]
                units = max(0.0, risk / max(1e-6, entry - sl))
                position = 1
            elif position == 1:
                tp = df.iloc[i]["tp"]
                sl = df.iloc[i]["sl"]
                if price >= tp or price <= sl:
                    pnl = (price - entry) * units
                    equity += pnl
                    position = 0
            eq_curve.append({"ts": df.iloc[i]["ts"], "equity": equity})
        summary = {
            "final_equity": equity,
            "return_pct": (equity/10000.0-1.0)*100.0,
            "trades": int((df["conf"]>0.7).sum()/2)
        }
        return {"equity_curve": pd.DataFrame(eq_curve), "summary": summary}

    def update_params(self, new_params: dict):
        self.params.update(new_params)
        self._logs.append(f"Params updated: {new_params}")

    def get_recent_logs(self, n=100):
        return self._logs[-n:]

