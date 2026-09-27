"""
dependencies.py — Dependency graph builder for ChangeGraph.

Takes a list of ParsedModules and constructs a directed NetworkX graph where:
  - Nodes are qualified symbol keys: "<module>.<qualified_name>"
  - Edges represent "A depends on B" (A calls B, A imports B, etc.)

Node types:
  "module"    — a whole Python file
  "function"  — a function or method
  "class"     — a class definition

Edge types (stored in edge attribute "kind"):
  "calls"     — function A calls function B
  "imports"   — module A imports module B
  "contains"  — module/class A contains function/class B
  "inherits"  — class A inherits from class B
"""

import networkx as nx
from typing import Optional

from .python_ast import ParsedModule, FunctionInfo, ClassInfo


# ─────────────────────────────────────────────────────────────────────────────
# Key helpers
# ─────────────────────────────────────────────────────────────────────────────

def module_key(module_name: str) -> str:
    return f"module:{module_name}"


def function_key(module_name: str, qualified_name: str) -> str:
    return f"func:{module_name}.{qualified_name}"


def class_key(module_name: str, class_name: str) -> str:
    return f"class:{module_name}.{class_name}"


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

class DependencyGraph:
    """
    Directed dependency graph over a parsed Python repository.

    Nodes carry metadata attributes (type, name, module, file_path, lineno).
    Edges carry a "kind" attribute describing the relationship.
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        # Lookup maps built during construction
        # function_name → list of function_key (same name may exist in multiple modules)
        self._func_name_index: dict[str, list[str]] = {}
        # module_name → module_key
        self._module_index: dict[str, str] = {}
        # file_path → module_name
        self._path_to_module: dict[str, str] = {}

    # ------------------------------------------------------------------ build

    def build(self, modules: list[ParsedModule]) -> None:
        """Populate the graph from a list of ParsedModules."""
        # Pass 1: add all nodes
        for mod in modules:
            self._add_module_nodes(mod)

        # Pass 2: add all edges (requires all nodes to exist first)
        for mod in modules:
            self._add_module_edges(mod)

    def _add_module_nodes(self, mod: ParsedModule) -> None:
        mkey = module_key(mod.module_name)
        self._module_index[mod.module_name] = mkey
        self._path_to_module[mod.file_path] = mod.module_name
        self.graph.add_node(
            mkey,
            type="module",
            name=mod.module_name,
            module=mod.module_name,
            file_path=mod.file_path,
            lineno=1,
        )

        for cls in mod.classes:
            ckey = class_key(mod.module_name, cls.name)
            self.graph.add_node(
                ckey,
                type="class",
                name=cls.name,
                module=mod.module_name,
                file_path=mod.file_path,
                lineno=cls.lineno,
            )

        for fn in mod.functions:
            fkey = function_key(mod.module_name, fn.qualified_name)
            self.graph.add_node(
                fkey,
                type="function",
                name=fn.qualified_name,
                module=mod.module_name,
                file_path=mod.file_path,
                lineno=fn.lineno,
            )
            # Index by bare name for call resolution
            self._func_name_index.setdefault(fn.name, []).append(fkey)
            if fn.qualified_name != fn.name:
                # also index by qualified name
                self._func_name_index.setdefault(fn.qualified_name, []).append(fkey)

    def _add_module_edges(self, mod: ParsedModule) -> None:
        mkey = module_key(mod.module_name)

        # Module contains its functions and classes
        for fn in mod.functions:
            fkey = function_key(mod.module_name, fn.qualified_name)
            self.graph.add_edge(mkey, fkey, kind="contains")

        for cls in mod.classes:
            ckey = class_key(mod.module_name, cls.name)
            self.graph.add_edge(mkey, ckey, kind="contains")

        # Module import edges
        for imp in mod.imports:
            target_module = imp.module.split(".")[0]  # top-level module name
            if target_module in self._module_index:
                self.graph.add_edge(
                    mkey,
                    self._module_index[target_module],
                    kind="imports",
                )

        # Function call edges
        for fn in mod.functions:
            fkey = function_key(mod.module_name, fn.qualified_name)
            for called_name in fn.calls:
                # Resolve call to known function keys
                candidates = self._func_name_index.get(called_name, [])
                for target_fkey in candidates:
                    if target_fkey != fkey:  # skip self-calls
                        self.graph.add_edge(fkey, target_fkey, kind="calls")

        # Class inheritance edges
        for cls in mod.classes:
            ckey = class_key(mod.module_name, cls.name)
            for base_name in cls.bases:
                base_candidates = [
                    class_key(m, base_name)
                    for m in self._module_index
                    if self.graph.has_node(class_key(m, base_name))
                ]
                for base_ckey in base_candidates:
                    self.graph.add_edge(ckey, base_ckey, kind="inherits")

    # ─────────────────────────────────────────────────────────────────────────
    # Query helpers
    # ─────────────────────────────────────────────────────────────────────────

    def get_node_data(self, key: str) -> Optional[dict]:
        """Return node attribute dict, or None if not in graph."""
        if self.graph.has_node(key):
            return dict(self.graph.nodes[key])
        return None

    def nodes_for_module(self, module_name: str) -> list[str]:
        """Return all node keys that belong to the given module."""
        return [
            n for n, d in self.graph.nodes(data=True)
            if d.get("module") == module_name
        ]

    def resolve_symbol(self, symbol: str) -> list[str]:
        """
        Given a symbol string like "checkout.calculate_total" or
        "calculate_total", return matching node keys.
        """
        # Try direct key forms first
        candidates = []
        for prefix in ("func:", "class:", "module:"):
            key = f"{prefix}{symbol}"
            if self.graph.has_node(key):
                candidates.append(key)

        # Fall back to name-index lookup
        if not candidates:
            candidates = list(self._func_name_index.get(symbol, []))

        return candidates

    def callers_of(self, func_key: str) -> list[str]:
        """Return all function/module nodes that have a 'calls' edge TO func_key."""
        return [
            src
            for src, _, d in self.graph.in_edges(func_key, data=True)
            if d.get("kind") == "calls"
        ]

    def callees_of(self, func_key: str) -> list[str]:
        """Return all function nodes that func_key calls."""
        return [
            dst
            for _, dst, d in self.graph.out_edges(func_key, data=True)
            if d.get("kind") == "calls"
        ]

    def modules_importing(self, module_name: str) -> list[str]:
        """Return all module node keys that import the given module."""
        target_key = module_key(module_name)
        return [
            src
            for src, _, d in self.graph.in_edges(target_key, data=True)
            if d.get("kind") == "imports"
        ]

    def summary(self) -> dict:
        """Return basic graph statistics."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "modules": len(self._module_index),
            "functions": len(self._func_name_index),
        }


def build_graph(modules: list[ParsedModule]) -> DependencyGraph:
    """Convenience: create and populate a DependencyGraph from parsed modules."""
    g = DependencyGraph()
    g.build(modules)
    return g
