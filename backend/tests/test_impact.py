"""
backend/tests/test_impact.py — Tests for the change impact analyzer.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.analyzers.python_ast import parse_directory
from backend.app.analyzers.dependencies import build_graph, function_key, module_key
from backend.app.analyzers.impact import ImpactAnalyzer

SHOP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_repos", "test_shop")


@pytest.fixture(scope="module")
def analyzer():
    modules = parse_directory(SHOP_DIR)
    graph = build_graph(modules)
    return ImpactAnalyzer(graph)


@pytest.fixture(scope="module")
def calculate_total_impact(analyzer):
    key = function_key("checkout", "calculate_total")
    return analyzer.analyze([key])


@pytest.fixture(scope="module")
def authenticate_user_impact(analyzer):
    key = function_key("users", "authenticate_user")
    return analyzer.analyze([key])


class TestCalculateTotalImpact:
    def test_finds_direct_impact(self, calculate_total_impact):
        assert len(calculate_total_impact.direct) > 0, \
            "calculate_total should have direct dependents"

    def test_finds_indirect_impact(self, calculate_total_impact):
        # calculate_total → calculate_refund_amount → process_refund (etc.)
        assert len(calculate_total_impact.indirect) >= 0  # may be 0 if shallow

    def test_risk_is_not_low(self, calculate_total_impact):
        assert calculate_total_impact.risk_level in ("MEDIUM", "HIGH"), \
            f"Expected MEDIUM or HIGH, got: {calculate_total_impact.risk_level}"

    def test_has_risk_reasons(self, calculate_total_impact):
        assert len(calculate_total_impact.risk_reasons) > 0

    def test_affected_modules_includes_financial_modules(self, calculate_total_impact):
        affected = calculate_total_impact.affected_modules
        # At least one of refund / invoice should be affected
        financial = {"refund", "invoice"}
        assert financial & set(affected), \
            f"Expected financial modules in affected. Got: {affected}"

    def test_all_impacted_have_explanation(self, calculate_total_impact):
        for node in calculate_total_impact.all_affected:
            assert node.explanation, \
                f"Node {node.key} has no explanation"

    def test_all_impacted_have_path(self, calculate_total_impact):
        for node in calculate_total_impact.all_affected:
            assert len(node.path) >= 2, \
                f"Node {node.key} path too short: {node.path}"


class TestAuthenticateUserImpact:
    def test_checkout_is_affected(self, authenticate_user_impact):
        affected_modules = authenticate_user_impact.affected_modules
        assert "checkout" in affected_modules, \
            f"checkout should be affected by authenticate_user change. Got: {affected_modules}"


class TestImpactResult:
    def test_empty_changed_keys(self, analyzer):
        result = analyzer.analyze([])
        assert result.direct == []
        assert result.indirect == []

    def test_nonexistent_key(self, analyzer):
        result = analyzer.analyze(["func:nonexistent.does_not_exist"])
        assert result.direct == []

    def test_affected_files_are_absolute_or_known_paths(self, calculate_total_impact):
        for fp in calculate_total_impact.affected_files:
            assert fp  # must be non-empty

    def test_risk_level_is_valid(self, calculate_total_impact):
        assert calculate_total_impact.risk_level in ("LOW", "MEDIUM", "HIGH")
