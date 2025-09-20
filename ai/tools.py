#Description: CrewAI tools for features, regime classification, risk overlays, and JSON parsing.

from __future__ import annotations
import json
from typing import Dict, Any, List, Tuple
import numpy as np

from services.market_data import MarketDataService
from services.signals import SignalService
from utils.logging import logger

class FeatureTool:
    """
    Provides latest features for a symbol/timeframe using the existing SignalService feature engine.
    """
    def __init__(self):
        self.market = MarketDataService.instance()
        self.signals = SignalService.instance()

    def latest_features(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        df = self.market.get_candles_df(symbol, timeframe, limit=400)
        df = self.signals.compute_features(df)
        if df is None or df.empty:
            return {}
        row = df.iloc[-1]
        # Propose targets with current parameterization to derive RR
        tp, sl = self.signals.propose_targets(row)
        entry = float(row["close"])
        rr = float((tp - entry) / max(1e-9, entry - sl))
        atr_ratio = float((row.get("atr") or 0.0) / max(1e-9, entry))
        ema_fast = float(row.get("ema_fast") or 0.0)
        ema_slow = float(row.get("ema_slow") or 0.0)
        trend_strength = float((ema_fast - ema_slow) / max(1e-9, 0.02 * entry))  # normalized
        rsi = float(row.get("rsi") or 50.0)
        macd = float(row.get("macd") or 0.0)
        macd_signal = float(row.get("macd_signal") or 0.0)
        breakout = int(row.get("breakout") or 0)

        return {
            "price": entry,
            "tp": float(tp),
            "sl": float(sl),
            "rr": rr,
            "atr": float(row.get("atr") or 0.0),
            "atr_ratio": atr_ratio,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "trend_strength": trend_strength,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "breakout": breakout,
        }


class RegimeTool:
    """
    Computes a simple market regime based on BTCUSDT 4h features:
    - Trend strength (EMA difference normalized)
    - RSI anchor
    - Volatility bucket via ATR ratio
    """
    def __init__(self):
        self.features = FeatureTool()

    def get_regime(self, base_symbol: str = "BTCUSDT", timeframe: str = "4h") -> Dict[str, Any]:
        f = self.features.latest_features(base_symbol, timeframe)
        if not f:
            return {"label": "unknown", "trend_strength": 0.0, "volatility": "med"}
        trend = float(f.get("trend_strength", 0.0))
        rsi = float(f.get("rsi", 50.0))
        atr_ratio = float(f.get("atr_ratio", 0.02))

        if trend > 0.2 and rsi > 55:
            label = "bullish"
        elif trend < -0.2 and rsi < 45:
            label = "bearish"
        else:
            label = "sideways"

        if atr_ratio < 0.02:
            vol = "low"
        elif atr_ratio < 0.05:
            vol = "med"
        else:
            vol = "high"

        return {"label": label, "trend_strength": trend, "rsi": rsi, "volatility": vol, "atr_ratio": atr_ratio}


class RiskTool:
    """
    Applies risk-based adjustments to confidence and collects human-readable reasons.
    """
    def confidence_adjustment(self, signal, features: Dict[str, Any], regime: Dict[str, Any]) -> Tuple[float, List[str]]:
        delta = 0.0
        reasons: List[str] = []

        atr_ratio = float(features.get("atr_ratio", 0.02))
        rsi = float(features.get("rsi", 50.0))
        trend = float(features.get("trend_strength", 0.0))
        breakout = bool(features.get("breakout", 0) == 1)
        rr = float(features.get("rr", 1.5))
        reg_label = regime.get("label", "unknown")
        vol_bucket = regime.get("volatility", "med")

        # Volatility penalties
        if atr_ratio > 0.06:
            delta -= 0.10
            reasons.append("ATR high")
        elif atr_ratio > 0.04:
            delta -= 0.05
            reasons.append("ATR elevated")

        # RSI extremes
        if rsi >= 80:
            delta -= 0.08; reasons.append("RSI overbought")
        elif rsi >= 70:
            delta -= 0.04; reasons.append("RSI hot")
        elif rsi <= 25:
            delta -= 0.05; reasons.append("RSI oversold")

        # Trend alignment bonus
        if trend > 0.3 and signal.side.upper() == "BUY":
            delta += 0.03; reasons.append("Trend aligned")

        # Breakout bonus (minor)
        if breakout:
            delta += 0.02; reasons.append("Breakout")

        # Regime alignment
        if reg_label == "bullish" and signal.side.upper() == "BUY":
            delta += 0.02; reasons.append("Bull regime")
        if reg_label == "bearish" and signal.side.upper() == "BUY":
            delta -= 0.03; reasons.append("Bear regime")

        # Risk/Reward sanity
        if rr < 1.2:
            delta -= 0.05; reasons.append("RR weak")
        elif rr > 2.5:
            delta += 0.01; reasons.append("RR strong")

        # Clamp conservative bounds
        delta = max(-0.15, min(0.10, delta))
        return delta, reasons


class JsonTool:
    """
    Safely parse JSON from LLM text output. Accepts raw JSON or text with JSON fenced blocks.
    """
    @staticmethod
    def parse_json_from_text(text: str) -> Dict[str, Any]:
        # try exact JSON
        try:
            return json.loads(text)
        except Exception:
            pass
        # Try to extract a fenced or inline JSON object
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end+1])
        except Exception:
            pass
        return {}