#Description: Portfolio service managing balances, equity, positions, orders, events.
import pandas as pd
from datetime import datetime,timezone
from threading import Lock

from utils.logging import logger
from utils.config import settings
from models.db import get_session
from models.orm import Order, Position, PortfolioSnapshot, Alert
from models.schemas import SignalOut

class PortfolioService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.config = {
            "max_positions": 5,
            "risk_per_trade_pct": settings.RISK_PER_TRADE_PCT,
            "max_leverage": settings.MAX_LEVERAGE
        }
        # Simulation balances
        self._balances = {"spot_usdt": 10000.0, "futures_usdt": 5000.0}
        self._events: list[dict] = []
        self._auto_trade = False
        self._confidence_threshold = settings.CONFIDENCE_THRESHOLD

    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = PortfolioService()
        return cls._instance

    def log_event(self, level: str, message: str, context: dict | None = None):
        evt = {"ts": datetime.now().isoformat(timespec="seconds"), "level": level, "message": message, "context": context or {}}
        self._events.append(evt)
        # Persist minimal alert
        with get_session() as s:
            s.add(Alert(level=level, message=message, context=context or {}))
            s.commit()

    def set_auto_trade(self, enabled: bool):
        self._auto_trade = enabled

    def set_confidence_threshold(self, th: float):
        self._confidence_threshold = th

    def get_equity(self) -> float:
        return self._balances["spot_usdt"] + self._balances["futures_usdt"]

    def get_balances(self):
        return dict(self._balances)

    def adjust_balance(self, market: str, delta: float):
        key = "spot_usdt" if market == "spot" else "futures_usdt"
        self._balances[key] += delta

    def get_equity_curve(self) -> pd.DataFrame:
        with get_session() as s:
            snaps = s.query(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.asc()).all()
        if not snaps:
            return pd.DataFrame({"ts": [], "equity": []})
        return pd.DataFrame([{"ts": x.ts, "equity": x.equity} for x in snaps])

    def get_exposure_snapshot(self) -> pd.DataFrame:
        with get_session() as s:
            pos = s.query(Position).filter(Position.status == "open").all()
        d = {}
        for p in pos:
            d[p.symbol] = d.get(p.symbol, 0.0) + p.qty * p.entry_price
        items = [{"asset": k, "exposure": v} for k, v in d.items()]
        return pd.DataFrame(items)

    def get_open_positions_df(self) -> pd.DataFrame:
        with get_session() as s:
            pos = s.query(Position).filter(Position.status == "open").all()
        rows = []
        for p in pos:
            rows.append({
                "id": p.id, "symbol": p.symbol, "market": p.market, "side": p.side, "entry_price": p.entry_price,
                "qty": p.qty, "leverage": p.leverage, "sl": p.sl, "tp": p.tp, "unrealized_pnl": p.unrealized_pnl, "status": p.status
            })
        return pd.DataFrame(rows)

    def get_orders_df(self, limit=100) -> pd.DataFrame:
        with get_session() as s:
            orders = s.query(Order).order_by(Order.ts_created.desc()).limit(limit).all()
        rows = []
        for o in orders:
            rows.append({
                "id": o.id, "symbol": o.symbol, "market": o.market, "side": o.side, "qty": o.qty, "price": o.price,
                "status": o.status, "ts_created": o.ts_created, "tp": o.tp_price, "sl": o.sl_price
            })
        return pd.DataFrame(rows)

    def record_snapshot(self):
        eq = self.get_equity()
        with get_session() as s:
            s.add(PortfolioSnapshot(ts=datetime.now(timezone.utc), equity=eq, cash_spot=self._balances["spot_usdt"],
                                    cash_futures=self._balances["futures_usdt"], margin_used=0.0, exposure_json={}))
            s.commit()

    def get_recent_events(self, limit=20) -> list[dict]:
        return self._events[-limit:]
