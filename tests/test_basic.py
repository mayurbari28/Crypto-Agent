#Description: Minimal tests to verify core services run.

from services.signals import SignalService
from services.market_data import MarketDataService
from services.execution import ExecutionService
from services.monitor import MonitorService
from services.portfolio import PortfolioService
from utils.config import settings
from models.orm import Base

import pytest
from sqlalchemy import create_engine



def test_signal_scan():
    sig = SignalService.instance()
    out = sig.scan_and_score(sig.get_universe()[:3], "1h")
    assert isinstance(out, list)
    assert len(out) > 0

def test_execution_sim():
    sig = SignalService.instance()
    ex = ExecutionService.instance()
    candidates = sig.scan_and_score(sig.get_universe()[:2], "1h")
    res = ex.allocate_and_execute(candidates[:1])
    assert "orders_placed" in res

def test_monitor():
    mon = MonitorService.instance()
    mon.monitor_once()
    port = PortfolioService.instance()
    assert isinstance(port.get_equity(), float)

#TODO MarketDataService imported but no test defined.

@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    engine = create_engine(settings.DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
