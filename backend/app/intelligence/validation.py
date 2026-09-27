"""
backend/app/intelligence/validation.py — Grounding Validator & Hallucination Guard.

Enforces the critical architectural constraint:
The deterministic analyzer is the SOLE authority for code relationships.
Any component claimed as affected by an agent MUST trace back to Phase 1 facts.
Fabricated or un-evidenced components are detected, filtered, and logged into the audit trail.
"""

from __future__ import annotations

import re
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    ImpactReasoningOutput,
    RiskReasoningOutput,
    TestRecommendationsOutput,
    HistoryContextOutput,
    EvidenceAudit,
    WorkflowImpact,
    FailureScenario,
)

logger = logging.getLogger("changegraph.intelligence.validation")


class GroundingValidator:
    """
    Validates agent outputs against deterministic Phase 1 facts.
    Guarantees no hallucinated components, un-evidenced dependencies, or fabricated history.
    """

    def __init__(self, input_data: IntelligenceInput):
        self.input_data = input_data
        self.filtered_claims: list[str] = []

        # Build white-list of valid symbols, modules, and files from deterministic facts
        self.valid_modules: set[str] = {
            c.module.lower() for c in input_data.changed_components if c.module
        }
        self.valid_symbols: set[str] = set()

        for c in input_data.changed_components:
            self._register_symbol(c.symbol)

        for imp in input_data.all_impacted_symbols:
            if imp.module:
                self.valid_modules.add(imp.module.lower())
            self._register_symbol(imp.name)
            if imp.module:
                self._register_symbol(f"{imp.module}.{imp.name}")

        self.valid_files: set[str] = {
            f.lower().replace("\\", "/") for f in input_data.affected_files
        }

    def _register_symbol(self, sym: str) -> None:
        if not sym:
            return
        clean = sym.strip().lower().replace("()", "")
        self.valid_symbols.add(clean)
        # Also register bare name if qualified
        if "." in clean:
            self.valid_symbols.add(clean.split(".")[-1])

    def is_symbol_grounded(self, symbol_name: str) -> bool:
        """Check whether a symbol or module is verified by Phase 1."""
        if not symbol_name:
            return False
        clean = symbol_name.strip().lower().replace("()", "")
        if clean in self.valid_symbols or clean in self.valid_modules:
            return True
        # Check module prefix
        if "." in clean:
            mod = clean.split(".")[0]
            if mod in self.valid_modules:
                return True
        return False

    def validate_impact(self, impact: ImpactReasoningOutput) -> ImpactReasoningOutput:
        """Filter any un-evidenced components from workflow impacts."""
        sanitized_workflows: list[WorkflowImpact] = []

        for wf in impact.affected_workflows:
            verified_components: list[str] = []
            for comp in wf.affected_components:
                if self.is_symbol_grounded(comp):
                    verified_components.append(comp)
                else:
                    msg = f"Filtered ungrounded component '{comp}' from workflow '{wf.workflow_name}'"
                    self.filtered_claims.append(msg)
                    logger.warning(msg)

            # Only retain workflow if it has at least one verified component
            if verified_components:
                wf.affected_components = verified_components
                sanitized_workflows.append(wf)

        # Validate grounded_symbols list
        verified_symbols = []
        for s in impact.grounded_symbols:
            if self.is_symbol_grounded(s):
                verified_symbols.append(s)
            else:
                self.filtered_claims.append(f"Filtered fabricated symbol claim: '{s}'")

        impact.affected_workflows = sanitized_workflows
        impact.grounded_symbols = verified_symbols
        return impact

    def validate_risk(self, risk: RiskReasoningOutput) -> RiskReasoningOutput:
        """Ensure failure scenarios reference real affected components."""
        sanitized_scenarios: list[FailureScenario] = []

        for scen in risk.failure_scenarios:
            if self.is_symbol_grounded(scen.component):
                sanitized_scenarios.append(scen)
            else:
                msg = f"Filtered failure scenario for un-evidenced component '{scen.component}'"
                self.filtered_claims.append(msg)
                logger.warning(msg)

        # Ensure sensitive domains are grounded in actual affected modules
        grounded_domains = []
        for domain in risk.sensitive_domains_identified:
            d_lower = domain.lower()
            if any(d_lower in mod for mod in self.valid_modules):
                grounded_domains.append(domain)
            else:
                self.filtered_claims.append(f"Filtered sensitive domain claim '{domain}' (not in affected modules)")

        risk.failure_scenarios = sanitized_scenarios
        risk.sensitive_domains_identified = grounded_domains
        return risk

    def validate_history(self, history: HistoryContextOutput) -> HistoryContextOutput:
        """
        Enforce critical rule:
        Never claim a historical regression or file churn unless the provided Git data supports it.
        """
        if not self.input_data.git_context or not self.input_data.git_context.git_available:
            history.has_git_data = False
            history.high_churn_files = []
            history.co_change_patterns = []
            history.historical_risk_notes = [
                "No git commit history was available for the analyzed repository."
            ]
            return history

        # Validate high churn files exist in actual git history
        valid_histories = self.input_data.git_context.file_histories
        sanitized_churn = []
        for item in history.high_churn_files:
            # Check if file_path is recognized
            matched = any(
                item.file_path.lower() in fp.lower() or fp.lower() in item.file_path.lower()
                for fp in valid_histories
            )
            if matched:
                sanitized_churn.append(item)
            else:
                self.filtered_claims.append(f"Filtered history claim for un-tracked file '{item.file_path}'")

        history.high_churn_files = sanitized_churn
        return history

    def build_audit(self, provider_name: str, mode: str) -> EvidenceAudit:
        """Create the observability audit record."""
        return EvidenceAudit(
            deterministic_nodes_evaluated=self.input_data.graph_summary.get("nodes", 0),
            deterministic_edges_evaluated=self.input_data.graph_summary.get("edges", 0),
            direct_dependents_count=len(self.input_data.direct_impact),
            indirect_dependents_count=len(self.input_data.indirect_impact),
            validated_symbol_count=len(self.valid_symbols),
            unverified_claims_filtered=self.filtered_claims,
            ai_provider_used=provider_name,
            generation_mode=mode,  # type: ignore
        )
