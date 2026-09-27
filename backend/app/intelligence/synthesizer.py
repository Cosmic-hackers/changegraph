"""
backend/app/intelligence/synthesizer.py — Synthesis Agent for ChangeGraph.

Synthesizes the outputs of Impact, Risk, Test, and History agents into the final
Change Impact Report with:
- Executive Summary
- Step-by-step Developer Actions checklist
- Evidence audit & confidence guarantees
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    ImpactReasoningOutput,
    RiskReasoningOutput,
    TestRecommendationsOutput,
    HistoryContextOutput,
    ChangeImpactReport,
    DeveloperAction,
    EvidenceAudit,
)
from .provider import AIProvider

logger = logging.getLogger("changegraph.intelligence.synthesizer")


class SynthesisAgent:
    """
    Synthesizes multi-agent outputs into the unified Change Impact Report.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def run(
        self,
        input_data: IntelligenceInput,
        impact_out: ImpactReasoningOutput,
        risk_out: RiskReasoningOutput,
        test_out: TestRecommendationsOutput,
        history_out: HistoryContextOutput,
        evidence: EvidenceAudit,
    ) -> ChangeImpactReport:
        # Generate developer action steps
        actions = self._generate_developer_actions(input_data, impact_out, risk_out, test_out, history_out)

        # Generate executive summary
        exec_summary = self._generate_executive_summary(input_data, risk_out, impact_out, test_out)

        # Direct & indirect impact human-readable summaries
        direct_summary = (
            f"{len(input_data.direct_impact)} direct dependent component(s) located across "
            f"{len({n.module for n in input_data.direct_impact})} module(s)."
        )
        indirect_summary = (
            f"{len(input_data.indirect_impact)} transitive dependent component(s) located across "
            f"{len({n.module for n in input_data.indirect_impact})} module(s)."
        )

        return ChangeImpactReport(
            repository_path=input_data.repository_path,
            change_request=input_data.change_request,
            executive_summary=exec_summary,
            changed_components=input_data.changed_components,
            direct_impact_summary=direct_summary,
            indirect_impact_summary=indirect_summary,
            impact_reasoning=impact_out,
            risk_analysis=risk_out,
            test_strategy=test_out,
            history_context=history_out,
            suggested_developer_actions=actions,
            evidence=evidence,
            warnings=list(input_data.warnings),
        )

    def _generate_executive_summary(
        self,
        input_data: IntelligenceInput,
        risk_out: RiskReasoningOutput,
        impact_out: ImpactReasoningOutput,
        test_out: TestRecommendationsOutput,
    ) -> str:
        changed_symbols = [c.symbol for c in input_data.changed_components]
        target_str = ", ".join(changed_symbols) if changed_symbols else "selected components"

        sensitive_str = ""
        if risk_out.sensitive_domains_identified:
            sensitive_str = f" Sensitive business domains impacted: {', '.join(risk_out.sensitive_domains_identified)}."

        return (
            f"ChangeGraph Impact Assessment: Proposed modification '{input_data.change_request}' targets {target_str}. "
            f"The change carries a {risk_out.assessed_risk_level} risk level due to "
            f"{len(input_data.direct_impact)} direct and {len(input_data.indirect_impact)} transitive dependent(s).{sensitive_str} "
            f"{len(test_out.recommended_suites)} test suite(s) should be executed before deployment."
        )

    def _generate_developer_actions(
        self,
        input_data: IntelligenceInput,
        impact_out: ImpactReasoningOutput,
        risk_out: RiskReasoningOutput,
        test_out: TestRecommendationsOutput,
        history_out: HistoryContextOutput,
    ) -> list[DeveloperAction]:
        actions: list[DeveloperAction] = []
        step = 1

        # Step 1: Make code change
        for c in input_data.changed_components:
            actions.append(
                DeveloperAction(
                    step=step,
                    action_type="MODIFY",
                    description=f"Implement proposed logic in '{c.symbol}' ({c.file_path}). Preserve existing argument signature if possible.",
                    target_component=c.symbol,
                )
            )
            step += 1

        # Step 2: Co-updates for paired files if present
        for co in history_out.co_change_patterns[:2]:
            actions.append(
                DeveloperAction(
                    step=step,
                    action_type="CO_UPDATE",
                    description=f"Review '{co.file_b}' as it has historically changed in conjunction with '{co.file_a}'.",
                    target_component=co.file_b,
                )
            )
            step += 1

        # Step 3: Run existing recommended tests
        for suite in test_out.recommended_suites[:3]:
            actions.append(
                DeveloperAction(
                    step=step,
                    action_type="TEST",
                    description=f"Run test suite '{suite.test_module}' ({suite.test_file}) to guard against immediate regressions.",
                    target_component=suite.test_module,
                )
            )
            step += 1

        # Step 4: Write test cases for coverage gaps
        for gap in test_out.coverage_gaps[:2]:
            actions.append(
                DeveloperAction(
                    step=step,
                    action_type="VERIFY",
                    description=f"Add unit test coverage for '{gap.component}': {gap.suggested_test_scenario}",
                    target_component=gap.component,
                )
            )
            step += 1

        # Step 5: Verify sensitive business logic
        if risk_out.sensitive_domains_identified:
            actions.append(
                DeveloperAction(
                    step=step,
                    action_type="MONITOR",
                    description=f"Manually verify sensitive transactions in: {', '.join(risk_out.sensitive_domains_identified)}.",
                    target_component=", ".join(risk_out.sensitive_domains_identified),
                )
            )

        return actions
