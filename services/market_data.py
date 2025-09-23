#Description: Market data service using CoinDCX public ticker; candles via CSV fallback and synthetic if needed.

import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from functools import lru_cache
from threading import Lock
from utils.logging import logger
from pathlib import Path

class MarketDataService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.client = httpx.Client(timeout=10)
        self.csv_dir = Path(__file__).resolve().parents[2] / "data"
        self.csv_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = MarketDataService()
        return cls._instance

    def get_tickers(self, limit: int = 10):
        try:
            r = self.client.get("https://api.coindcx.com/exchange/ticker")
            arr = r.json()
            # Normalize to USDT quote and sort by volume or price change
            df = pd.DataFrame(arr)
            # Fallback if fields differ by API updates
            if "change_24_hour_percentage" in df.columns:
                df["change_pct"] = df["change_24_hour_percentage"].astype(float)
            else:
                df["change_pct"] = 0.0
            if "last_price" in df.columns:
                df["last"] = df["last_price"].astype(float)
            elif "last_trade_price" in df.columns:
                df["last"] = df["last_trade_price"].astype(float)
            else:
                df["last"] = 0.0
            df = df[df["market"].str.contains("USDT")]
            df = df.sort_values("change_pct", ascending=False).head(limit)
            out = [{"symbol": row["market"], "last": row["last"], "change_pct": row["change_pct"]} for _, row in df.iterrows()]
            return out
        except Exception as e:
            logger.warning(f"Ticker fetch failed: {e}")
            # Return a synthetic minimal set
            # TODO learn
            return [{"symbol":"BTCUSDT","last":60000.0,"change_pct":0.0}, {"symbol":"ETHUSDT","last":3000.0,"change_pct":0.0}]
        
    def _load_csv(self, symbol: str, timeframe: str) -> pd.DataFrame | None:
        fname = f"{symbol}_{timeframe}.csv"
        fpath = self.csv_dir / fname
        if fpath.exists():
            df = pd.read_csv(fpath)
            df["ts"] = pd.to_datetime(df["ts"])
            return df
        return None

    def get_candles_df(self, symbol: str, timeframe: str, limit: int = 300, source: str = "auto") -> pd.DataFrame:
        # Try CSV
        if source in ("csv","auto"):
            df = self._load_csv(symbol, timeframe)
            if df is not None:
                return df.tail(limit).copy()

        # Synthetic fallback: random walk (for demos)
        end = datetime.now()
        if timeframe.endswith("m"):
            minutes = int(timeframe.replace("m",""))
            delta = timedelta(minutes=minutes)
        elif timeframe.endswith("h"):
            hours = int(timeframe.replace("h",""))
            delta = timedelta(hours=hours)
        elif timeframe.endswith("d"):
            days = int(timeframe.replace("d",""))
            delta = timedelta(days=days)
        else:
            delta = timedelta(hours=1)

        ts = [end - i*delta for i in range(limit)][::-1]
        price0 = 100.0 if symbol.endswith("USDT") else 50.0
        rng = np.random.default_rng(abs(hash(symbol+timeframe)) % (2**32))
        steps = rng.normal(0, 1, size=limit).cumsum()
        close = price0 + steps
        high = close + rng.random(size=limit)
        low = close - rng.random(size=limit)
        openp = close + rng.normal(0, 0.5, size=limit)
        vol = rng.random(size=limit) * 1000
        df = pd.DataFrame({"ts": ts, "open": openp, "high": high, "low": low, "close": close, "volume": vol})
        return df

