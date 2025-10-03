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

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        client_id: str,
        leverage: int = 1,
        take_profit: float = 0,
        stop_loss: float = 0
    ):
        """
        Place a futures limit order with optional Take Profit (TP) and Stop Loss (SL).
        """
        payload = {
            "timestamp": int(time.time() * 1000),
            "order": {
                "side": side.lower(),                       # buy or sell
                "pair": symbol,                             # e.g., "B-ID_USDT"
                "order_type": "limit_order",                # limit order
                "price": str(price),                        # price as string
                "total_quantity": qty,                      # numeric value
                "leverage": leverage,                       # leverage (e.g. 10)
                "notification": "email_notification",       # adjust if needed
                "time_in_force": "good_till_cancel",        # or fill_or_kill / immediate_or_cancel
                "hidden": False,
                "post_only": False,
                "client_order_id": client_id
            }
        }

        # Attach TP and SL only if provided
        if take_profit > 0:
            payload["order"]["take_profit_price"] = float(take_profit)
        if stop_loss > 0:
            payload["order"]["stop_loss_price"] = float(stop_loss)

        if settings.MODE != "live":
            return {"status": "new", "order_id": "SIM-" + client_id}

        try:
            res = self.post("/exchange/v1/derivatives/futures/orders/create", payload)
            return {"status": "new", "order_id": res.get("order_id")}
        except Exception as e:
            logger.exception(f"Futures order failed: {e}")
            raise


    # ----------------------------------- NOT IN USE ----------------------------------------------------- #
    # --------------------------------------------------------------------- #
    # 1. PRIMARY LIMIT ORDER                                                #
    # --------------------------------------------------------------------- #
    from typing import Dict, Optional, Literal

    TTriggerType = Literal["MARK_PRICE", "INDEX_PRICE", "LAST_PRICE"]
    TOrderType   = Literal["market", "limit"]
    TExitMode    = Literal["TAKE_PROFIT", "STOP_LOSS"]

    def place_limit_order_tp_sl(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        client_id: str,
        leverage: int = 1,
        reduce_only: bool = False,
        take_profit: Optional[Dict] = None,
        stop_loss: Optional[Dict] = None,
    ) -> Dict:
        """
        Places the main limit order and, if configs are supplied, schedules TP/SL
        via the /futures/orders/create/tp-sl endpoint *after* the entry order is live.

        take_profit / stop_loss dicts expect:
            {
                "trigger_price": float,             # mandatory
                "trigger_type": "MARK_PRICE",       # optional, defaults to MARK_PRICE
                "order_type": "market"|"limit",     # optional, defaults to "market"
                "price_per_unit": float,            # required when order_type == "limit"
                "qty": float,                       # optional, defaults to entry qty
                "client_suffix": "-TP"              # optional string appended to client_id
            }
        """
        payload = {
            "side": side.upper(),
            "order_type": "limit",
            "market": symbol,
            "price_per_unit": price,
            "total_quantity": qty,
            "timestamp": int(time.time() * 1000),
            "client_order_id": client_id,
            "leverage": leverage,
            "reduce_only": reduce_only,
        }

        if settings.MODE != "live":
            order_id = f"SIM-{client_id}"
            response = {"status": "new", "order_id": order_id}
        else:
            try:
                res = self.post("/exchange/v1/futures/orders/create", payload)
            except Exception as exc:
                logger.exception(f"Primary futures order failed: {exc}")
                raise
            order_id = res.get("order_id")
            response = {"status": res.get("status", "new"), "order_id": order_id}

        # Nothing more to do in paper/backtest mode.
        if settings.MODE != "live":
            return response

        exit_side = "SELL" if side.upper() == "BUY" else "BUY"

        if stop_loss:
            response["stop_loss"] = self._create_tp_sl_order(
                mode="STOP_LOSS",
                symbol=symbol,
                exit_side=exit_side,
                parent_order_id=order_id,
                qty=stop_loss.get("qty", qty),
                trigger_price=stop_loss["trigger_price"],
                trigger_type=stop_loss.get("trigger_type", "MARK_PRICE"),
                order_type=stop_loss.get("order_type", "market"),
                price_per_unit=stop_loss.get("price_per_unit"),
                client_id=f"{client_id}{stop_loss.get('client_suffix', '-SL')}",
            )

        if take_profit:
            response["take_profit"] = self._create_tp_sl_order(
                mode="TAKE_PROFIT",
                symbol=symbol,
                exit_side=exit_side,
                parent_order_id=order_id,
                qty=take_profit.get("qty", qty),
                trigger_price=take_profit["trigger_price"],
                trigger_type=take_profit.get("trigger_type", "MARK_PRICE"),
                order_type=take_profit.get("order_type", "market"),
                price_per_unit=take_profit.get("price_per_unit"),
                client_id=f"{client_id}{take_profit.get("client_suffix", "-TP")}",
            )

        return response

    # --------------------------------------------------------------------- #
    # 2. TP / SL CREATION (per CoinDCX endpoint)                            #
    # --------------------------------------------------------------------- #
    def _create_tp_sl_order(
        self,
        *,
        mode: TExitMode,
        symbol: str,
        exit_side: str,
        parent_order_id: str,
        qty: float,
        trigger_price: float,
        trigger_type: TTriggerType,
        order_type: TOrderType,
        client_id: str,
        price_per_unit: Optional[float] = None,
        reduce_only: bool = True,
    ) -> Dict:
        """
        Wraps https://docs.coindcx.com/#create-take-profit-and-stop-loss-orders

        Required request fields (per docs):
          - mode               : "STOP_LOSS" | "TAKE_PROFIT"
          - parent_order_id    : ID returned when the primary order was placed
          - market             : instrument symbol
          - side               : exit side (opposite of entry)
          - trigger_type       : "MARK_PRICE" | "INDEX_PRICE" | "LAST_PRICE"
          - trigger_price      : float
          - order_type         : "market" | "limit"
          - total_quantity     : float
          - client_order_id    : unique identifier
          - timestamp          : ms epoch
        Optional:
          - price_per_unit     : required when order_type == "limit"
          - reduce_only        : recommended True for exits
        """
        order_type = order_type.lower()
        if order_type not in {"market", "limit"}:
            raise ValueError("order_type must be 'market' or 'limit'")

        trigger_type = trigger_type.upper()
        if trigger_type not in {"MARK_PRICE", "INDEX_PRICE", "LAST_PRICE"}:
            raise ValueError("trigger_type must be MARK_PRICE / INDEX_PRICE / LAST_PRICE")

        payload = {
            "mode": mode,
            "parent_order_id": parent_order_id,
            "market": symbol,
            "side": exit_side.upper(),
            "order_type": order_type,
            "total_quantity": qty,
            "trigger_type": trigger_type,
            "trigger_price": trigger_price,
            "client_order_id": client_id,
            "reduce_only": reduce_only,
            "timestamp": int(time.time() * 1000),
        }

        if order_type == "limit":
            if price_per_unit is None:
                raise ValueError("price_per_unit is mandatory for limit TP/SL orders")
            payload["price_per_unit"] = price_per_unit

        if settings.MODE != "live":
            return {"status": "new", "order_id": f"SIM-{client_id}", "mode": mode.lower()}

        try:
            res = self.post("/exchange/v1/futures/orders/create/tp-sl", payload)
            return {
                "status": res.get("status", "new"),
                "order_id": res.get("order_id"),
                "mode": mode.lower(),
            }
        except Exception as exc:
            logger.exception(f"{mode} creation failed for {symbol}: {exc}")
            raise