#Description: ORM entity definitions.

from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, DateTime, JSON, ForeignKey, Boolean
from datetime import datetime

#TODO check Base.metadata.create_all(bind=engine) <= orm.py
Base = declarative_base()

class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, index=True)
    market: Mapped[str] = mapped_column(String)  # spot|futures
    base: Mapped[str] = mapped_column(String)
    quote: Mapped[str] = mapped_column(String)
    tick_size: Mapped[float] = mapped_column(Float, default=0.0001)
    lot_size: Mapped[float] = mapped_column(Float, default=0.0001)
    min_notional: Mapped[float] = mapped_column(Float, default=1.0)
    leverage_max: Mapped[int] = mapped_column(Integer, default=3)

class Candle(Base):
    __tablename__ = "candles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    timeframe: Mapped[str] = mapped_column(String)
    ts_open: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)

class FeatureSnapshot(Base):
    __tablename__ = "feature_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    timeframe: Mapped[str] = mapped_column(String)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    features: Mapped[dict] = mapped_column(JSON)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    market: Mapped[str] = mapped_column(String, default="spot")
    timeframe: Mapped[str] = mapped_column(String)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    strategy: Mapped[str] = mapped_column(String, default="ensemble_v1")
    confidence: Mapped[float] = mapped_column(Float)
    expected_return_pct: Mapped[float] = mapped_column(Float)
    entry: Mapped[float] = mapped_column(Float)
    tp: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    side: Mapped[str] = mapped_column(String, default="BUY")
    rationale: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="new")  # new/approved/ordered

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exchange_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    market: Mapped[str] = mapped_column(String, default="spot")
    side: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="market")
    qty: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="new")  # new/filled/partial/canceled
    ts_created: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ts_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sl_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False)
    client_id: Mapped[str | None] = mapped_column(String, nullable=True)

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, index=True)
    market: Mapped[str] = mapped_column(String, default="spot")
    side: Mapped[str] = mapped_column(String, default="BUY")
    entry_price: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    leverage: Mapped[int] = mapped_column(Integer, default=1)
    sl: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp: Mapped[float | None] = mapped_column(Float, nullable=True)
    ts_open: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ts_close: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open/closed

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    equity: Mapped[float] = mapped_column(Float)
    cash_spot: Mapped[float] = mapped_column(Float)
    cash_futures: Mapped[float] = mapped_column(Float)
    margin_used: Mapped[float] = mapped_column(Float)
    exposure_json: Mapped[dict] = mapped_column(JSON)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    level: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    context: Mapped[dict] = mapped_column(JSON)

class ApiCredentials(Base):
    __tablename__ = "api_credentials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String)  # spot|futures
    key_id: Mapped[str] = mapped_column(String)
    encrypted_secret: Mapped[str] = mapped_column(String)
    permissions: Mapped[dict] = mapped_column(JSON, default={})
