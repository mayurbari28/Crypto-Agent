#Description: Signal engine computing indicators and composite confidence; backtest utility.
from __future__ import annotations

import pandas as pd
import numpy as np
import pandas_ta as ta

from datetime import datetime,timezone,timedelta
from threading import Lock
from typing import Dict, Any, List

from utils.logging import logger
from models.schemas import SignalOut
from services.market_data import MarketDataService
from adapters.coindcx_common import CoinDCXBaseAdapter
from utils.config import settings

FALLBACK_UNIVERSE: List[str] = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    "SOLUSDT", "MATICUSDT", "DOTUSDT", "LTCUSDT", "TRXUSDT", "LINKUSDT",
]

class SignalService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.market = MarketDataService.instance()
        self.coindcx= CoinDCXBaseAdapter(settings.COINDCX_FUT_API_KEY, settings.COINDCX_FUT_API_SECRET)
        
        # cache dictionary with default values
        self._universe_cache = {
            "updated": datetime.min.replace(tzinfo=timezone.utc),
            "markets": []
        }

        # Default parameters aligned with the enhanced scoring model (BalancedDefault preset)
        self.params: Dict[str, Any] = {
            "ema_fast": 20,
            "ema_slow": 50,
            "rsi_length": 14,
            "atr_length": 14,
            "breakout_lookback": 55,
            "rr_target": 1.8,
            # Advanced scoring controls
            "trend_use_atr": True,
            "trend_k_atr": 1.5,
            "trend_k_pct": 0.02,
            "rsi_center": 58.0,
            "rsi_width": 30.0,
            "macd_k_atr": 1.0,
            "macd_k_pct_close": 0.01,
            "adx_trend_threshold": 20.0,
            "adx_length": 14,
            # Confidence weights
            "w_trend": 0.40,
            "w_rsi": 0.20,
            "w_macd": 0.25,
            "w_breakout": 0.15,
            # Optional regime-specific weights
            "weights_trending": {"trend": 0.42, "rsi": 0.18, "macd": 0.25, "breakout": 0.15},
            "weights_ranging": {"trend": 0.25, "rsi": 0.30, "macd": 0.20, "breakout": 0.25},
            # MACD lengths (kept configurable; defaults match pandas-ta)
            "macd_fast_length": 12,
            "macd_slow_length": 26,
            "macd_signal_length": 9,
        }
        self._logs = []


    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = SignalService()
        return cls._instance
    
    def get_universe(self) -> List[str]:
        """Return cached list of CoinDCX USDT markets, refreshing once per day."""
        now = datetime.now(timezone.utc)
        updated = self._universe_cache.get("updated", datetime.min.replace(tzinfo=timezone.utc))
        
        if now - updated > timedelta(days=1):
            try:
                response = self.coindcx.get("/exchange/v1/markets")
                symbols = [s for s in response if isinstance(s, str)]
                if symbols:
                    self._universe_cache = {"updated": now, "symbols": symbols}
                    logger.info("Default universe refreshed from CoinDCX API (%d symbols).", len(symbols))
                else:
                    logger.warning("CoinDCX API returned no USDT markets; keeping cached universe.")
            except Exception as exc:
                logger.warning("Unable to refresh CoinDCX universe: %s. Using cached list.", exc)

        return self._filter_markets_by_volume(self._universe_cache.get("symbols", FALLBACK_UNIVERSE))
    
    def _filter_markets_by_volume(
        self,
        symbols: List[str],
        min_notional_usd: float = 75_000.0,
    ) -> List[str]:
        """
        Filter a list of CoinDCX market symbols by 24h notional volume.

        Args:
            symbols: Markets (e.g., ["BTCUSDT", ...]) to evaluate.
            min_notional_usd: Minimum 24h notional volume (volume * last_price) required.

        Returns:
            The subset of symbols whose notional volume meets or exceeds the threshold. If the
            ticker feed cannot be retrieved, the original list is returned unfiltered.
        """
        try:
            resp = self.coindcx.get("/exchange/ticker")
            tickers = resp.json()
            ticker_map = {
                t.get("market"): t
                for t in tickers
                if isinstance(t, dict) and isinstance(t.get("market"), str)
            }
        except Exception as exc:
            logger.warning(
                "Volume filter skipped; unable to fetch CoinDCX ticker data: %s", exc
            )
            return symbols

        filtered: List[str] = []
        for market in symbols:
            ticker = ticker_map.get(market)
            if not ticker:
                continue
            try:
                volume = float(ticker.get("volume", 0.0))
                last_price = float(ticker.get("last_price", 0.0))
            except (TypeError, ValueError):
                continue
            if volume * last_price >= min_notional_usd:
                filtered.append(market)

        return filtered
        
    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical features used by the scoring model."""
        if df is None or df.empty:
            return df

        p = self.params
        df = df.copy()

        ema_fast_len = int(p.get("ema_fast", 20))
        ema_slow_len = int(p.get("ema_slow", 50))
        rsi_len = int(p.get("rsi_length", 14))
        atr_len = int(p.get("atr_length", 14))
        breakout_lb = max(1, int(p.get("breakout_lookback", 55)))
        adx_len = int(p.get("adx_length", atr_len))

        macd_fast = int(p.get("macd_fast_length", 12))
        macd_slow = int(p.get("macd_slow_length", 26))
        macd_signal = int(p.get("macd_signal_length", 9))
        macd_cols_prefix = f"{macd_fast}_{macd_slow}_{macd_signal}"

        df["ema_fast"] = ta.ema(df["close"], length=ema_fast_len)
        df["ema_slow"] = ta.ema(df["close"], length=ema_slow_len)

        df["rsi"] = ta.rsi(df["close"], length=rsi_len)

        macd = ta.macd(
            df["close"],
            fast=macd_fast,
            slow=macd_slow,
            signal=macd_signal,
        )
        df["macd"] = macd[f"MACD_{macd_cols_prefix}"]
        df["macd_signal"] = macd[f"MACDs_{macd_cols_prefix}"]

        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=atr_len)

        # Optional helper: ATR as % of close (used by some downstream analytics)
        df["atr_pct"] = df["atr"] / df["close"]

        # Breakout: Donchian-style highest close over the lookback window
        df["breakout"] = (
            df["close"] >= df["close"].rolling(breakout_lb, min_periods=1).max()
        ).astype(int)

        # ADX for regime detection (trending vs ranging)
        adx = ta.adx(df["high"], df["low"], df["close"], length=adx_len)
        df["adx"] = adx[f"ADX_{adx_len}"]

        return df    
    
    def score_row(self, row) -> float:
        p = self.params
        close = float(row.get("close") or 0.0)

        # -----------------------
        # Trend: EMA fast above slow, normalized (prefer ATR; fallback to % of price)
        # -----------------------
        trend = 0.0
        ema_fast = row.get("ema_fast")
        ema_slow = row.get("ema_slow")
        atr = row.get("atr")  # expected in price units; if absent we fallback to pct-of-price
        if ema_fast is not None and ema_slow is not None and close > 0:
            use_atr = bool(p.get("trend_use_atr", True))
            if use_atr and atr:
                denom = max(1e-12, float(p.get("trend_k_atr", 1.5)) * float(atr))
            else:
                denom = max(1e-12, float(p.get("trend_k_pct", 0.02)) * close)  # fallback: 2% of price
            trend_raw = (float(ema_fast) - float(ema_slow)) / denom
            trend = max(0.0, min(1.0, trend_raw))  # bullish-only score

        # -----------------------
        # RSI: prefer mildly bullish range with tighter window (configurable)
        # -----------------------
        rsi = float(row.get("rsi") if row.get("rsi") is not None else 50.0)
        rsi_center = float(p.get("rsi_center", 58.0))
        rsi_width = float(p.get("rsi_width", 30.0))  # narrower than 40 → crisper preference
        rsi_score = max(0.0, 1.0 - abs(rsi - rsi_center) / max(1e-12, rsi_width))

        # -----------------------
        # MACD: continuous momentum confirmation normalized by ATR (bullish-only)
        # -----------------------
        macd = row.get("macd")
        macd_sig = row.get("macd_signal")
        macd_score = 0.0
        if macd is not None and macd_sig is not None and close > 0:
            macd = float(macd)
            macd_sig = float(macd_sig)
            if atr:
                denom = max(1e-12, float(p.get("macd_k_atr", 1.0)) * float(atr))
            else:
                # fallback: normalize by % of price if ATR missing
                denom = max(1e-12, float(p.get("macd_k_pct_close", 0.01)) * close)  # ~1% of price
            edge = (macd - macd_sig) / denom
            macd_score = max(0.0, min(1.0, edge)) if macd > 0.0 else 0.0

        # -----------------------
        # Breakout: direct feature (0/1 or scaled), use as-is
        # -----------------------
        breakout = float(row.get("breakout") or 0.0)

        # -----------------------
        # Weights: regime-aware if ADX present, else defaults; normalize weights sum
        # -----------------------
        w_default = {
            "trend": float(p.get("w_trend", 0.35)),
            "rsi": float(p.get("w_rsi", 0.25)),
            "macd": float(p.get("w_macd", 0.25)),
            "breakout": float(p.get("w_breakout", 0.15)),
        }
        weights = w_default
        adx = row.get("adx")
        adx_thresh = float(p.get("adx_trend_threshold", 20.0))
        if adx is not None:
            if float(adx) >= adx_thresh and isinstance(p.get("weights_trending"), dict):
                weights = p["weights_trending"]
            elif float(adx) < adx_thresh and isinstance(p.get("weights_ranging"), dict):
                weights = p["weights_ranging"]

        # Ensure weight keys exist and normalize total
        w_trend = float(weights.get("trend", w_default["trend"]))
        w_rsi = float(weights.get("rsi", w_default["rsi"]))
        w_macd = float(weights.get("macd", w_default["macd"]))
        w_breakout = float(weights.get("breakout", w_default["breakout"]))
        w_sum = w_trend + w_rsi + w_macd + w_breakout
        if w_sum <= 0:
            w_sum = 1.0

        conf = (w_trend * trend + w_rsi * rsi_score + w_macd * macd_score + w_breakout * breakout) / w_sum
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
        self._logs.append(f"{datetime.now(timezone.utc)} Generated {len(out)} signals for tf={timeframe}")
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

    def update_params(self, updates: Dict[str, Any]) -> None:
        """Merge incoming updates into params, pruning None regime weights."""
        self.params.update(updates or {})
        # Drop regime weights if explicitly disabled (saved as None)
        if self.params.get("weights_trending") is None:
            self.params.pop("weights_trending", None)
        if self.params.get("weights_ranging") is None:
            self.params.pop("weights_ranging", None)


    def get_recent_logs(self, n=100):
        return self._logs[-n:]

