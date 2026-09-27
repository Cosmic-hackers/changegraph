"""
impact.py — Change impact finder for ChangeGraph.

Given a DependencyGraph and a set of changed symbols (functions/classes/modules),
this module finds:
  - Direct dependents (nodes that directly call or import the changed symbol)
  - Indirect dependents (nodes reachable through transitive edges)
  - Dependency paths explaining WHY each node is affected

All analysis is deterministic graph traversal — no LLM involvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import networkx as nx

from .dependencies import DependencyGraph, module_key, function_key


@dataclass
class ImpactedNode:
    """A single node identified as being impacted by a change."""
    key: str                         # graph node key
    node_type: str                   # "function" | "class" | "module"
    name: str                        # human-readable symbol name
    module: str                      # module (file stem) it lives in
    file_path: str
    depth: int                       # 1 = direct, 2+ = indirect
    path: list[str] = field(default_factory=list)   # chain of node keys from changed → this
    explanation: str = ""            # human-readable "why" sentence


def _make_explanation(path: list[str], graph: nx.DiGraph) -> str:
    """
    Build a human-readable explanation sentence from a dependency path.

    path[0] is the changed node; path[-1] is the impacted node.
    """
    if len(path) < 2:
        return ""

    def label(key: str) -> str:
        d = graph.nodes.get(key, {})
        t = d.get("type", "")
        n = d.get("name", key)
        m = d.get("module", "")
        if t == "function":
            return f"{m}.{n}()" if m else f"{n}()"
        if t == "class":
            return f"{m}.{n}" if m else n
        return m or key

    parts = []
    for i in range(len(path) - 1):
        src = label(path[i])
        dst = label(path[i + 1])
        edge_data = graph.get_edge_data(path[i], path[i + 1]) or {}
        kind = edge_data.get("kind", "depends on")
        if kind == "calls":
            parts.append(f"{dst} calls {src}")
        elif kind == "imports":
            parts.append(f"{dst} imports {src}")
        elif kind == "contains":
            parts.append(f"{src} contains {dst}")
        elif kind == "inherits":
            parts.append(f"{dst} inherits from {src}")
        else:
            parts.append(f"{dst} depends on {src}")

    # Build a single sentence describing the chain
    changed_label = label(path[0])
    impacted_label = label(path[-1])
    chain = " → ".join(label(p) for p in path)
    return (
        f"{impacted_label} is potentially affected because: {chain}."
    )


class ImpactAnalyzer:
    """
    Performs change impact analysis on a DependencyGraph.

    Usage:
        analyzer = ImpactAnalyzer(dep_graph)
        result = analyzer.analyze(changed_keys=["func:checkout.calculate_total"])
    """

    def __init__(self, dep_graph: DependencyGraph):
        self.dep_graph = dep_graph
        self.graph = dep_graph.graph

    def analyze(
        self,
        changed_keys: list[str],
        max_depth: int = 6,
    ) -> "ImpactResult":
        """
        Find all nodes impacted by changes to the specified keys.

        Returns an ImpactResult with direct and indirect impacted nodes,
        dependency paths, and an overall risk classification.
        """
        # Reverse the graph: edges now point from dependents to dependencies,
        # so we can traverse "who depends on X"
        reverse_graph = self.graph.reverse(copy=False)

        direct: list[ImpactedNode] = []
        indirect: list[ImpactedNode] = []
        seen: set[str] = set(changed_keys)

        # BFS from each changed key through the reversed graph
        for root_key in changed_keys:
            if not self.graph.has_node(root_key):
                continue

            # BFS: queue of (current_node, path_so_far, depth)
            queue: list[tuple[str, list[str], int]] = [(root_key, [root_key], 0)]

            while queue:
                current, path, depth = queue.pop(0)
                if depth >= max_depth:
                    continue

                for neighbor in reverse_graph.successors(current):
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)

                    edge_data = self.graph.get_edge_data(neighbor, current) or {}
                    kind = edge_data.get("kind", "")

                    # "contains" edges point module→function; reversing them
                    # would say "function is affected because module contains it"
                    # — which isn't useful.  Skip them in impact traversal.
                    if kind == "contains":
                        continue

                    node_depth = depth + 1
                    full_path = path + [neighbor]

                    node_data = self.graph.nodes.get(neighbor, {})
                    impacted = ImpactedNode(
                        key=neighbor,
                        node_type=node_data.get("type", "unknown"),
                        name=node_data.get("name", neighbor),
                        module=node_data.get("module", ""),
                        file_path=node_data.get("file_path", ""),
                        depth=node_depth,
                        path=full_path,
                        explanation=_make_explanation(full_path, self.graph),
                    )

                    if node_depth == 1:
                        direct.append(impacted)
                    else:
                        indirect.append(impacted)

                    queue.append((neighbor, full_path, node_depth))

        risk = _classify_risk(changed_keys, direct, indirect, self.graph)

        return ImpactResult(
            changed_keys=changed_keys,
            direct=direct,
            indirect=indirect,
            risk_level=risk.level,
            risk_reasons=risk.reasons,
        )


@dataclass
class RiskClassification:
    level: str          # "LOW" | "MEDIUM" | "HIGH"
    reasons: list[str]


def _classify_risk(
    changed_keys: list[str],
    direct: list[ImpactedNode],
    indirect: list[ImpactedNode],
    graph: nx.DiGraph,
) -> RiskClassification:
    """
    Classify change risk as LOW / MEDIUM / HIGH based on concrete evidence.
    Never returns an arbitrary numeric score.
    """
    reasons: list[str] = []
    score = 0

    total_direct = len(direct)
    total_indirect = len(indirect)
    total_affected = total_direct + total_indirect

    if total_direct >= 4:
        reasons.append(f"Changed symbol has {total_direct} direct dependents across multiple modules.")
        score += 3
    elif total_direct >= 2:
        reasons.append(f"Changed symbol is called by {total_direct} other components.")
        score += 2
    elif total_direct == 1:
        reasons.append("Changed symbol has 1 direct dependent.")
        score += 1

    if total_indirect >= 3:
        reasons.append(f"Change propagates transitively to {total_indirect} additional components.")
        score += 2
    elif total_indirect >= 1:
        reasons.append(f"Change propagates transitively to {total_indirect} indirect component(s).")
        score += 1

    # Check if any impacted module is finance/payment/refund-related
    sensitive_keywords = {"payment", "refund", "invoice", "billing", "auth", "user"}
    sensitive_hits = [
        n for n in direct + indirect
        if any(kw in n.module.lower() for kw in sensitive_keywords)
    ]
    if sensitive_hits:
        names = ", ".join(sorted({n.module for n in sensitive_hits}))
        reasons.append(f"Affected modules include sensitive business logic: {names}.")
        score += 2

    # Check if any changed key is a widely-called function
    for key in changed_keys:
        if not graph.has_node(key):
            continue
        in_degree = graph.in_degree(key)
        if in_degree >= 3:
            reasons.append(f"'{key}' is called from {in_degree} locations — high coupling.")
            score += 2
        elif in_degree >= 2:
            reasons.append(f"'{key}' is called from {in_degree} locations.")
            score += 1

    if score >= 5:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    if not reasons:
        reasons.append("No significant downstream dependencies detected.")

    return RiskClassification(level=level, reasons=reasons)


@dataclass
class ImpactResult:
    """The full output of an impact analysis."""
    changed_keys: list[str]
    direct: list[ImpactedNode]
    indirect: list[ImpactedNode]
    risk_level: str               # "LOW" | "MEDIUM" | "HIGH"
    risk_reasons: list[str]

    @property
    def all_affected(self) -> list[ImpactedNode]:
        return self.direct + self.indirect

    @property
    def affected_modules(self) -> list[str]:
        return sorted({n.module for n in self.all_affected if n.module})

    @property
    def affected_files(self) -> list[str]:
        return sorted({n.file_path for n in self.all_affected if n.file_path})
