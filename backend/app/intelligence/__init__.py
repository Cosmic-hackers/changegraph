"""
backend/app/intelligence — Phase 2 IBM Bob Intelligence Layer for ChangeGraph.
"""

from .models import (
    IntelligenceInput,
    ChangedSymbolFact,
    ImpactedSymbolFact,
    TestFileFact,
    GitContextFact,
    ImpactReasoningOutput,
    RiskReasoningOutput,
    TestRecommendationsOutput,
    HistoryContextOutput,
    ChangeImpactReport,
    DeveloperAction,
    EvidenceAudit,
)
from .provider import (
    AIProvider,
    BobProvider,
    DeterministicFallbackProvider,
    MockAIProvider,
    get_ai_provider,
    AIProviderError,
)
from .impact_agent import ImpactAgent
from .risk_agent import RiskAgent
from .test_agent import TestAgent
from .history_agent import HistoryAgent
from .synthesizer import SynthesisAgent
from .validation import GroundingValidator
from .orchestrator import IntelligenceOrchestrator, convert_phase1_to_intelligence_input

__all__ = [
    "IntelligenceInput",
    "ChangedSymbolFact",
    "ImpactedSymbolFact",
    "TestFileFact",
    "GitContextFact",
    "ImpactReasoningOutput",
    "RiskReasoningOutput",
    "TestRecommendationsOutput",
    "HistoryContextOutput",
    "ChangeImpactReport",
    "DeveloperAction",
    "EvidenceAudit",
    "AIProvider",
    "BobProvider",
    "DeterministicFallbackProvider",
    "MockAIProvider",
    "get_ai_provider",
    "AIProviderError",
    "ImpactAgent",
    "RiskAgent",
    "TestAgent",
    "HistoryAgent",
    "SynthesisAgent",
    "GroundingValidator",
    "IntelligenceOrchestrator",
    "convert_phase1_to_intelligence_input",
]
