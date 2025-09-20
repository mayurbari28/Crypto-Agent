#Description: Secrets encryption vault using Fernet.

import os
from cryptography.fernet import Fernet
from utils.config import settings
from pathlib import Path
import json
from threading import Lock

class SecretsVault:
    _instance = None
    _lock = Lock()

    def __init__(self):
        key = settings.ENCRYPTION_KEY
        if not key:
            key_path = Path(".key")
            if key_path.exists():
                key = key_path.read_text().strip().encode()
            else:
                key = Fernet.generate_key()
                key_path.write_text(key.decode())
        self.fernet = Fernet(key)
        self.path = Path(".secrets.json")
        if not self.path.exists():
            self.path.write_text(self.fernet.encrypt(b"{}").decode())

    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = SecretsVault()
        return cls._instance

    def _read(self) -> dict:
        data = self.path.read_text().encode()
        raw = self.fernet.decrypt(data)
        return json.loads(raw.decode())

    def _write(self, obj: dict):
        enc = self.fernet.encrypt(json.dumps(obj).encode())
        self.path.write_text(enc.decode())

    def store(self, label: str, key_id: str, secret: str):
        data = self._read()
        data[label] = {"key": key_id, "secret": secret}
        self._write(data)

    def fetch(self, label: str) -> tuple[str|None, str|None]:
        data = self._read()
        info = data.get(label)
        if not info: return None, None
        return info.get("key"), info.get("secret")
