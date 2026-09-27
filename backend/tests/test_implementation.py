"""
tests/test_implementation.py — Tests for Phase 6 Bob-Assisted Implementation.
"""
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.implementation.service import ImplementationService
from backend.app.implementation.models import (
    ImplementationPlan,
    ImplementationPlanRequest,
    ProposeRequest,
    FileChange,
    ApplyRequest,
)

client = TestClient(app)

REPO = "./sample_repos/test_shop"
TARGET_FILE = os.path.abspath("sample_repos/test_shop/checkout.py")


def test_create_plan_valid():
    response = client.post("/api/implementation/plan", json={
        "repository": REPO,
        "change_request": "Add discount_percent parameter to calculate_total",
    })
    assert response.status_code == 200
    data = response.json()
    assert "target_file" in data
    assert "implementation_steps" in data
    assert len(data["implementation_steps"]) > 0


def test_create_plan_invalid_repo():
    response = client.post("/api/implementation/plan", json={
        "repository": "./nonexistent",
        "change_request": "anything",
    })
    assert response.status_code == 400


def test_create_plan_has_bob_assistance():
    response = client.post("/api/implementation/plan", json={
        "repository": REPO,
        "change_request": "Change calculate_total",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["bob_assistance"] != ""


def test_propose_generates_diff():
    plan = ImplementationService.create_plan(
        ImplementationPlanRequest(repository=REPO, change_request="Add discount support")
    )
    with open(TARGET_FILE, "r") as f:
        original_content = f.read()
    new_content = original_content + "\n# proposed change\n"
    proposal = ImplementationService.propose(ProposeRequest(
        plan=plan,
        changes=[FileChange(file_path=TARGET_FILE, content=new_content, rationale="test")]
    ))
    assert proposal.diff != ""
    assert "proposed change" in proposal.diff


def test_propose_returns_proposal_object():
    plan = ImplementationService.create_plan(
        ImplementationPlanRequest(repository=REPO, change_request="No change")
    )
    proposal = ImplementationService.propose(ProposeRequest(
        plan=plan,
        changes=[FileChange(file_path=TARGET_FILE, content="# minimal content", rationale="test")]
    ))
    assert hasattr(proposal, "diff")
    assert isinstance(proposal.warnings, list)


def test_apply_requires_approval():
    plan = ImplementationService.create_plan(
        ImplementationPlanRequest(repository=REPO, change_request="test")
    )
    from backend.app.implementation.models import ProposedChangeResponse
    proposal = ProposedChangeResponse(plan=plan, changes=[], diff="")
    with pytest.raises(ValueError, match="approved"):
        ImplementationService.apply(ApplyRequest(proposal=proposal, approved=False))


def test_apply_creates_workspace():
    plan = ImplementationService.create_plan(
        ImplementationPlanRequest(repository=REPO, change_request="Add discount support")
    )
    with open(TARGET_FILE, "r") as f:
        content = f.read()
    from backend.app.implementation.models import ProposedChangeResponse
    proposal = ProposedChangeResponse(
        plan=plan,
        changes=[FileChange(file_path=TARGET_FILE, content=content, rationale="test")],
        diff="",
    )
    result = ImplementationService.apply(ApplyRequest(proposal=proposal, approved=True))
    assert "workspace_id" in result
    assert os.path.isdir(result["workspace_path"])
    # Cleanup
    import shutil
    shutil.rmtree(result["workspace_path"], ignore_errors=True)


def test_verify_invalid_workspace():
    from backend.app.implementation.models import VerificationRequest
    with pytest.raises(ValueError, match="not found"):
        ImplementationService.verify(VerificationRequest(workspace_id="nonexistent-id"))
