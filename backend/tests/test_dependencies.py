"""
backend/tests/test_dependencies.py — Tests for the dependency graph builder.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.analyzers.python_ast import parse_directory
from backend.app.analyzers.dependencies import build_graph, module_key, function_key

SHOP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_repos", "test_shop")


@pytest.fixture(scope="module")
def graph():
    modules = parse_directory(SHOP_DIR)
    return build_graph(modules)


class TestGraphStructure:
    def test_graph_has_nodes(self, graph):
        assert graph.graph.number_of_nodes() > 0

    def test_graph_has_edges(self, graph):
        assert graph.graph.number_of_edges() > 0

    def test_checkout_module_node_exists(self, graph):
        key = module_key("checkout")
        assert graph.graph.has_node(key)

    def test_calculate_total_function_node_exists(self, graph):
        key = function_key("checkout", "calculate_total")
        assert graph.graph.has_node(key), f"Expected node {key} in graph"

    def test_checkout_module_imports_payment(self, graph):
        checkout_key = module_key("checkout")
        payment_key = module_key("payment")
        # There should be an imports edge checkout → payment
        edge = graph.graph.get_edge_data(checkout_key, payment_key)
        assert edge is not None, "checkout should import payment"
        assert edge.get("kind") == "imports"

    def test_checkout_module_imports_invoice(self, graph):
        checkout_key = module_key("checkout")
        invoice_key = module_key("invoice")
        edge = graph.graph.get_edge_data(checkout_key, invoice_key)
        assert edge is not None, "checkout should import invoice"

    def test_refund_imports_checkout(self, graph):
        refund_key = module_key("refund")
        checkout_key = module_key("checkout")
        edge = graph.graph.get_edge_data(refund_key, checkout_key)
        assert edge is not None, "refund should import checkout"


class TestCallEdges:
    def test_calculate_total_has_callers(self, graph):
        key = function_key("checkout", "calculate_total")
        callers = graph.callers_of(key)
        assert len(callers) > 0, "calculate_total should have callers"

    def test_process_refund_calls_calculate_refund_amount(self, graph):
        process_refund_key = function_key("refund", "process_refund")
        # process_refund calls calculate_refund_amount which calls calculate_total
        callees = graph.callees_of(process_refund_key)
        callee_names = [graph.get_node_data(k).get("name") for k in callees if graph.get_node_data(k)]
        assert any("calculate" in (n or "") for n in callee_names), \
            f"process_refund should call something with 'calculate' in the name. Callees: {callee_names}"


class TestResolveSymbol:
    def test_resolve_calculate_total_by_bare_name(self, graph):
        candidates = graph.resolve_symbol("calculate_total")
        assert len(candidates) > 0

    def test_resolve_checkout_calculate_total_qualified(self, graph):
        candidates = graph.resolve_symbol("checkout.calculate_total")
        assert any("calculate_total" in k for k in candidates)

    def test_resolve_nonexistent_returns_empty(self, graph):
        candidates = graph.resolve_symbol("nonexistent_function_xyz")
        assert candidates == []


class TestModulesImporting:
    def test_modules_importing_checkout(self, graph):
        importers = graph.modules_importing("checkout")
        importer_names = [graph.get_node_data(k).get("module") for k in importers if graph.get_node_data(k)]
        assert "refund" in importer_names, f"refund should import checkout. Got: {importer_names}"
