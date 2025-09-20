 #Description: CrewAI orchestrator; uses LLM-backed or rule-based agents to enrich signals with explainable rationale and risk-adjusted confidence.

from threading import Lock
from typing import List, Tuple

from utils.config import settings
from utils.logging import logger
from models.schemas import SignalOut
from ai.tools import FeatureTool, RegimeTool, RiskTool
from ai.agents import RuleBasedResearchAgent, RuleBasedRiskAgent, LLMResearchAgent

class CrewOrchestrator:
    """
    Orchestrates agentic enrichment of numeric trading signals.
    - If OPENAI_API_KEY and CrewAI libs are available, uses LLMResearchAgent for richer rationales.
    - Always applies RuleBasedRiskAgent to apply conservative confidence adjustments.
    - Never changes entry/TP/SL prices drastically, only confidence and rationale. Keeps outputs deterministic if LLM is disabled.
    """
    _instance = None
    _lock = Lock()

    def __init__(self):
        self.llm_enabled = False
        try:
            import crewai  # noqa: F401
            # If OPENAI_API_KEY present, allow LLM mode
            self.llm_enabled = bool(settings.OPENAI_API_KEY)
        except Exception:
            self.llm_enabled = False

        # Tools
        self.features = FeatureTool()
        self.regime = RegimeTool()
        self.risk_tool = RiskTool()

        # Agents
        self.research_agent = (
            LLMResearchAgent() if self.llm_enabled else RuleBasedResearchAgent()
        )
        self.risk_agent = RuleBasedRiskAgent(self.risk_tool)

        logger.info(f"CrewOrchestrator initialized. LLM enabled: {self.llm_enabled}")

    @classmethod
    def instance(cls):
        with cls._lock:
            if not cls._instance:
                cls._instance = CrewOrchestrator()
        return cls._instance

    def enrich_signals(self, signals: List[SignalOut], timeframe: str) -> List[SignalOut]:
        """
        Enrich a list of signals with:
        - ResearchAgent rationale (LLM or rule-based)
        - RiskAgent confidence adjustment with reasons
        Returns updated signals (confidence clamped to [0,1], rationale appended).
        """
        if not signals:
            return signals

        try:
            # Compute market regime context once (for BTCUSDT 4h by default)
            regime = self.regime.get_regime(base_symbol="BTCUSDT", timeframe="4h")
        except Exception as e:
            logger.warning(f"Regime computation failed: {e}")
            regime = {"label": "unknown", "trend_strength": 0.0, "volatility": "med"}

        enriched: List[SignalOut] = []
        for s in signals:
            try:
                feats = self.features.latest_features(s.symbol, timeframe)
                # Research rationale (LLM or rule-based)
                research_out = self.research_agent.analyze(signal=s, features=feats, regime=regime)
                research_notes = research_out.get("notes", "")
                conf_delta_research = float(research_out.get("confidence_delta", 0.0))
                # Apply risk overlay adjustments
                conf_delta_risk, risk_reasons = self.risk_agent.apply(signal=s, features=feats, regime=regime)

                # Update confidence with bounded adjustments
                new_conf = float(s.confidence) + conf_delta_research + conf_delta_risk
                new_conf = max(0.0, min(1.0, new_conf))

                # Build rationale
                segments = [seg for seg in [s.rationale, research_notes] if seg]
                if risk_reasons:
                    segments.append("Risk: " + "; ".join(risk_reasons))
                s.confidence = new_conf
                s.rationale = " | ".join(segments)[:1000]  # keep concise

                enriched.append(s)
            except Exception as e:
                logger.warning(f"Signal enrichment failed for {s.symbol}: {e}")
                enriched.append(s)

        # Optionally sort by adjusted confidence, then expected return
        try:
            enriched.sort(key=lambda x: (x.confidence, x.expected_return_pct), reverse=True)
        except Exception:
            pass

        return enriched