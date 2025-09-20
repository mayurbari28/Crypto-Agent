#Description: Spot adapter with connectivity test and basic order endpoints (stubbed for safety).

from adapters.coindcx_common import CoinDCXBaseAdapter
from utils.logging import logger
from utils.config import settings

#TODO learn
class CoinDCXSpotAdapter(CoinDCXBaseAdapter):
    def __init__(self):
        super().__init__(settings.COINDCX_API_KEY, settings.COINDCX_API_SECRET)

    def test_connectivity(self):
        try:
            # Public endpoint
            tick = self.get("/exchange/ticker", public=True)
            return True, f"Tickers: {len(tick)} items"
        except Exception as e:
            return False, f"Connectivity failed: {e}"

    def place_market_order(self, symbol: str, side: str, qty: float, client_id: str):
        # WARNING: Actual endpoint paths/params must be verified from CoinDCX docs.
        payload = {
            "side": side.upper(), "order_type": "market", "market": symbol,
            "total_quantity": qty, "timestamp": int(time.time() * 1000), "client_order_id": client_id
        }
        # For safety, do not send if not live
        if settings.MODE != "live":
            return {"status": "filled", "order_id": "SIM-"+client_id, "avg_price": None}
        try:
            res = self.post("/exchange/v1/orders/create", payload)
            return {"status": "new", "order_id": res.get("order_id"), "avg_price": None}
        except Exception as e:
            logger.exception(f"Spot order failed: {e}")
            raise


    def place_market_order(self, symbol: str, side: str, qty: float, client_id: str):
        # WARNING: Actual endpoint paths/params must be verified from CoinDCX docs.
        payload = {
            "side": side.upper(), "order_type": "market", "market": symbol,
            "total_quantity": qty, "timestamp": int(time.time() * 1000), "client_order_id": client_id
        }
        # For safety, do not send if not live
        if settings.MODE != "live":
            return {"status": "filled", "order_id": "SIM-"+client_id, "avg_price": None}
        try:
            res = self.post("/exchange/v1/orders/create", payload)
            return {"status": "new", "order_id": res.get("order_id"), "avg_price": None}
        except Exception as e:
            logger.exception(f"Spot order failed: {e}")
            raise

import time  # placed here to keep imports minimal TODO:Why this import needed? 
