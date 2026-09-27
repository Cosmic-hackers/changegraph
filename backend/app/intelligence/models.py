"""
backend/app/intelligence/models.py — Structured data contracts for Phase 2 AI Intelligence Layer.

Defines Pydantic models for:
- Phase 1 deterministic fact ingestion (IntelligenceInput)
- Individual agent outputs (Impact, Risk, Test, History)
- Grounding verification & evidence audit trails
- Final synthesized Change Impact Report
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 Ingestion Data Contract
# ─────────────────────────────────────────────────────────────────────────────

class ChangedSymbolFact(BaseModel):
    """A symbol confirmed as directly changed in Phase 1."""
    key: str
    symbol: str
    module: str
    file_path: str
    reason: str


class ImpactedSymbolFact(BaseModel):
    """A dependent symbol confirmed as impacted in Phase 1."""
    key: str
    node_type: str
    name: str
    module: str
    file_path: str
    depth: int
    path: list[str] = Field(default_factory=list)
    explanation: str = ""


class TestFileFact(BaseModel):
    """A test file identified as relevant in Phase 1."""
    __test__ = False
    file_path: str
    module_name: str
    match_reasons: list[str] = Field(default_factory=list)
    matched_functions: list[str] = Field(default_factory=list)


class CommitFact(BaseModel):
    """A git commit touching an affected file."""
    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str] = Field(default_factory=list)


class FileHistoryFact(BaseModel):
    """Git history for a single file."""
    file_path: str
    relative_path: str
    churn_score: int = 0
    authors: list[str] = Field(default_factory=list)
    recent_commits: list[CommitFact] = Field(default_factory=list)


class CoChangeFact(BaseModel):
    """Pair of files historically modified together."""
    file_a: str
    file_b: str
    co_change_count: int


class GitContextFact(BaseModel):
    """Git context discovered in Phase 1."""
    git_available: bool = False
    repo_root: str = ""
    file_histories: dict[str, FileHistoryFact] = Field(default_factory=dict)
    co_changed_pairs: list[CoChangeFact] = Field(default_factory=list)
    error: Optional[str] = None


class IntelligenceInput(BaseModel):
    """
    Standardized, strongly-typed input contract for the Intelligence Layer.
    Can be constructed directly from Phase 1 AnalysisResult or AnalyzeResponse.
    """
    repository_path: str
    change_request: str
    changed_components: list[ChangedSymbolFact] = Field(default_factory=list)
    direct_impact: list[ImpactedSymbolFact] = Field(default_factory=list)
    indirect_impact: list[ImpactedSymbolFact] = Field(default_factory=list)
    affected_files: list[str] = Field(default_factory=list)
    recommended_tests: list[TestFileFact] = Field(default_factory=list)
    deterministic_risk_level: str = "UNKNOWN"
    deterministic_risk_reasons: list[str] = Field(default_factory=list)
    dependency_paths: list[list[str]] = Field(default_factory=list)
    git_context: Optional[GitContextFact] = None
    graph_summary: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @property
    def all_impacted_symbols(self) -> list[ImpactedSymbolFact]:
        return self.direct_impact + self.indirect_impact

    @property
    def known_modules(self) -> set[str]:
        mods = {c.module for c in self.changed_components if c.module}
        for n in self.all_impacted_symbols:
            if n.module:
                mods.add(n.module)
        return mods

    @property
    def known_symbols(self) -> set[str]:
        symbols = {c.symbol for c in self.changed_components if c.symbol}
        for n in self.all_impacted_symbols:
            symbols.add(f"{n.module}.{n.name}" if n.module else n.name)
            symbols.add(n.name)
        return symbols


# ─────────────────────────────────────────────────────────────────────────────
# Agent Communication Outputs
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowImpact(BaseModel):
    """Specific business/system workflow affected by the change."""
    workflow_name: str
    affected_components: list[str]
    propagation_chain: str
    impact_explanation: str
    criticality: Literal["CRITICAL", "MAJOR", "MINOR"] = "MAJOR"


class ImpactReasoningOutput(BaseModel):
    """Output produced by the Impact Agent."""
    summary: str
    affected_workflows: list[WorkflowImpact] = Field(default_factory=list)
    propagation_breakdown: list[str] = Field(default_factory=list)
    grounded_symbols: list[str] = Field(default_factory=list)


class FailureScenario(BaseModel):
    """Concrete potential failure mode grounded in the affected code."""
    component: str
    scenario_description: str
    potential_consequence: str
    mitigation_advice: str


class RiskReasoningOutput(BaseModel):
    """Output produced by the Risk Agent."""
    assessed_risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_justification: list[str] = Field(default_factory=list)
    failure_scenarios: list[FailureScenario] = Field(default_factory=list)
    sensitive_domains_identified: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)


class RecommendedTestItem(BaseModel):
    """Individual test suite recommendation."""
    test_file: str
    test_module: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    rationale: str
    target_functions: list[str] = Field(default_factory=list)


class TestCoverageGap(BaseModel):
    """Area or function affected by the change that lacks targeted test coverage."""
    component: str
    gap_description: str
    suggested_test_scenario: str


class TestRecommendationsOutput(BaseModel):
    """Output produced by the Test Agent."""
    __test__ = False
    recommended_suites: list[RecommendedTestItem] = Field(default_factory=list)
    coverage_gaps: list[TestCoverageGap] = Field(default_factory=list)
    regression_scenarios: list[str] = Field(default_factory=list)
    summary: str


class HighChurnFileItem(BaseModel):
    file_path: str
    churn_score: int
    authors: list[str] = Field(default_factory=list)
    risk_implication: str


class CoChangePatternItem(BaseModel):
    file_a: str
    file_b: str
    co_change_count: int
    implication: str


class HistoryContextOutput(BaseModel):
    """Output produced by the History Agent."""
    historical_summary: str
    high_churn_files: list[HighChurnFileItem] = Field(default_factory=list)
    co_change_patterns: list[CoChangePatternItem] = Field(default_factory=list)
    historical_risk_notes: list[str] = Field(default_factory=list)
    has_git_data: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Observability & Evidence Audit
# ─────────────────────────────────────────────────────────────────────────────

class EvidenceAudit(BaseModel):
    """Audit trail verifying facts used and ensuring zero invented dependencies."""
    deterministic_nodes_evaluated: int
    deterministic_edges_evaluated: int
    direct_dependents_count: int
    indirect_dependents_count: int
    validated_symbol_count: int
    unverified_claims_filtered: list[str] = Field(default_factory=list)
    ai_provider_used: str
    generation_mode: Literal["AI_AUGMENTED", "DETERMINISTIC_GROUNDED", "MOCK"]


# ─────────────────────────────────────────────────────────────────────────────
# Final Synthesized Change Impact Report
# ─────────────────────────────────────────────────────────────────────────────

class DeveloperAction(BaseModel):
    step: int
    action_type: Literal["MODIFY", "TEST", "VERIFY", "CO_UPDATE", "MONITOR"]
    description: str
    target_component: str


class ChangeImpactReport(BaseModel):
    """The complete Phase 2 Synthesized Change Impact Report."""
    repository_path: str
    change_request: str
    executive_summary: str
    changed_components: list[ChangedSymbolFact]
    direct_impact_summary: str
    indirect_impact_summary: str
    impact_reasoning: ImpactReasoningOutput
    risk_analysis: RiskReasoningOutput
    test_strategy: TestRecommendationsOutput
    history_context: HistoryContextOutput
    suggested_developer_actions: list[DeveloperAction] = Field(default_factory=list)
    evidence: EvidenceAudit
    warnings: list[str] = Field(default_factory=list)
