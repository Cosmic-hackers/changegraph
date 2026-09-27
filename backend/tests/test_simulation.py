"""
tests/test_simulation.py — Tests for Phase 5 What-If Change Simulation.
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.simulation.engine import SimulationEngine
from backend.app.simulation.models import SimulationRequest, WhatIfReport

client = TestClient(app)

REPO = "./sample_repos/test_shop"


def test_simulation_valid_scenario():
    response = client.post("/api/simulate", json={
        "repository": REPO,
        "scenario": "What happens if I remove checkout.calculate_total?",
    })
    assert response.status_code == 200
    data = response.json()
    assert "scenario" in data
    assert "deterministic_evidence" in data


def test_simulation_returns_whatif_report():
    response = client.post("/api/simulate", json={
        "repository": REPO,
        "scenario": "Change calculate_total to support discounts",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_type"] == "what_if"


def test_simulation_empty_scenario():
    response = client.post("/api/simulate", json={
        "repository": REPO,
        "scenario": "   ",
    })
    assert response.status_code == 422


def test_simulation_invalid_repo():
    response = client.post("/api/simulate", json={
        "repository": "./nonexistent_repo",
        "scenario": "Remove checkout",
    })
    assert response.status_code == 400


def test_simulation_has_deterministic_evidence():
    engine = SimulationEngine()
    req = SimulationRequest(repository=REPO, scenario="Change calculate_total to support discounts")
    result = engine.simulate(req)
    assert isinstance(result, WhatIfReport)
    assert result.deterministic_evidence is not None


def test_simulation_sufficient_evidence_for_known_target():
    engine = SimulationEngine()
    req = SimulationRequest(repository=REPO, scenario="Change calculate_total to support discounts")
    result = engine.simulate(req)
    assert result.deterministic_evidence.get("sufficient") is True


def test_simulation_insufficient_evidence_for_unknown_target():
    engine = SimulationEngine()
    req = SimulationRequest(repository=REPO, scenario="xyznonexistentfunctionabc")
    result = engine.simulate(req)
    assert result.deterministic_evidence.get("sufficient") is False


def test_simulation_has_developer_actions():
    engine = SimulationEngine()
    req = SimulationRequest(repository=REPO, scenario="Change calculate_total to support discounts")
    result = engine.simulate(req)
    assert isinstance(result.developer_actions, list)
