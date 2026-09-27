"""
backend/tests/test_intelligence.py — Comprehensive tests for Phase 2 IBM Bob Intelligence Layer.

Tests all 11 required scenarios:
1. Structured Phase 1 → AI input conversion
2. Impact Agent
3. Risk Agent
4. Test Agent
5. History Agent
6. Synthesis Agent
7. Full orchestration
8. FastAPI /api/analyze/intelligence endpoint
9. Invalid / missing input handling
10. AI provider failure resilience (fallback)
11. Hallucination / evidence validation
"""

import os
import sys
import json
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.main import app
from backend.app.analyzers.repository import RepositoryAnalyzer
from backend.app.intelligence.models import (
    IntelligenceInput,
    ChangedSymbolFact,
    ImpactedSymbolFact,
    TestFileFact,
    GitContextFact,
    FileHistoryFact,
    CommitFact,
    CoChangeFact,
    ImpactReasoningOutput,
    RiskReasoningOutput,
    TestRecommendationsOutput,
    HistoryContextOutput,
    ChangeImpactReport,
    WorkflowImpact,
    FailureScenario,
)
from backend.app.intelligence.provider import (
    AIProvider,
    DeterministicFallbackProvider,
    MockAIProvider,
    BobProvider,
    AIProviderError,
)
from backend.app.intelligence.validation import GroundingValidator
from backend.app.intelligence.impact_agent import ImpactAgent
from backend.app.intelligence.risk_agent import RiskAgent
from backend.app.intelligence.test_agent import TestAgent
from backend.app.intelligence.history_agent import HistoryAgent
from backend.app.intelligence.synthesizer import SynthesisAgent
from backend.app.intelligence.orchestrator import (
    IntelligenceOrchestrator,
    convert_phase1_to_intelligence_input,
)

SHOP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sample_repos", "test_shop")


@pytest.fixture(scope="module")
def phase1_discount():
    analyzer = RepositoryAnalyzer(SHOP_DIR)
    return analyzer.analyze("Change calculate_total to support discounts")


@pytest.fixture(scope="module")
def phase1_payment():
    analyzer = RepositoryAnalyzer(SHOP_DIR)
    return analyzer.analyze("Modify payment processing logic")


