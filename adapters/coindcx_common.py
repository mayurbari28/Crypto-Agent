#Description: Base adapter utilities, including signing and request.

import time
import hmac
import hashlib
import json
import httpx

from utils.config import settings
from utils.logging import logger

class CoinDCXBaseAdapter:
    BASE_URL = "https://api.coindcx.com"
    PUB_URL = "https://public.coindcx.com"

    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        self.api_key = api_key or settings.COINDCX_API_KEY
        self.api_secret = api_secret or settings.COINDCX_API_SECRET
        self.client = httpx.Client(timeout=10)

    def _headers(self, payload: dict | None = None):
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_secret and payload is not None:
            body = json.dumps(payload)
            signature = hmac.new(self.api_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers.update({"X-AUTH-APIKEY": self.api_key, "X-AUTH-SIGNATURE": signature})
        return headers

    def get(self, path: str, params: dict | None = None, public: bool = False):
        url = (self.PUB_URL if public else self.BASE_URL) + path
        r = self.client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, payload: dict):
        headers = self._headers(payload)
        url = self.BASE_URL + path
        r = self.client.post(url, headers=headers, content=json.dumps(payload))
        r.raise_for_status()
        return r.json()

