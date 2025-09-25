#Description: Market data service using CoinDCX public ticker; candles via CSV fallback and synthetic if needed.

import httpx
import pandas as pd
import numpy as np
from typing import Optional,Tuple,Dict,Any,List

from datetime import datetime, timedelta
from functools import lru_cache
from threading import Lock
from pathlib import Path

from sympy import true

from utils.logging import logger
from adapters.coindcx_common import CoinDCXBaseAdapter
from utils.config import settings

class MarketDataService:
    _instance = None
    _lock = Lock()
    # reuse one session and cache for speed
    _cg_coins_cache: Optional[List[Dict[str, Any]]] = None
    _coindcx_markets_cache: Optional[List[Dict[str, Any]]] = None

    def __init__(self):
        self.client = httpx.Client(timeout=10)
        self.csv_dir = Path(__file__).resolve().parents[2] / "data"
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.coindcx= CoinDCXBaseAdapter(settings.COINDCX_FUT_API_KEY, settings.COINDCX_FUT_API_SECRET)

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

    #Source hardcoded to coindcx 
    def get_candles_df(self, symbol: str, timeframe: str, limit: int = 300, source: str = "coindcx") -> pd.DataFrame:
        # 1) CSV fast-path
        if source in ("csv", "auto"):
            df = self._load_csv(symbol, timeframe)
            if df is not None and not df.empty:
                return df.tail(limit).copy()

        # 2) Try live APIs based on source preference
        errors = []

        if source in ("coindcx", "auto"):
            try:
                df = self._fetch_coindcx_candles(symbol, timeframe, limit)
                if df is not None and not df.empty:
                    return df.tail(limit).copy()
            except Exception as e:
                errors.append(f"CoinDCX error: {e}")
        
        # if source in ("coingecko", "auto"):

        # 3) Fallback: synthetic random-walk (demo only)
        df = self._generate_demo_candles(symbol,timeframe,limit)
    
        if errors:
            df.attrs["warnings"] = errors
        return df
    # -----------------------
    # CoinDCX
    # -----------------------
    def _fetch_coindcx_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        pair = self._coindcx_resolve_pair(symbol)
        interval = self._coindcx_interval(timeframe)

        data = self.coindcx.get(
            "/market_data/candles",
            params={"pair": pair, "interval": interval, "limit": int(limit)},
            public=True,
        )
        if not isinstance(data, list) or not data:
            raise ValueError("CoinDCX returned empty candles")

        # Common CoinDCX payload shape: [{'t': 1716947100000, 'o': '...', 'h': '...', 'l': '...', 'c': '...', 'v': '...'}, ...]
        # Convert to DataFrame
        records = []
        for row in data:
            t = row.get("t") or row.get("time")
            o = row.get("o") or row.get("open")
            h = row.get("h") or row.get("high")
            l = row.get("l") or row.get("low")
            c = row.get("c") or row.get("close")
            v = row.get("v") or row.get("volume")
            if t is None or o is None or h is None or l is None or c is None:
                continue
            records.append(
                {
                    "ts": pd.to_datetime(int(t), unit="ms", utc=True),
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v) if v is not None else float("nan"),
                }
            )

        if not records:
            raise ValueError("CoinDCX: No valid candle rows after parsing")

        df = pd.DataFrame(records).sort_values("ts").reset_index(drop=True)
        return df

    def _coindcx_interval(self, timeframe: str) -> str:
        # CoinDCX commonly supports: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 1d, 1w, 1M
        tf = timeframe.lower()
        supported = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"}
        if tf in supported:
            return tf
        # Fallback best-effort mapping
        td = self._parse_timeframe_to_timedelta(tf)
        mins = int(td.total_seconds() // 60)
        if mins < 2: return "1m"
        if mins <= 5: return "5m"
        if mins <= 15: return "15m"
        if mins <= 30: return "30m"
        hrs = mins // 60
        if hrs <= 1: return "1h"
        if hrs <= 2: return "2h"
        if hrs <= 4: return "4h"
        if hrs <= 6: return "6h"
        if hrs <= 8: return "8h"
        if hrs <= 12: return "12h"
        days = hrs // 24
        if days <= 1: return "1d"
        if days <= 3: return "3d"
        if days <= 7: return "1w"
        return "1M"

    def _coindcx_resolve_pair(self, symbol: str) -> str:
        # Accepts:
        # - "BTCUSDT", "BTC/USDT", "BTC-USDT", "BTC_USDT", or a raw CoinDCX pair like "BTC_USDT"
        s = symbol.strip().upper()
        # If user already passed a CoinDCX-style pair, try to use it directly
        if "_" in s and s.replace("_", "").isalnum():
            return s

        base, quote = self._split_base_quote(s)
        if not base or not quote:
            raise ValueError(f"Cannot parse symbol '{symbol}' into base/quote")

        # Try cached market list first
        markets = self._get_coindcx_markets_cache()
        # Look for exact base/quote short names
        for m in markets:
            b = (m.get("target_currency_short_name") or m.get("base_currency") or "").upper()
            q = (m.get("base_currency_short_name") or m.get("target_currency") or "").upper()
            if b == base and q == quote:
                # Prefer coindcx_name if present; otherwise compose base_quote
                return m.get("pair") or f"{base}_{quote}"

        # Fallback guess
        return f"{base}_{quote}"

    def _get_coindcx_markets_cache(self) -> List[Dict[str, Any]]:
        if self._coindcx_markets_cache is not None:
            return self._coindcx_markets_cache
        try:
            data = self.coindcx.get("/exchange/v1/markets_details")
            if isinstance(data, list) and data:
                self._coindcx_markets_cache = data
        except Exception:
            self._coindcx_markets_cache = []
        return self._coindcx_markets_cache

    def _parse_timeframe_to_timedelta(self, tf: str) -> timedelta:
        tf = tf.strip().lower()
        if tf.endswith("ms"):
            return timedelta(milliseconds=int(tf[:-2]))
        if tf.endswith("s"):
            return timedelta(seconds=int(tf[:-1]))
        if tf.endswith("m"):
            return timedelta(minutes=int(tf[:-1]))
        if tf.endswith("h"):
            return timedelta(hours=int(tf[:-1]))
        if tf.endswith("d"):
            return timedelta(days=int(tf[:-1]))
        if tf.endswith("w"):
            return timedelta(weeks=int(tf[:-1]))
        if tf.endswith("mo") or tf.endswith("mon") or tf.endswith("month"):
            # approximate month = 30 days
            num = int("".join(ch for ch in tf if ch.isdigit()) or "1")
            return timedelta(days=30 * num)
        if tf.endswith("y"):
            num = int(tf[:-1])
            return timedelta(days=365 * num)
        # default 1h
        return timedelta(hours=1)

    # -----------------------
    # Utilities
    # -----------------------
    def _split_base_quote(self, symbol: str) -> Tuple[Optional[str], Optional[str]]:
        s = symbol.strip().upper()
        # Handle common separators
        for sep in ["/", "-", "_"]:
            if sep in s:
                base, quote = s.split(sep, 1)
                return base, quote
        # No separator: try to split by known quote tokens
        known_quotes = ["USDT", "USDC", "BUSD", "BTC", "ETH", "INR", "USD", "EUR"]
        for q in known_quotes:
            if s.endswith(q) and len(s) > len(q):
                return s[: -len(q)], q
        return None, None

    # -----------------------
    # Generate Demo(Test) data
    # -----------------------

    def _generate_demo_candles(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
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
