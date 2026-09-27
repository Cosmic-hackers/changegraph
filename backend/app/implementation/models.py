"""
implementation/models.py — Pydantic models for Phase 6 Bob-Assisted Implementation.
"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


class ImplementationPlanRequest(BaseModel):
    repository: str
    change_request: str
    analysis: Optional[Any] = None


class ImplementationPlan(BaseModel):
    repository: str
    change_request: str
    requested_change: str
    target_file: str
    affected_files: list[str] = []
    relevant_tests: list[str] = []
    implementation_steps: list[str] = []
    bob_assistance: str = ""
    risk_level: str = "UNKNOWN"


class FileChange(BaseModel):
    file_path: str
    content: str
    rationale: str = ""


class ProposeRequest(BaseModel):
    plan: ImplementationPlan
    changes: list[FileChange]


class ProposedChangeResponse(BaseModel):
    plan: ImplementationPlan
    changes: list[FileChange]
    diff: str = ""
    warnings: list[str] = []


class ApplyRequest(BaseModel):
    proposal: ProposedChangeResponse
    approved: bool = False


class VerificationRequest(BaseModel):
    workspace_id: str
    test_files: list[str] = []


class ImplementationVerification(BaseModel):
    workspace_id: str
    passed: bool
    test_output: str = ""
    comparison: list[str] = []
    warnings: list[str] = []
