#Description: Futures adapter (stubbed); ensure leverage parameter handling.

from adapters.coindcx_common import CoinDCXBaseAdapter
from utils.logging import logger
from utils.config import settings

import time

class CoinDCXFuturesAdapter(CoinDCXBaseAdapter):
    def __init__(self):
        super().__init__(settings.COINDCX_FUT_API_KEY, settings.COINDCX_FUT_API_SECRET)

    def test_connectivity(self):
        try:
            # If public futures tickers exist; fallback to spot tickers
            tick = self.get("/exchange/ticker", public=True)
            return True, f"Tickers: {len(tick)} items"
        except Exception as e:
            return False, f"Connectivity failed: {e}"

    def place_limit_order(self, symbol: str, side: str, qty: float, price: float, client_id: str, leverage: int = 1):
        payload = {
            "side": side.upper(), "order_type": "limit", "market": symbol,
            "price_per_unit": price, "total_quantity": qty, "timestamp": int(time.time() * 1000),
            "client_order_id": client_id, "leverage": leverage
        }
        if settings.MODE != "live":
            return {"status": "new", "order_id": "SIM-"+client_id}
        try:
            res = self.post("/exchange/v1/futures/orders/create", payload)
            return {"status": "new", "order_id": res.get("order_id")}
        except Exception as e:
            logger.exception(f"Futures order failed: {e}")
            raise
