#Description: Execution service for allocation and order placement (simulation or live adapters).
import uuid
from typing import List
from threading import Lock
from datetime import datetime,timezone

from utils.config import settings
from utils.logging import logger
from models.db import get_session
from models.orm import Order, Position
from models.schemas import SignalOut
from services.portfolio import PortfolioService
from adapters.coindcx_spot import CoinDCXSpotAdapter
from adapters.coindcx_futures import CoinDCXFuturesAdapter


class ExecutionService:
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.portfolio = PortfolioService.instance()
        self.spot = CoinDCXSpotAdapter()
        self.futures = CoinDCXFuturesAdapter()

    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = ExecutionService()
        return cls._instance

    def _allocation_amounts(self, signals: List[SignalOut]) -> dict:
        # Compute per-signal allocation using confidence * exp_return weighting, within spot/futures buckets
        total_equity = self.portfolio.get_equity()
        spot_budget = total_equity * settings.SPOT_ALLOCATION_PCT
        fut_budget = total_equity * settings.FUTURES_ALLOCATION_PCT

        spot_sigs = [s for s in signals if s.market == "spot"]
        fut_sigs = [s for s in signals if s.market == "futures"]

        def weights(sigs):
            raw = [max(0.0, s.confidence * max(0.0, s.expected_return_pct)) for s in sigs]
            tot = sum(raw) if sum(raw) > 0 else 1.0
            return [x / tot for x in raw]

        allocs = {}
        for sigs, budget in [(spot_sigs, spot_budget), (fut_sigs, fut_budget)]:
            ws = weights(sigs)
            for s, w in zip(sigs, ws):
                allocs[(s.symbol, s.market)] = budget * w
        return allocs

    def allocate_and_execute(self, signals: List[SignalOut]) -> dict:
        # Filter by confidence and max positions
        signals = [s for s in signals if s.confidence >= self.portfolio._confidence_threshold]
        signals = signals[: self.portfolio.config["max_positions"]]
        allocs = self._allocation_amounts(signals)

        placed = 0; skipped = 0; errors = 0
        for s in signals:
            try:
                amt = allocs.get((s.symbol, s.market), 0.0)
                if amt <= 0:
                    skipped += 1; continue
                qty = max(0.0, amt / s.entry)
                if s.market == "spot":
                    self._place_spot_order(s, qty)
                else:
                    self._place_futures_order(s, qty, leverage=settings.MAX_LEVERAGE)
                placed += 1
            except Exception as e:
                logger.exception(f"Order failed for {s.symbol}: {e}")
                errors += 1
        return {"orders_placed": placed, "skipped": skipped, "errors": errors}

    def _place_spot_order(self, s: SignalOut, qty: float):
        client_id = f"cli-{uuid.uuid4().hex[:10]}"
        # Simulation or live
        if settings.MODE in ("paper","dryrun"):
            with get_session() as db:
                order = Order(symbol=s.symbol, market="spot", side=s.side, qty=qty, price=s.entry, status="filled",
                              tp_price=s.tp, sl_price=s.sl, client_id=client_id, type="market")
                db.add(order)
                db.flush()
                pos = Position(symbol=s.symbol, market="spot", side=s.side, entry_price=s.entry, qty=qty, leverage=1,
                               sl=s.sl, tp=s.tp, status="open")
                db.add(pos)
                db.commit()
            self.portfolio.adjust_balance("spot", delta=-(qty * s.entry))
            self.portfolio.log_event("INFO", f"SIM SPOT BUY {s.symbol} qty={qty:.6f} @ {s.entry:.6f}")
        else:
            # Implement live order via adapter
            res = self.spot.place_market_order(symbol=s.symbol, side="buy", qty=qty, client_id=client_id)
            with get_session() as db:
                order = Order(symbol=s.symbol, market="spot", side="BUY", qty=qty, price=res.get("avg_price", s.entry),
                              status=res.get("status","filled"), exchange_order_id=res.get("order_id"), tp_price=s.tp, sl_price=s.sl, client_id=client_id)
                db.add(order)
                db.flush()
                pos = Position(symbol=s.symbol, market="spot", side="BUY", entry_price=order.price, qty=qty, leverage=1,
                               sl=s.sl, tp=s.tp, status="open")
                db.add(pos)
                db.commit()
            self.portfolio.log_event("INFO", f"LIVE SPOT BUY {s.symbol} qty={qty:.6f}")

    def _place_futures_order(self, s: SignalOut, qty: float, leverage: int):
        client_id = f"cli-{uuid.uuid4().hex[:10]}"
        eff_qty = qty * leverage
        if settings.MODE in ("paper","dryrun"):
            with get_session() as db:
                order = Order(symbol=s.symbol, market="futures", side=s.side, qty=eff_qty, price=s.entry, status="filled",
                              tp_price=s.tp, sl_price=s.sl, client_id=client_id, type="limit")
                db.add(order)
                db.flush()
                pos = Position(symbol=s.symbol, market="futures", side=s.side, entry_price=s.entry, qty=eff_qty, leverage=leverage,
                               sl=s.sl, tp=s.tp, status="open")
                db.add(pos)
                db.commit()
            # Deduct margin estimate
            margin = qty * s.entry / leverage
            self.portfolio.adjust_balance("futures", delta=-margin)
            self.portfolio.log_event("INFO", f"SIM FUT BUY {s.symbol} qty={eff_qty:.6f} lev={leverage} @ {s.entry:.6f}")
        else:
            res = self.futures.place_limit_order(symbol=s.symbol, side="buy", qty=eff_qty, price=s.entry, client_id=client_id, leverage=leverage)
            with get_session() as db:
                order = Order(symbol=s.symbol, market="futures", side="BUY", qty=eff_qty, price=s.entry,
                              status=res.get("status","new"), exchange_order_id=res.get("order_id"), tp_price=s.tp, sl_price=s.sl, client_id=client_id)
                db.add(order)
                db.flush()
                pos = Position(symbol=s.symbol, market="futures", side="BUY", entry_price=s.entry, qty=eff_qty, leverage=leverage,
                               sl=s.sl, tp=s.tp, status="open")
                db.add(pos)
                db.commit()
            self.portfolio.log_event("INFO", f"LIVE FUT BUY {s.symbol} qty={eff_qty:.6f}")

    def place_manual(self, symbol: str, side: str, qty: float, entry: float, tp: float, sl: float, market_type: str):
        s = SignalOut(symbol=symbol, market=market_type, timeframe="manual", ts=datetime.now(timezone.utc), confidence=1.0,
                      expected_return_pct=(tp-entry)/entry*100.0, entry=entry, tp=tp, sl=sl, side=side.upper(), rationale="Manual order")
        if market_type == "spot":
            self._place_spot_order(s, qty)
        else:
            self._place_futures_order(s, qty, leverage=settings.MAX_LEVERAGE)
        return {"status": "ok", "symbol": symbol}

    def close_all_positions(self):
        with get_session() as db:
            pos = db.query(Position).filter(Position.status == "open").all()
            for p in pos:
                p.status = "closed"; p.ts_close = datetime.now(timezone.utc)
            db.commit()
        return {"closed": len(pos)}

    def rebalance(self):
        # Placeholder
        return {"status": "ok", "message": "Rebalance logic not implemented yet."}
