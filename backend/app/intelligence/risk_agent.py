"""
backend/app/intelligence/risk_agent.py — Risk Reasoning Agent for ChangeGraph.

Evaluates:
- Risk level grounded in Phase 1 deterministic analysis
- Concrete failure scenarios based on real dependencies
- Impact on sensitive domains (finance, payment, authentication)
- Uncertainty or lack of test coverage

Strict rule: Must NOT invent evidence or non-existent failure modes.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    RiskReasoningOutput,
    FailureScenario,
)
from .provider import AIProvider

logger = logging.getLogger("changegraph.intelligence.risk_agent")


class RiskAgent:
    """
    Evaluates failure severity and edge cases using Phase 1 deterministic evidence.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def run(self, input_data: IntelligenceInput) -> RiskReasoningOutput:
        if self.provider.is_available() and self.provider.name != "Deterministic Grounded Reasoner":
            try:
                ai_output = self._run_ai(input_data)
                if ai_output:
                    return ai_output
            except Exception as exc:
                logger.warning("AI provider failed in RiskAgent, falling back to deterministic reasoning: %s", exc)

        return self._run_deterministic(input_data)

    def _run_ai(self, input_data: IntelligenceInput) -> Optional[RiskReasoningOutput]:
        system_prompt = (
            "You are the ChangeGraph Risk Agent powered by IBM Bob. "
            "Evaluate risk ONLY based on the provided deterministic impact facts and code coupling evidence. "
            "Do NOT invent un-evidenced failure modes or claim affected components that were not listed. "
            "Output your answer strictly in valid JSON matching the required schema."
        )

        facts = {
            "deterministic_risk_level": input_data.deterministic_risk_level,
            "deterministic_risk_reasons": input_data.deterministic_risk_reasons,
            "changed_components": [c.symbol for c in input_data.changed_components],
            "affected_modules": list(input_data.known_modules),
            "direct_impact_count": len(input_data.direct_impact),
            "indirect_impact_count": len(input_data.indirect_impact),
        }

        prompt = (
            f"Phase 1 Risk and Impact Facts:\n{json.dumps(facts, indent=2)}\n\n"
            f"Produce a JSON response with:\n"
            f"- 'assessed_risk_level': 'LOW', 'MEDIUM', or 'HIGH'\n"
            f"- 'risk_justification': list of concrete justification bullet points\n"
            f"- 'failure_scenarios': list of objects with 'component', 'scenario_description', 'potential_consequence', 'mitigation_advice'\n"
            f"- 'sensitive_domains_identified': list of sensitive domains (e.g. payment, refund, auth)\n"
            f"- 'uncertainties': list of unknowns or areas needing verification"
        )

        raw = self.provider.generate(prompt=prompt, system_prompt=system_prompt, json_schema=RiskReasoningOutput)
        data = json.loads(raw)
        return RiskReasoningOutput.model_validate(data)

    def _run_deterministic(self, input_data: IntelligenceInput) -> RiskReasoningOutput:
        # Align with Phase 1 risk level
        level = input_data.deterministic_risk_level
        if level not in ("LOW", "MEDIUM", "HIGH"):
            level = "MEDIUM"

        justifications = list(input_data.deterministic_risk_reasons)
        if not justifications:
            justifications.append("Risk evaluated based on downstream dependency count and call coupling.")

        # Detect sensitive domains from known affected modules
        sensitive_keywords = {"payment", "refund", "invoice", "billing", "auth", "user"}
        sensitive_hits = [
            mod for mod in input_data.known_modules
            if any(kw in mod.lower() for kw in sensitive_keywords)
        ]

        failure_scenarios: list[FailureScenario] = []
        changed_symbols = [c.symbol for c in input_data.changed_components]
        target_name = changed_symbols[0] if changed_symbols else "target component"

        # Construct concrete failure scenarios for sensitive modules
        if any("refund" in mod for mod in sensitive_hits):
            failure_scenarios.append(
                FailureScenario(
                    component="refund",
                    scenario_description=(
                        f"Modifications to '{target_name}' may alter return values or parameter contracts "
                        "expected by refund calculation routines."
                    ),
                    potential_consequence=(
                        "Financial discrepancy: Inaccurate refund amounts computed for processed orders."
                    ),
                    mitigation_advice=(
                        "Add regression tests verifying refund calculation parity for discounted and undiscounted orders."
                    ),
                )
            )

        if any("payment" in mod for mod in sensitive_hits):
            failure_scenarios.append(
                FailureScenario(
                    component="payment",
                    scenario_description=(
                        f"Downstream transaction processing may receive unexpected totals or types from '{target_name}'."
                    ),
                    potential_consequence="Payment gateway rejection or incorrect charge amounts.",
                    mitigation_advice="Verify checkout-to-payment payload contracts with integration tests.",
                )
            )

        # General failure scenario for direct dependents
        if input_data.direct_impact:
            first_dep = input_data.direct_impact[0]
            failure_scenarios.append(
                FailureScenario(
                    component=f"{first_dep.module}.{first_dep.name}",
                    scenario_description=(
                        f"Direct caller '{first_dep.name}' may break if function signature or return type changes."
                    ),
                    potential_consequence="Runtime TypeError or unexpected downstream state.",
                    mitigation_advice="Ensure backward compatibility in signature or update all call sites.",
                )
            )

        uncertainties = []
        if not input_data.recommended_tests:
            uncertainties.append("No explicit test files were mapped to the affected components.")
        else:
            tested_mods = {t.module_name for t in input_data.recommended_tests}
            untested = [m for m in input_data.known_modules if not any(m in tm for tm in tested_mods) and not m.startswith("test_")]
            if untested:
                uncertainties.append(f"Affected modules without direct test mapping: {', '.join(untested)}.")

        return RiskReasoningOutput(
            assessed_risk_level=level,  # type: ignore
            risk_justification=justifications,
            failure_scenarios=failure_scenarios,
            sensitive_domains_identified=sorted(list(set(sensitive_hits))),
            uncertainties=uncertainties,
        )
