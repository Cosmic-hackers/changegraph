"""
simulation/engine.py — Phase 5 What-If Change Simulation Engine.

Read-only. Evaluates hypothetical scenarios against the current deterministic graph.
Does not edit files, execute generated code, create commits, or modify GitHub.
"""
from __future__ import annotations

import os
import logging
from typing import Any

from ..analyzers.repository import RepositoryAnalyzer
from ..intelligence.orchestrator import IntelligenceOrchestrator
from .models import SimulationRequest, WhatIfReport

logger = logging.getLogger("changegraph.simulation.engine")


class SimulationEngine:
    """
    Evaluates what-if scenarios against the current dependency graph.
    Separates deterministic current evidence from hypothetical predicted impact.
    """

    def simulate(self, request: SimulationRequest) -> WhatIfReport:
        repo_path = os.path.abspath(request.repository)
        scenario = request.scenario.strip()

        # Run Phase 1 deterministic analysis using scenario as change request
        analyzer = RepositoryAnalyzer(repo_path)
        try:
            result = analyzer.analyze(scenario)
        except Exception as exc:
            logger.warning("Simulation analysis failed: %s", exc)
            return WhatIfReport(
                scenario=scenario,
                simulation_type="what_if",
                deterministic_evidence={"sufficient": False, "warnings": [str(exc)]},
                hypothetical_impact=[],
                developer_actions=[],
                uncertainty=["Analysis could not be completed for this scenario."],
            )

        sufficient = bool(result.changed_components)

        current_evidence = []
        for c in result.changed_components:
            current_evidence.append(f"Symbol '{c.symbol}' found in module '{c.module}' ({c.file_path}).")
        for r in result.risk_reasons[:3]:
            current_evidence.append(r)

        hypothetical_impact = []
        if sufficient:
            for n in result.direct_impact[:6]:
                hypothetical_impact.append(
                    f"Removing or changing '{n.name}' would directly affect '{n.module}.{n.name}' (depth {n.depth})."
                )
            for n in result.indirect_impact[:4]:
                hypothetical_impact.append(
                    f"Transitively, '{n.module}.{n.name}' would also be affected (depth {n.depth})."
                )

        developer_actions = []
        for t in result.recommended_tests[:4]:
            developer_actions.append(f"Run '{t.module_name}' ({t.file_path}) to verify no regressions.")
        if result.risk_level in ("HIGH", "MEDIUM"):
            developer_actions.append(f"Risk level is {result.risk_level} — manual review of affected modules is advised.")

        uncertainty = []
        if not sufficient:
            uncertainty.append("The scenario target could not be resolved in the current repository graph.")
        if not result.git_context or not result.git_context.git_available:
            uncertainty.append("Git history was unavailable — co-change patterns could not be assessed.")

        # Run intelligence over the result
        intelligence = None
        try:
            orchestrator = IntelligenceOrchestrator()
            intelligence = orchestrator.run_intelligence(result)
        except Exception as exc:
            logger.warning("Intelligence synthesis failed in simulation: %s", exc)

        det_evidence: dict[str, Any] = {
            "sufficient": sufficient,
            "current_evidence": current_evidence,
            "direct_impact": [
                {"name": n.name, "module": n.module, "depth": n.depth} for n in result.direct_impact
            ],
            "indirect_impact": [
                {"name": n.name, "module": n.module, "depth": n.depth} for n in result.indirect_impact
            ],
            "affected_tests": [t.file_path for t in result.recommended_tests],
            "dependency_paths": result.dependency_paths[:5],
            "warnings": result.warnings,
        }

        return WhatIfReport(
            scenario=scenario,
            simulation_type="what_if",
            deterministic_evidence=det_evidence,
            hypothetical_impact=hypothetical_impact,
            developer_actions=developer_actions,
            uncertainty=uncertainty,
            intelligence=intelligence,
        )