@pytest.fixture
def test_client():
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Structured Phase 1 → AI input conversion
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase1Conversion:
    def test_convert_analysis_result_dataclass(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        assert isinstance(intel_input, IntelligenceInput)
        assert len(intel_input.changed_components) > 0
        assert any("calculate_total" in c.symbol for c in intel_input.changed_components)
        assert len(intel_input.direct_impact) > 0
        assert intel_input.deterministic_risk_level in ("MEDIUM", "HIGH")
        assert len(intel_input.known_modules) > 0

    def test_convert_dict_payload(self, phase1_discount):
        payload = {
            "repository_path": phase1_discount.repository_path,
            "change_request": phase1_discount.change_request,
            "changed_components": [
                {
                    "key": c.key,
                    "symbol": c.symbol,
                    "module": c.module,
                    "file_path": c.file_path,
                    "reason": c.reason,
                }
                for c in phase1_discount.changed_components
            ],
            "direct_impact": [
                {
                    "key": n.key,
                    "node_type": n.node_type,
                    "name": n.name,
                    "module": n.module,
                    "file_path": n.file_path,
                    "depth": n.depth,
                    "path": n.path,
                    "explanation": n.explanation,
                }
                for n in phase1_discount.direct_impact
            ],
            "indirect_impact": [],
            "affected_files": phase1_discount.affected_files,
            "recommended_tests": [],
            "risk_level": "HIGH",
            "risk_reasons": ["Coupling"],
            "dependency_paths": [],
            "graph_summary": {"nodes": 10, "edges": 15},
            "warnings": [],
        }
        intel_input = convert_phase1_to_intelligence_input(payload)
        assert intel_input.deterministic_risk_level == "HIGH"
        assert len(intel_input.changed_components) == len(phase1_discount.changed_components)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Impact Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestImpactAgent:
    def test_impact_agent_reasoning(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        provider = DeterministicFallbackProvider()
        agent = ImpactAgent(provider)
        output = agent.run(intel_input)

        assert isinstance(output, ImpactReasoningOutput)
        assert len(output.summary) > 0
        assert len(output.affected_workflows) > 0
        assert len(output.propagation_breakdown) > 0
        # Verify symbols are grounded
        assert any("calculate_total" in s for s in output.grounded_symbols)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Risk Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskAgent:
    def test_risk_agent_grounded_reasons(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        provider = DeterministicFallbackProvider()
        agent = RiskAgent(provider)
        output = agent.run(intel_input)

        assert isinstance(output, RiskReasoningOutput)
        assert output.assessed_risk_level in ("LOW", "MEDIUM", "HIGH")
        assert len(output.risk_justification) > 0
        assert len(output.failure_scenarios) > 0
        # refund is a sensitive domain affected by calculate_total
        assert any("refund" in d for d in output.sensitive_domains_identified)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Test Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestTestAgent:
    def test_test_agent_recommendations_and_gaps(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        provider = DeterministicFallbackProvider()
        agent = TestAgent(provider)
        output = agent.run(intel_input)

        assert isinstance(output, TestRecommendationsOutput)
        assert len(output.recommended_suites) > 0
        # test_checkout should be recommended
        assert any("checkout" in s.test_module for s in output.recommended_suites)
        assert len(output.regression_scenarios) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. History Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestHistoryAgent:
    def test_history_agent_with_simulated_git(self):
        history_fact = FileHistoryFact(
            file_path="checkout.py",
            relative_path="checkout.py",
            churn_score=7,
            authors=["Alice", "Bob"],
            recent_commits=[
                CommitFact(
                    sha="abc1234",
                    message="Refactor checkout total",
                    author="Alice",
                    date="2026-01-01",
                )
            ],
        )
        git_fact = GitContextFact(
            git_available=True,
            repo_root="/repo",
            file_histories={"checkout.py": history_fact},
            co_changed_pairs=[
                CoChangeFact(file_a="checkout.py", file_b="payment.py", co_change_count=4)
            ],
        )
        intel_input = IntelligenceInput(
            repository_path="/repo",
            change_request="test",
            git_context=git_fact,
        )

        agent = HistoryAgent(DeterministicFallbackProvider())
        output = agent.run(intel_input)

        assert output.has_git_data is True
        assert len(output.high_churn_files) == 1
        assert output.high_churn_files[0].churn_score == 7
        assert len(output.co_change_patterns) == 1
        assert output.co_change_patterns[0].co_change_count == 4

    def test_history_agent_without_git(self):
        intel_input = IntelligenceInput(
            repository_path="/repo",
            change_request="test",
            git_context=None,
        )
        agent = HistoryAgent(DeterministicFallbackProvider())
        output = agent.run(intel_input)
        assert output.has_git_data is False


# ─────────────────────────────────────────────────────────────────────────────
# 6. Synthesis Agent
# ─────────────────────────────────────────────────────────────────────────────

class TestSynthesisAgent:
    def test_synthesis_creates_complete_report(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        provider = DeterministicFallbackProvider()
        validator = GroundingValidator(intel_input)

        impact_out = ImpactAgent(provider).run(intel_input)
        risk_out = RiskAgent(provider).run(intel_input)
        test_out = TestAgent(provider).run(intel_input)
        history_out = HistoryAgent(provider).run(intel_input)
        audit = validator.build_audit(provider.name, "DETERMINISTIC_GROUNDED")

        synthesizer = SynthesisAgent(provider)
        report = synthesizer.run(
            input_data=intel_input,
            impact_out=impact_out,
            risk_out=risk_out,
            test_out=test_out,
            history_out=history_out,
            evidence=audit,
        )

        assert isinstance(report, ChangeImpactReport)
        assert len(report.executive_summary) > 0
        assert len(report.suggested_developer_actions) > 0
        assert any(a.action_type == "MODIFY" for a in report.suggested_developer_actions)
        assert any(a.action_type == "TEST" for a in report.suggested_developer_actions)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Full Orchestration
# ─────────────────────────────────────────────────────────────────────────────

class TestFullOrchestration:
    def test_orchestrator_end_to_end(self, phase1_discount):
        orchestrator = IntelligenceOrchestrator()
        report = orchestrator.run_intelligence(phase1_discount)

        assert isinstance(report, ChangeImpactReport)
        assert report.risk_analysis.assessed_risk_level in ("MEDIUM", "HIGH")
        assert len(report.changed_components) > 0
        assert len(report.evidence.unverified_claims_filtered) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 8. API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestAPIEndpoint:
    def test_post_analyze_intelligence_with_repo_and_change(self, test_client):
        response = test_client.post(
            "/api/analyze/intelligence",
            json={
                "repository": SHOP_DIR,
                "change_request": "Change calculate_total to support discounts",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "executive_summary" in data
        assert "impact_reasoning" in data
        assert "risk_analysis" in data
        assert "test_strategy" in data
        assert "evidence" in data
        assert "suggested_developer_actions" in data

    def test_post_analyze_intelligence_with_precomputed_analysis(self, test_client):
        # Step 1: Run Phase 1 /api/analyze
        phase1_res = test_client.post(
            "/api/analyze",
            json={
                "repository": SHOP_DIR,
                "change_request": "Modify payment processing logic",
            },
        )
        assert phase1_res.status_code == 200
        phase1_data = phase1_res.json()

        # Step 2: Pass Phase 1 result to /api/analyze/intelligence
        intel_res = test_client.post(
            "/api/analyze/intelligence",
            json={"analysis": phase1_data},
        )
        assert intel_res.status_code == 200
        intel_data = intel_res.json()
        assert intel_data["risk_analysis"]["assessed_risk_level"] in ("MEDIUM", "HIGH")


# ─────────────────────────────────────────────────────────────────────────────
# 9. Invalid / Missing Input Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidInputHandling:
    def test_missing_body_fields(self, test_client):
        response = test_client.post("/api/analyze/intelligence", json={})
        assert response.status_code == 400
        assert "Must provide either" in response.json()["detail"]

    def test_invalid_repo_path(self, test_client):
        response = test_client.post(
            "/api/analyze/intelligence",
            json={
                "repository": "/invalid/nonexistent/directory/xyz123",
                "change_request": "anything",
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# 10. AI Provider Failure & Fallback Resilience
# ─────────────────────────────────────────────────────────────────────────────

class TestAIProviderFailureResilience:
    def test_provider_failure_gracefully_falls_back(self, phase1_discount):
        failing_provider = MockAIProvider(should_fail=True)
        orchestrator = IntelligenceOrchestrator(provider=failing_provider)

        # Must not raise AIProviderError; agents must catch and fall back
        report = orchestrator.run_intelligence(phase1_discount)
        assert isinstance(report, ChangeImpactReport)
        assert report.risk_analysis.assessed_risk_level in ("MEDIUM", "HIGH")
        assert len(report.impact_reasoning.affected_workflows) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 11. Hallucination / Evidence Validation
# ─────────────────────────────────────────────────────────────────────────────

class TestHallucinationValidation:
    def test_ungrounded_symbols_filtered(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        validator = GroundingValidator(intel_input)

        # Artificially create an output containing an ungrounded hallucinated symbol
        hallucinated_impact = ImpactReasoningOutput(
            summary="Test summary",
            affected_workflows=[
                WorkflowImpact(
                    workflow_name="Hallucinated Crypto Workflow",
                    affected_components=["crypto_wallet.transfer_funds", "checkout.calculate_total"],
                    propagation_chain="calculate_total → crypto_wallet",
                    impact_explanation="Fake explanation",
                ),
                WorkflowImpact(
                    workflow_name="Completely Fake Workflow",
                    affected_components=["nonexistent_module.fake_function"],
                    propagation_chain="fake → fake",
                    impact_explanation="Fake",
                ),
            ],
            grounded_symbols=["checkout.calculate_total", "hallucinated_token_xyz"],
        )

        sanitized = validator.validate_impact(hallucinated_impact)

        # "crypto_wallet.transfer_funds" must be removed
        valid_wf = sanitized.affected_workflows[0]
        assert "crypto_wallet.transfer_funds" not in valid_wf.affected_components
        assert "checkout.calculate_total" in valid_wf.affected_components

        # "Completely Fake Workflow" has no valid components left, so it must be pruned
        assert len(sanitized.affected_workflows) == 1

        # "hallucinated_token_xyz" must be pruned from grounded_symbols
        assert "hallucinated_token_xyz" not in sanitized.grounded_symbols

        # Validator must have recorded the filtered claims
        assert len(validator.filtered_claims) >= 2
        assert any("crypto_wallet" in claim for claim in validator.filtered_claims)
        assert any("hallucinated_token_xyz" in claim for claim in validator.filtered_claims)

    def test_ungrounded_failure_scenario_filtered(self, phase1_discount):
        intel_input = convert_phase1_to_intelligence_input(phase1_discount)
        validator = GroundingValidator(intel_input)

        risk_out = RiskReasoningOutput(
            assessed_risk_level="HIGH",
            risk_justification=["Real justification"],
            failure_scenarios=[
                FailureScenario(
                    component="fake_database_sharding",
                    scenario_description="Sharding error",
                    potential_consequence="Data loss",
                    mitigation_advice="None",
                )
            ],
            sensitive_domains_identified=["fake_crypto_domain"],
        )

        sanitized_risk = validator.validate_risk(risk_out)
        assert len(sanitized_risk.failure_scenarios) == 0
        assert "fake_crypto_domain" not in sanitized_risk.sensitive_domains_identified
        assert any("fake_database_sharding" in claim for claim in validator.filtered_claims)
