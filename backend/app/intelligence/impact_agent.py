"""
backend/app/intelligence/impact_agent.py — Impact Reasoning Agent for ChangeGraph.

Takes deterministic AST and graph traversal results from Phase 1 and explains:
- What components are affected
- Why each component is affected (propagation chain)
- Key downstream workflows affected

Strict rule: Must NOT invent dependencies. Every statement is grounded in Phase 1 evidence.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    ImpactReasoningOutput,
    WorkflowImpact,
)
from .provider import AIProvider

logger = logging.getLogger("changegraph.intelligence.impact_agent")


class ImpactAgent:
    """
    Reasons over code dependency propagation using Phase 1 graph data.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def run(self, input_data: IntelligenceInput) -> ImpactReasoningOutput:
        """Execute impact reasoning for the given change analysis."""
        # If external provider is active, attempt AI reasoning with strict prompt
        if self.provider.is_available() and self.provider.name != "Deterministic Grounded Reasoner":
            try:
                ai_output = self._run_ai(input_data)
                if ai_output:
                    return ai_output
            except Exception as exc:
                logger.warning("AI provider failed in ImpactAgent, falling back to deterministic reasoning: %s", exc)

        # Fallback to grounded deterministic synthesis
        return self._run_deterministic(input_data)

    def _run_ai(self, input_data: IntelligenceInput) -> Optional[ImpactReasoningOutput]:
        system_prompt = (
            "You are the ChangeGraph Impact Agent powered by IBM Bob. "
            "Your job is to reason about downstream code impact based EXCLUSIVELY on the provided dependency facts. "
            "CRITICAL: Do NOT invent, assume, or hallucinate any dependencies. "
            "You must ONLY reference functions, modules, and relationships explicitly provided in the facts. "
            "Output your answer strictly in valid JSON matching the required schema."
        )

        # Strip raw PR diff from the prompt — keep only the human-readable title
        raw_cr = input_data.change_request or ""
        pipe_idx = raw_cr.find(" | ")
        clean_cr = (raw_cr[:pipe_idx] if pipe_idx > 0 else raw_cr)[:200]

        facts_summary = {
            "change_request": clean_cr,
            "changed_components": [
                {"symbol": c.symbol, "module": c.module, "reason": c.reason}
                for c in input_data.changed_components
            ],
            "direct_impact": [
                {"name": n.name, "module": n.module, "explanation": n.explanation, "depth": n.depth}
                for n in input_data.direct_impact
            ],
            "indirect_impact": [
                {"name": n.name, "module": n.module, "depth": n.depth, "path": n.path}
                for n in input_data.indirect_impact[:10]  # cap to top 10 for prompt efficiency
            ],
        }

        prompt = (
            f"Given these deterministic dependency facts from Phase 1:\n"
            f"{json.dumps(facts_summary, indent=2)}\n\n"
            f"Produce a JSON response with:\n"
            f"- 'summary': Clear summary of impacted components\n"
            f"- 'affected_workflows': list of items with 'workflow_name', 'affected_components', 'propagation_chain', 'impact_explanation', 'criticality' (CRITICAL/MAJOR/MINOR)\n"
            f"- 'propagation_breakdown': list of strings explaining step-by-step propagation\n"
            f"- 'grounded_symbols': list of exact symbol strings referenced"
        )

        raw = self.provider.generate(prompt=prompt, system_prompt=system_prompt, json_schema=ImpactReasoningOutput)
        data = json.loads(raw)
        return ImpactReasoningOutput.model_validate(data)

    def _run_deterministic(self, input_data: IntelligenceInput) -> ImpactReasoningOutput:
        """Grounded synthesis generated directly from the dependency graph."""
        changed_names = [c.symbol for c in input_data.changed_components]
        direct_count = len(input_data.direct_impact)
        indirect_count = len(input_data.indirect_impact)

        target_str = ", ".join(changed_names) if changed_names else "unspecified component"
        summary = (
            f"Modifying '{target_str}' directly impacts {direct_count} component(s) "
            f"and propagates transitively to {indirect_count} indirect component(s)."
        )

        workflows: list[WorkflowImpact] = []
        propagation_breakdown: list[str] = []
        grounded_symbols: list[str] = list(changed_names)

        # Group impacts by module
        module_groups: dict[str, list[str]] = {}
        for node in input_data.all_impacted_symbols:
            mod = node.module or "core"
            module_groups.setdefault(mod, []).append(node.name)
            grounded_symbols.append(f"{node.module}.{node.name}" if node.module else node.name)

        # Build workflow impacts for recognized module groups
        for mod, funcs in module_groups.items():
            funcs_sample = ", ".join(funcs[:3])
            chain = " → ".join([c.symbol for c in input_data.changed_components] + [mod])
            
            criticality = "MAJOR"
            if any(term in mod.lower() for term in ["payment", "refund", "auth", "checkout"]):
                criticality = "CRITICAL"
            elif mod.startswith("test_"):
                criticality = "MINOR"

            workflows.append(
                WorkflowImpact(
                    workflow_name=f"{mod.replace('_', ' ').title()} Workflow",
                    affected_components=[f"{mod}.{fn}" for fn in funcs[:5]],
                    propagation_chain=chain,
                    impact_explanation=(
                        f"Module '{mod}' depends on upstream changes in '{target_str}'. "
                        f"Affected symbols include: {funcs_sample}."
                    ),
                    criticality=criticality,
                )
            )

        # Build propagation breakdown from direct & indirect nodes
        for node in input_data.direct_impact:
            exp = node.explanation or f"{node.module}.{node.name} directly calls or imports the changed target."
            propagation_breakdown.append(f"[Direct - Depth 1] {node.module}.{node.name}: {exp}")

        for node in input_data.indirect_impact[:6]:
            chain_str = " → ".join(node.path) if node.path else f"depth {node.depth}"
            propagation_breakdown.append(f"[Indirect - Depth {node.depth}] {node.module}.{node.name} via {chain_str}")

        return ImpactReasoningOutput(
            summary=summary,
            affected_workflows=workflows,
            propagation_breakdown=propagation_breakdown,
            grounded_symbols=list(set(grounded_symbols)),
        )
