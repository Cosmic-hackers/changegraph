"""
repository.py — Repository analysis orchestrator for ChangeGraph.

Ties together all Phase 1 analyzers:
  1. python_ast.py  — parse source files
  2. dependencies.py — build dependency graph
  3. impact.py       — find change impact
  4. tests_mapper.py — identify relevant tests
  5. git_history.py  — gather git context

Provides a single analyze() entry point that accepts a repository path
and a change request description, and returns a structured AnalysisResult.

Change request parsing is intentionally simple in Phase 1:
  - Look for known function/class names mentioned in the request
  - Fall back to keyword matching against module names
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from .python_ast import parse_directory, ParsedModule
from .dependencies import build_graph, DependencyGraph, function_key, module_key
from .impact import ImpactAnalyzer, ImpactResult, ImpactedNode
from .tests_mapper import TestMapper, TestFileMatch
from .git_history import GitHistoryAnalyzer, GitContext


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ChangedComponent:
    key: str
    symbol: str      # e.g. "checkout.calculate_total"
    module: str
    file_path: str
    reason: str      # why this was identified as the changed component


@dataclass
class AnalysisResult:
    """The full output of a repository change analysis."""
    repository_path: str
    change_request: str
    changed_components: list[ChangedComponent] = field(default_factory=list)
    direct_impact: list[ImpactedNode] = field(default_factory=list)
    indirect_impact: list[ImpactedNode] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    recommended_tests: list[TestFileMatch] = field(default_factory=list)
    risk_level: str = "UNKNOWN"
    risk_reasons: list[str] = field(default_factory=list)
    dependency_paths: list[list[str]] = field(default_factory=list)
    git_context: Optional[GitContext] = None
    graph_summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def affected_modules(self) -> list[str]:
        """Unique module names across all directly and indirectly impacted nodes."""
        return sorted({n.module for n in self.direct_impact + self.indirect_impact if n.module})


# ─────────────────────────────────────────────────────────────────────────────
# Change request → symbol resolver
# ─────────────────────────────────────────────────────────────────────────────

# Simple keyword → module hints
_MODULE_KEYWORDS = {
    "checkout": ["checkout"],
    "cart": ["cart"],
    "payment": ["payment"],
    "refund": ["refund"],
    "invoice": ["invoice"],
    "user": ["users"],
    "auth": ["users"],
    "product": ["products"],
    "notification": ["notifications"],
    "discount": ["checkout"],
    "total": ["checkout"],
    "price": ["checkout", "products"],
    "order": ["checkout"],
    "stock": ["products"],
}


def _extract_changed_symbols(
    change_request: str,
    dep_graph: DependencyGraph,
    modules: list[ParsedModule],
) -> list[ChangedComponent]:
    """
    Parse the change request and return the most likely changed components.

    Strategy (deterministic, no LLM):
    1. Look for explicit "module.function" patterns in the request.
    2. Look for known function names mentioned by name.
    3. Fall back to module-level keyword matching.
    """
    request_lower = change_request.lower()
    components: list[ChangedComponent] = []
    seen_keys: set[str] = set()

    # Build a flat index of all function/class names for quick lookup
    all_functions: dict[str, list[tuple[str, str, str]]] = {}  # name → [(module, qname, file)]
    all_modules_index: dict[str, str] = {}  # module_name → file_path

    for mod in modules:
        all_modules_index[mod.module_name] = mod.file_path
        for fn in mod.functions:
            all_functions.setdefault(fn.name.lower(), []).append(
                (mod.module_name, fn.qualified_name, mod.file_path)
            )
            if fn.qualified_name.lower() != fn.name.lower():
                all_functions.setdefault(fn.qualified_name.lower(), []).append(
                    (mod.module_name, fn.qualified_name, mod.file_path)
                )

    # Strategy 1: explicit "module.function" or "module.Class.method" in request
    dot_pattern = re.findall(r"\b([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_.]*)\b", request_lower)
    for token in dot_pattern:
        parts = token.split(".")
        if parts[0] in all_modules_index:
            # Try to resolve function key
            remainder = ".".join(parts[1:])
            candidates = dep_graph.resolve_symbol(f"{parts[0]}.{remainder}")
            for key in candidates:
                if key not in seen_keys:
                    seen_keys.add(key)
                    node = dep_graph.get_node_data(key)
                    if node:
                        components.append(ChangedComponent(
                            key=key,
                            symbol=f"{node['module']}.{node['name']}",
                            module=node["module"],
                            file_path=node.get("file_path", ""),
                            reason=f"Explicitly mentioned as '{token}' in the change request.",
                        ))

    # Strategy 2: bare function names in the request
    for fn_name, occurrences in all_functions.items():
        if fn_name in request_lower:
            for module_name, qname, file_path in occurrences:
                key = function_key(module_name, qname)
                if key not in seen_keys and dep_graph.graph.has_node(key):
                    seen_keys.add(key)
                    components.append(ChangedComponent(
                        key=key,
                        symbol=f"{module_name}.{qname}",
                        module=module_name,
                        file_path=file_path,
                        reason=f"Function name '{qname}' appears in the change request.",
                    ))

    # Strategy 3: keyword → module fallback
    if not components:
        matched_modules: set[str] = set()
        for keyword, mods in _MODULE_KEYWORDS.items():
            if keyword in request_lower:
                for m in mods:
                    matched_modules.add(m)

        for mod_name in matched_modules:
            mkey = module_key(mod_name)
            if dep_graph.graph.has_node(mkey) and mkey not in seen_keys:
                seen_keys.add(mkey)
                file_path = all_modules_index.get(mod_name, "")
                components.append(ChangedComponent(
                    key=mkey,
                    symbol=mod_name,
                    module=mod_name,
                    file_path=file_path,
                    reason=f"Keyword match: '{mod_name}' module is relevant to the change request.",
                ))

    return components


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class RepositoryAnalyzer:
    """
    Orchestrates the full Phase 1 analysis pipeline.

    Usage:
        analyzer = RepositoryAnalyzer("./sample_repos/test_shop")
        result = analyzer.analyze("Change calculate_total to support discounts")
    """

    def __init__(self, repository_path: str):
        self.repository_path = os.path.abspath(repository_path)

    def analyze(self, change_request: str) -> AnalysisResult:
        """Run the full analysis pipeline and return a structured result."""
        result = AnalysisResult(
            repository_path=self.repository_path,
            change_request=change_request,
        )

        # ── Step 1: Parse repository
        modules = parse_directory(self.repository_path)
        if not modules:
            result.warnings.append("No Python files found in the repository.")
            return result

        # ── Step 2: Build dependency graph
        dep_graph = build_graph(modules)
        result.graph_summary = dep_graph.summary()

        # ── Step 3: Identify changed components from the change request
        changed_components = _extract_changed_symbols(change_request, dep_graph, modules)
        result.changed_components = changed_components

        if not changed_components:
            result.warnings.append(
                "Could not identify specific changed components from the change request. "
                "Try mentioning a function name (e.g. 'calculate_total') explicitly."
            )
            return result

        # ── Step 4: Impact analysis
        changed_keys = [c.key for c in changed_components]
        impact_analyzer = ImpactAnalyzer(dep_graph)
        impact: ImpactResult = impact_analyzer.analyze(changed_keys)

        result.direct_impact = impact.direct
        result.indirect_impact = impact.indirect
        result.affected_files = impact.affected_files
        result.risk_level = impact.risk_level
        result.risk_reasons = impact.risk_reasons

        # Collect dependency paths for reporting
        result.dependency_paths = [
            node.path for node in impact.all_affected if node.path
        ]

        # ── Step 5: Test mapping
        affected_module_names = list(
            {c.module for c in changed_components} | set(impact.affected_modules)
        )
        affected_fn_names = [
            dep_graph.get_node_data(n.key).get("name", "")
            for n in impact.all_affected
            if dep_graph.get_node_data(n.key)
        ] + [c.symbol.split(".")[-1] for c in changed_components]

        test_mapper = TestMapper(modules)
        result.recommended_tests = test_mapper.find_tests(
            affected_modules=affected_module_names,
            affected_function_names=affected_fn_names,
        )

        # ── Step 6: Git history context (best-effort)
        all_affected_files = list(
            {c.file_path for c in changed_components} | set(impact.affected_files)
        )
        git_analyzer = GitHistoryAnalyzer(self.repository_path)
        result.git_context = git_analyzer.get_context_for_files(all_affected_files)

        return result
