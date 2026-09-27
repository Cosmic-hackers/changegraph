"""
backend/app/intelligence/test_agent.py — Test Recommendation Agent for ChangeGraph.

Evaluates:
- Existing test suites to run immediately
- Missing test coverage / test gaps in affected modules
- Specific regression scenarios to guard against
- Explanation grounded in call/import dependencies
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    TestRecommendationsOutput,
    RecommendedTestItem,
    TestCoverageGap,
)
from .provider import AIProvider

logger = logging.getLogger("changegraph.intelligence.test_agent")


class TestAgent:
    """
    Identifies test suites to run, test gaps, and regression scenarios.
    """
    __test__ = False

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def run(self, input_data: IntelligenceInput) -> TestRecommendationsOutput:
        if self.provider.is_available() and self.provider.name != "Deterministic Grounded Reasoner":
            try:
                ai_output = self._run_ai(input_data)
                if ai_output:
                    return ai_output
            except Exception as exc:
                logger.warning("AI provider failed in TestAgent, falling back to deterministic reasoning: %s", exc)

        return self._run_deterministic(input_data)

    def _run_ai(self, input_data: IntelligenceInput) -> Optional[TestRecommendationsOutput]:
        system_prompt = (
            "You are the ChangeGraph Test Agent powered by IBM Bob. "
            "Recommend tests and identify coverage gaps strictly based on the provided affected code and mapped tests. "
            "Output your answer strictly in valid JSON matching the required schema."
        )

        facts = {
            "changed_components": [c.symbol for c in input_data.changed_components],
            "affected_modules": list(input_data.known_modules),
            "recommended_tests": [
                {
                    "file_path": t.file_path,
                    "module_name": t.module_name,
                    "match_reasons": t.match_reasons,
                    "matched_functions": t.matched_functions,
                }
                for t in input_data.recommended_tests
            ],
        }

        prompt = (
            f"Phase 1 Test Mapping Facts:\n{json.dumps(facts, indent=2)}\n\n"
            f"Produce a JSON response with:\n"
            f"- 'summary': Overall testing strategy summary\n"
            f"- 'recommended_suites': list of objects with 'test_file', 'test_module', 'priority' (HIGH/MEDIUM/LOW), 'rationale', 'target_functions'\n"
            f"- 'coverage_gaps': list of objects with 'component', 'gap_description', 'suggested_test_scenario'\n"
            f"- 'regression_scenarios': list of concrete regression scenarios to test"
        )

        raw = self.provider.generate(prompt=prompt, system_prompt=system_prompt, json_schema=TestRecommendationsOutput)
        data = json.loads(raw)
        return TestRecommendationsOutput.model_validate(data)

    def _run_deterministic(self, input_data: IntelligenceInput) -> TestRecommendationsOutput:
        suites: list[RecommendedTestItem] = []
        changed_mods = {c.module for c in input_data.changed_components if c.module}

        for t in input_data.recommended_tests:
            # Assign priority: HIGH if matches changed module directly, MEDIUM otherwise
            is_direct = any(mod in t.module_name for mod in changed_mods)
            priority = "HIGH" if is_direct else "MEDIUM"

            primary_reason = t.match_reasons[0] if t.match_reasons else "Mapped from dependency impact"
            suites.append(
                RecommendedTestItem(
                    test_file=t.file_path,
                    test_module=t.module_name,
                    priority=priority,  # type: ignore
                    rationale=primary_reason,
                    target_functions=t.matched_functions,
                )
            )

        # Detect coverage gaps: affected non-test modules with no matching test suite
        tested_mod_stems = {
            t.module_name.replace("test_", "").replace("_test", "")
            for t in input_data.recommended_tests
        }
        coverage_gaps: list[TestCoverageGap] = []
        for mod in input_data.known_modules:
            if not mod.startswith("test_") and mod not in tested_mod_stems:
                coverage_gaps.append(
                    TestCoverageGap(
                        component=mod,
                        gap_description=(
                            f"Module '{mod}' is impacted by upstream changes but has no dedicated test file "
                            f"(expected test_{mod}.py or {mod}_test.py)."
                        ),
                        suggested_test_scenario=(
                            f"Create unit tests verifying '{mod}' handles updated inputs and returns from upstream dependencies."
                        ),
                    )
                )

        # Concrete regression scenarios based on changed components
        regression_scenarios: list[str] = []
        for c in input_data.changed_components:
            regression_scenarios.append(
                f"Verify '{c.symbol}' maintains expected return contract with legacy callers."
            )
            regression_scenarios.append(
                f"Test boundary conditions and edge cases (e.g. None, empty collections, zero values) for '{c.symbol}'."
            )

        for dep in input_data.direct_impact[:3]:
            regression_scenarios.append(
                f"Verify '{dep.module}.{dep.name}' executes without error when '{dep.path[0]}' is executed under modified logic."
            )

        summary = (
            f"Identified {len(suites)} existing test suite(s) to execute immediately "
            f"and {len(coverage_gaps)} coverage gap(s) requiring supplemental test verification."
        )

        return TestRecommendationsOutput(
            recommended_suites=suites,
            coverage_gaps=coverage_gaps,
            regression_scenarios=regression_scenarios,
            summary=summary,
        )
