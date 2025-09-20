#Description: Minimal tests to verify core services run.

from services.signals import SignalService
from services.market_data import MarketDataService
from services.execution import ExecutionService
from services.monitor import MonitorService
from services.portfolio import PortfolioService

def test_signal_scan():
    sig = SignalService.instance()
    out = sig.scan_and_score(sig.default_universe()[:3], "1h")
    assert isinstance(out, list)
    assert len(out) > 0

def test_execution_sim():
    sig = SignalService.instance()
    ex = ExecutionService.instance()
    candidates = sig.scan_and_score(sig.default_universe()[:2], "1h")
    res = ex.allocate_and_execute(candidates[:1])
    assert "orders_placed" in res

def test_monitor():
    mon = MonitorService.instance()
    mon.monitor_once()
    port = PortfolioService.instance()
    assert isinstance(port.get_equity(), float)

#TODO MarketDataService imported but no test defined.