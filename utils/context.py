#Description: Simple app context singleton to share services and settings.

from dataclasses import dataclass
from utils.config import settings

@dataclass
class AppContext:
    mode: str = settings.MODE

_ctx: AppContext | None = None

def get_app_context() -> AppContext:
    global _ctx
    if _ctx is None:
        _ctx = AppContext()
    return _ctx
