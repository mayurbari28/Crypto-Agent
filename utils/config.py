#Description: Pydantic settings loader with defaults, reading .env.
import os
import pathlib

from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    APP_ENV: str = Field(default="development")
    DATABASE_URL: str = Field(default="sqlite:///./trader.db")
    ENCRYPTION_KEY: str | None = Field(default=None)
    MODE: str = Field(default=os.getenv("MODE", "paper"))  # live|paper|dryrun

    COINDCX_API_KEY: str | None = None
    COINDCX_API_SECRET: str | None = None
    COINDCX_FUT_API_KEY: str | None = None
    COINDCX_FUT_API_SECRET: str | None = None

    OPENAI_API_KEY: str | None = None

    CONFIDENCE_THRESHOLD: float = Field(default=0.65)
    SPOT_ALLOCATION_PCT: float = Field(default=0.6)
    FUTURES_ALLOCATION_PCT: float = Field(default=0.4)

    SCAN_INTERVAL_SECONDS: int = Field(default=300)
    MONITOR_INTERVAL_SECONDS: int = Field(default=10)

    MAX_LEVERAGE: int = Field(default=3)
    RISK_PER_TRADE_PCT: float = Field(default=0.0075)
    #TODO check/explain below
    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
