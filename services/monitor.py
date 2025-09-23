#Description: Monitoring service enforcing TP/SL and risk checks.

from threading import Lock
from datetime import datetime,timezone

from services.market_data import MarketDataService
from services.portfolio import PortfolioService
from models.db import get_session
from models.orm import Position
from utils.logging import logger

class MonitorService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.market = MarketDataService.instance()
        self.portfolio = PortfolioService.instance()
        self._kill = False
        self.config = {
            "max_daily_loss_pct": 10.0,
            "per_asset_cap_pct": 20.0,
            "correlation_cap": 0.8,
            "vol_spike_atr_mult": 3.0
        }
    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = MonitorService()
        return cls._instance

    def set_kill_switch(self, enabled: bool):
        self._kill = enabled
        self.portfolio.log_event("WARN", f"Kill Switch set to {enabled}")

    def update_config(self, cfg: dict):
        self.config.update(cfg)

    def get_status(self):
        return {"kill_switch": self._kill, "config": self.config}

    def monitor_once(self):
        # Update positions P&L and enforce TP/SL
        with get_session() as db:
            positions = db.query(Position).filter(Position.status == "open").all()
            for p in positions:
                last_price = self._get_last_price(p.symbol)
                if p.side.upper() == "BUY":
                    p.unrealized_pnl = (last_price - p.entry_price) * p.qty
                    hit_tp = p.tp and last_price >= p.tp
                    hit_sl = p.sl and last_price <= p.sl
                else:
                    p.unrealized_pnl = (p.entry_price - last_price) * p.qty
                    hit_tp = p.tp and last_price <= p.tp
                    hit_sl = p.sl and last_price >= p.sl
                if hit_tp or hit_sl:
                    p.status = "closed"; p.ts_close = datetime.now(timezone.utc)
                    self.portfolio.adjust_balance(p.market, delta=p.unrealized_pnl)
                    self.portfolio.log_event("INFO", f"Exit {p.symbol} {'TP' if hit_tp else 'SL'} @ {last_price:.6f} pnl={p.unrealized_pnl:.2f}")
            db.commit()
        # Record snapshot
        self.portfolio.record_snapshot()
        
    def _get_last_price(self, symbol: str) -> float:
        # Try tickers; else last candle
        tickers = self.market.get_tickers(limit=20)
        for t in tickers:
            if t["symbol"] == symbol:
                return float(t["last"])
        df = self.market.get_candles_df(symbol, "1h", limit=1)
        return float(df.iloc[-1]["close"]) if df is not None and len(df) else 0.0

