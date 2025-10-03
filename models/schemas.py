#Description: Pydantic schemas representing signals and orders for cross-layer transport.

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class SignalOut(BaseModel):
    symbol: str
    market: str = "spot"
    timeframe: str
    ts: datetime
    strategy: str = "ensemble_v1"
    confidence: float
    expected_return_pct: float
    suggested_leverage: float | None = None
    entry: float
    tp: float
    sl: float
    side: str = "BUY"
    rationale: str = ""

class OrderOut(BaseModel):
    id: Optional[int] = None
    exchange_order_id: Optional[str] = None
    symbol: str
    market: str = "spot"
    side: str
    type: str = "market"
    qty: float
    price: float
    status: str = "new"
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    client_id: Optional[str] = None
