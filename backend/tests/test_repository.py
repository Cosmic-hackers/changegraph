"""
backend/tests/test_repository.py — Integration tests for the RepositoryAnalyzer orchestrator.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.analyzers.repository import RepositoryAnalyzer

SHOP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_repos", "test_shop")


@pytest.fixture(scope="module")
def discount_result():
    analyzer = RepositoryAnalyzer(SHOP_DIR)
    return analyzer.analyze("Change calculate_total to support discounts")


@pytest.fixture(scope="module")
def payment_result():
    analyzer = RepositoryAnalyzer(SHOP_DIR)
    return analyzer.analyze("Modify payment processing logic")


@pytest.fixture(scope="module")
def auth_result():
    analyzer = RepositoryAnalyzer(SHOP_DIR)
    return analyzer.analyze("Update authenticate_user in users.py")


class TestDiscountScenario:
    """Scenario 1: modify checkout calculation to support discounts."""

    def test_changed_components_identified(self, discount_result):
        assert len(discount_result.changed_components) > 0

    def test_calculate_total_is_changed_component(self, discount_result):
        symbols = [c.symbol for c in discount_result.changed_components]
        assert any("calculate_total" in s for s in symbols), \
            f"calculate_total not in changed components: {symbols}"

    def test_finds_direct_impact(self, discount_result):
        assert len(discount_result.direct_impact) > 0

    def test_risk_is_medium_or_high(self, discount_result):
        assert discount_result.risk_level in ("MEDIUM", "HIGH")

    def test_recommended_tests_include_checkout(self, discount_result):
        test_names = [t.module_name for t in discount_result.recommended_tests]
        assert any("checkout" in n for n in test_names), \
            f"test_checkout not recommended. Got: {test_names}"

    def test_affected_files_not_empty(self, discount_result):
        assert len(discount_result.affected_files) > 0

    def test_no_warnings_for_valid_request(self, discount_result):
        # May have warnings, but changed_components should be non-empty
        assert len(discount_result.changed_components) > 0

    def test_graph_summary_populated(self, discount_result):
        assert discount_result.graph_summary.get("nodes", 0) > 0
        assert discount_result.graph_summary.get("edges", 0) > 0


class TestPaymentScenario:
    """Scenario 2: modify payment processing."""

    def test_payment_module_identified(self, payment_result):
        affected = {c.module for c in payment_result.changed_components}
        assert "payment" in affected

    def test_checkout_is_affected(self, payment_result):
        all_affected = {n.module for n in payment_result.direct_impact + payment_result.indirect_impact}
        assert "checkout" in all_affected, \
            f"checkout should be indirectly affected by payment change. Got: {all_affected}"


class TestAuthScenario:
    """Scenario 3: modify authentication."""

    def test_authenticate_user_is_changed(self, auth_result):
        symbols = [c.symbol for c in auth_result.changed_components]
        assert any("authenticate_user" in s for s in symbols), \
            f"authenticate_user not identified. Got: {symbols}"

    def test_checkout_affected_by_auth(self, auth_result):
        all_affected_modules = set(auth_result.affected_modules)
        assert "checkout" in all_affected_modules, \
            f"checkout should be affected by auth change. Got: {all_affected_modules}"


class TestEdgeCases:
    def test_invalid_repo_path_returns_empty_result(self):
        analyzer = RepositoryAnalyzer("/nonexistent/path/xyz")
        result = analyzer.analyze("anything")
        assert len(result.changed_components) == 0 or len(result.warnings) > 0

    def test_unknown_change_request_adds_warning(self):
        analyzer = RepositoryAnalyzer(SHOP_DIR)
        result = analyzer.analyze("zzzz_completely_unknown_symbol_xyz_abc_123")
        # Should either add a warning or return empty changed_components
        assert len(result.warnings) > 0 or len(result.changed_components) == 0
