#Description: Background scheduler to run scans and monitoring periodically.
from apscheduler.schedulers.background import BackgroundScheduler

from utils.logging import logger
from utils.config import settings
from services.signals import SignalService
from services.monitor import MonitorService
from services.execution import ExecutionService
from services.portfolio import PortfolioService
from datetime import datetime

_scheduler: BackgroundScheduler | None = None

def scan_job():
    try:
        sig = SignalService.instance()
        exec = ExecutionService.instance()
        port = PortfolioService.instance()
        # Universe default top 20
        universe = sig.default_universe()[:20]
        signals = sig.scan_and_score(universe, timeframe="1h")
        # Auto execute if enabled
        if port._auto_trade:
            exec.allocate_and_execute([s for s in signals if s.confidence >= port._confidence_threshold])
    except Exception as e:
        logger.exception(f"Scan job failed: {e}")

def monitor_job():
    try:
        mon = MonitorService.instance()
        mon.monitor_once()
    except Exception as e:
        logger.exception(f"Monitor job failed: {e}")

def start_scheduler():
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(scan_job, "interval", seconds=settings.SCAN_INTERVAL_SECONDS, id="scan_job", max_instances=1, coalesce=True)
    _scheduler.add_job(monitor_job, "interval", seconds=settings.MONITOR_INTERVAL_SECONDS, id="monitor_job", max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("Scheduler started.")
    return _scheduler

def get_scheduler():
    return _scheduler
