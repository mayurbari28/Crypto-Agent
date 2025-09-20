Description: Project overview, setup, and usage instructions.
```markdown
# Agentic AI Trading System for CoinDCX (Spot & Futures)

Python + Streamlit + CrewAI (optional) application that:
- Scans crypto spot and F&O (futures) on CoinDCX for short-term/swing opportunities
- Scores with confidence, expected return, target price, and stop loss
- Auto-invests funds by configured percentage when confidence exceeds threshold
- Monitors open positions and exits on TP/SL or risk triggers
- Provides a multi-page Streamlit UI with real-time data, charts, and portfolio management

Important: This tool is for research and automation support. Not financial advice. Use simulation mode before any live trading.

## Features

- Multipage Streamlit UI: Dashboard, Screener, Strategy Config, Portfolio & Orders, Backtesting & Logs, API & Keys, Risk Center
- Numeric signal engine using EMA/RSI/MACD/ATR, breakout filter
- Optional CrewAI agentic enrichment for rationales (works without LLM)
- Execution engine with CoinDCX adapters; paper/dryrun simulation mode
- Monitoring service to enforce TP/SL
- SQLite persistence via SQLAlchemy, Plotly charts, secure API key storage

## Tech Stack

- Python 3.10+, Streamlit, pandas/numpy, pandas-ta, SQLAlchemy
- APScheduler, tenacity, loguru, cryptography
- CrewAI (optional), OpenAI (optional)
- CoinDCX public ticker for live prices; candles via bundled CSV or synthetic generator

## Install

1. Clone repo and enter directory:
   ```
   git clone <repo-url>
   cd app
   ```

2. Create virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment:
   - Copy `.env.example` to `.env` and set values.
   - Default MODE is `paper`. For safety, live orders are disabled unless MODE=live.

## Run

- Start Streamlit:
  ```
  streamlit run app/streamlit_app.py
  ```
  Then open http://localhost:8501 in your browser. Use the sidebar to navigate between pages.

- The background scheduler automatically:
  - Scans markets every `SCAN_INTERVAL_SECONDS` (default 300)
  - Monitors TP/SL every `MONITOR_INTERVAL_SECONDS` (default 10)

## Modes

- `paper`: Simulates orders and PnL. Recommended for testing.
- `dryrun`: Same as paper but emphasizes no external calls.
- `live`: Enables adapters to place orders. Use at your own risk, with valid CoinDCX API keys and permissions.

## Security

- API keys saved via the "API & Keys" page are encrypted with a locally stored Fernet key (`.key`) and persisted in `.secrets.json`.
- Environment `.env` can hold keys as well (avoid committing). Secrets are never logged.
- Includes a global Kill Switch.

## CrewAI

- To enable agentic enrichment, install CrewAI (already in requirements) and set `OPENAI_API_KEY`.
- The app will annotate rationales with additional context. Numeric outputs remain deterministic.

## Data

- Sample CSVs for BTCUSDT_1h and ETHUSDT_1h included in `data/`.
- Candles for other symbols/timeframes are synthetically generated for demo purposes.

## Limitations and Notes

- CoinDCX endpoints evolve. The adapters provide stubs for placing orders; verify paths and parameters against the latest official documentation before live trading.
- Websocket streaming is not implemented; polling is used for simplicity.
- Options trading is not included; F&O is treated as Futures initially.
- Backtesting is illustrative, not a full engine.

## Tests

Run minimal tests:
```
pytest app/tests -q
```

## Deployment

- Containerize with a simple Dockerfile (not included here). Expose port 8501.
- Set environment variables via secrets manager.
- Use a process supervisor to keep Streamlit and scheduler running.

## Disclaimer

This software is provided "as is" without warranty. Crypto trading involves significant risk. You are responsible for any financial losses.
```

6. Setup & Deployment Instructions
- Prerequisites: Python 3.10+, Git. Optional: Docker.
- Steps:
  - Clone repository.
  - Create virtual environment and install dependencies from requirements.txt.
  - Copy .env.example to .env, set MODE=paper for testing; optionally fill API keys and OPENAI_API_KEY for CrewAI.
  - Run: streamlit run app/streamlit_app.py
  - Use the UI pages to configure strategies, run screener, and monitor portfolio.
- Live trading:
  - Switch MODE=live only after thorough paper testing.
  - Input API keys via API & Keys page and test connectivity.
  - Ensure correct permissions on CoinDCX for order placement.
  - Validate adapter endpoints against current docs, especially order placement paths and parameters.
- Deployment:
  - Containerize if desired; mount persistent volume for DB and secrets.
  - Running behind reverse proxy is optional. Add auth if exposing publicly.

7. Final Notes (any important considerations, limitations, or next steps)
- This is a complete, runnable system in simulation (paper/dryrun) mode with agentic scaffolding. Live trading requires adapter endpoint verification and careful risk validation.
- Next steps:
  - Implement live OCO/bracket orders if CoinDCX supports them; else maintain monitor-based TP/SL.
  - Add websocket subscriptions for price and order updates.
  - Expand CrewAI agents for deeper reasoning and risk critique, plus calibration based on realized hit ratios.
  - Integrate Telegram/webhook alerts.
  - Improve backtesting with vectorbt or custom engine, including commission/slippage models and futures fees.
- Safety:
  - Keep Kill Switch visible; use global limits in Risk Center.
  - Start sma