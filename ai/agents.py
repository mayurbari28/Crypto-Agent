# Description: Implements LLMResearchAgent (OpenAI JSON), RuleBasedResearchAgent (deterministic), and RuleBasedRiskAgent.
from __future__ import annotations
from email import message
from typing import Dict, Any, List, Tuple

from utils.config import settings
from utils.logging import logger
from models.schemas import SignalOut
from ai.tools import JsonTool, RiskTool

class LLMResearchAgent:
    """
    Uses OpenAI Chat Completions to create a concise rationale and confidence delta for a signal.
    Expects OPENAI_API_KEY. If any error occurs, falls back to a safe noop result.
    """
    def __init__(self, model: str | None = None, max_tokens: int = 300):
        self.model = model or "gpt-4o-mini"
        self.max_tokens = max_tokens
        # Lazy import to avoid hard dependency if key is not present
        try:
            from openai import OpenAI  # type: ignore
            self._client = OpenAI()
        except Exception as e:
            logger.warning(f"OpenAI client init failed: {e}")
            self._client = None

    def analyze(self, signal: SignalOut, features: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
        if self._client is None or not settings.OPENAI_API_KEY:
            return {"notes": self._compose_default_notes(signal, features, regime), "confidence_delta": 0.0}

        system = (
            "You are a concise crypto swing-trading analyst. Given numeric features and a preliminary signal, "
            "write a short rationale and a small confidence adjustment in JSON. "
            "Keep the adjustment conservative within [-0.15, 0.15]."
        )
        user = {
            "instruction": "Analyze the following and return JSON with keys: confidence_delta ([-0.15,0.15]), notes (<=280 chars), risk_flags (list).",
            "signal": {
                "symbol": signal.symbol, "market": signal.market, "timeframe": signal.timeframe,
                "confidence": signal.confidence, "expected_return_pct": signal.expected_return_pct,
                "entry": signal.entry, "tp": signal.tp, "sl": signal.sl, "side": signal.side
            },
            "features": features,
            "regime": regime
        }
        logger.info(f"Quering to LLM for {signal.symbol}")
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": str(user)}
                ],
                temperature=0.2,
                max_tokens=self.max_tokens,
            )
            text = resp.choices[0].message.content.strip()
            logger.info(f'Response received from LLM : {text}')
            data = JsonTool.parse_json_from_text(text)
            conf_delta = float(data.get("confidence_delta", 0.0))
            conf_delta = max(-0.15, min(0.15, conf_delta))
            notes = data.get("notes") or self._compose_default_notes(signal, features, regime)
            logger.info(f'Notes for Symbol {signal.symbol} : {notes}')
            # Normalize risk flags to short phrases if present
            flags = data.get("risk_flags") if isinstance(data.get("risk_flags"), list) else []
            if flags:
                notes = f"{notes} [Flags: {', '.join(flags[:3])}]"
            return {"notes": notes, "confidence_delta": conf_delta}
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return {"notes": self._compose_default_notes(signal, features, regime), "confidence_delta": 0.0}

    def _compose_default_notes(self, signal: SignalOut, f: Dict[str, Any], regime: Dict[str, Any]) -> str:
        trend = f.get("trend_strength", 0.0)
        rsi = f.get("rsi")
        atr_ratio = f.get("atr_ratio")
        breakout = "yes" if f.get("breakout") else "no"
        reg = regime.get("label", "unknown")
        return (
            f"Trend strength {trend:.2f}, RSI {rsi:.1f}, ATR ratio {atr_ratio:.3f}, breakout {breakout}, regime {reg}."
        )


class RuleBasedResearchAgent:
    """
    Deterministic research rationale based on numeric features and regime context.
    Produces a small positive or zero delta for confidence if conditions are favorable.
    """
    def analyze(self, signal: SignalOut, features: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
        notes, delta = self._build_notes_and_delta(signal, features, regime)
        return {"notes": notes, "confidence_delta": delta}

    def _build_notes_and_delta(self, s: SignalOut, f: Dict[str, Any], regime: Dict[str, Any]) -> Tuple[str, float]:
        trend = float(f.get("trend_strength", 0.0))
        rsi = float(f.get("rsi", 50.0))
        atr_ratio = float(f.get("atr_ratio", 0.02))
        breakout = bool(f.get("breakout", 0) == 1)
        rr = float(f.get("rr", 1.5))
        reg = regime.get("label", "unknown")

        delta = 0.0
        reasons: List[str] = []
        if trend > 0.2:
            delta += min(0.05, trend / 2.0)
            reasons.append("Trend up")
        if 50 <= rsi <= 65:
            delta += 0.02
            reasons.append("RSI sweet spot")
        if breakout:
            delta += 0.03
            reasons.append("Breakout")
        if rr >= 1.5:
            delta += 0.02
            reasons.append("RR ok")
        if atr_ratio > 0.06:
            delta -= 0.05
            reasons.append("High vol")
        if reg == "bullish" and s.side.upper() == "BUY":
            delta += 0.02
            reasons.append("Regime aligned")
        delta = max(-0.08, min(0.08, delta))

        text = (
            f"Trend {trend:.2f}, RSI {rsi:.1f}, ATR ratio {atr_ratio:.3f}, RR {rr:.2f}, breakout {'yes' if breakout else 'no'}, regime {reg}. "
            + ("+" if delta >= 0 else "") + f"{delta:.2f} conf."
        )
        return text, delta


class RuleBasedRiskAgent:
    """
    Applies conservative risk penalties/bonuses to confidence using RiskTool.
    """
    def __init__(self, risk_tool: RiskTool):
        self.risk_tool = risk_tool

    def apply(self, signal: SignalOut, features: Dict[str, Any], regime: Dict[str, Any]) -> Tuple[float, List[str]]:
        return self.risk_tool.confidence_adjustment(signal, features, regime)