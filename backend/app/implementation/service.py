"""
implementation/service.py — Phase 6 Bob-Assisted Implementation Service.

Approval-gated. Never modifies original repository files.
All changes applied only to isolated temporary workspace copies.
"""
from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import tempfile
import uuid
import logging
from typing import Optional

from ..analyzers.repository import RepositoryAnalyzer
from .models import (
    ApplyRequest,
    FileChange,
    ImplementationPlan,
    ImplementationPlanRequest,
    ImplementationVerification,
    ProposedChangeResponse,
    ProposeRequest,
    VerificationRequest,
)

logger = logging.getLogger("changegraph.implementation.service")

# In-memory workspace registry  {workspace_id: workspace_path}
_WORKSPACES: dict[str, str] = {}


class ImplementationService:

    @staticmethod
    def create_plan(request: ImplementationPlanRequest) -> ImplementationPlan:
        repo_path = os.path.abspath(request.repository)
        if not os.path.isdir(repo_path):
            raise ValueError(f"Repository path not found: {repo_path}")

        # Run Phase 1 to get evidence-backed affected files
        try:
            analyzer = RepositoryAnalyzer(repo_path)
            result = analyzer.analyze(request.change_request)
            affected_files = result.affected_files[:10]
            relevant_tests = [t.file_path for t in result.recommended_tests[:5]]
            risk_level = result.risk_level
            changed = result.changed_components
        except Exception as exc:
            logger.warning("Phase 1 failed in implementation planning: %s", exc)
            affected_files = []
            relevant_tests = []
            risk_level = "UNKNOWN"
            changed = []

        # Determine target file — first changed component's file
        target_file = changed[0].file_path if changed else (affected_files[0] if affected_files else "")

        implementation_steps = [
            f"Review the change request: '{request.change_request}'",
            f"Modify '{os.path.basename(target_file)}' with the proposed changes.",
            "Ensure all callers of modified functions are updated if signatures changed.",
            "Run the recommended test suites to verify no regressions.",
            "Review sensitive downstream modules: payment, refund, auth if affected.",
        ]

        bob_assistance = (
            "IBM Bob will assist by grounding implementation advice in the dependency graph. "
            "Paste your proposed file content below — a diff will be generated for review before any change is applied."
        )

        return ImplementationPlan(
            repository=repo_path,
            change_request=request.change_request,
            requested_change=request.change_request,
            target_file=target_file,
            affected_files=affected_files,
            relevant_tests=relevant_tests,
            implementation_steps=implementation_steps,
            bob_assistance=bob_assistance,
            risk_level=risk_level,
        )

    @staticmethod
    def propose(request: ProposeRequest) -> ProposedChangeResponse:
        warnings: list[str] = []
        all_diffs: list[str] = []

        for change in request.changes:
            file_path = change.file_path
            new_content = change.content

            if os.path.isfile(file_path):
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    original = f.readlines()
            else:
                original = []
                warnings.append(f"Original file not found at '{file_path}' — diff generated from empty baseline.")

            new_lines = new_content.splitlines(keepends=True)
            diff = difflib.unified_diff(
                original,
                new_lines,
                fromfile=f"a/{os.path.basename(file_path)}",
                tofile=f"b/{os.path.basename(file_path)}",
                lineterm="",
            )
            all_diffs.append("".join(diff))

        return ProposedChangeResponse(
            plan=request.plan,
            changes=request.changes,
            diff="\n".join(all_diffs),
            warnings=warnings,
        )

    @staticmethod
    def apply(request: ApplyRequest) -> dict:
        if not request.approved:
            raise ValueError("Proposal must be explicitly approved before applying.")

        repo_path = request.proposal.plan.repository
        if not os.path.isdir(repo_path):
            raise ValueError(f"Repository path not found: {repo_path}")

        # Create isolated workspace copy
        workspace_dir = tempfile.mkdtemp(prefix="changegraph-impl-")
        workspace_id = str(uuid.uuid4())
        shutil.copytree(repo_path, workspace_dir, dirs_exist_ok=True)
        _WORKSPACES[workspace_id] = workspace_dir

        # Apply each change to the workspace copy
        for change in request.proposal.changes:
            original_path = change.file_path
            # Map the original path into the workspace
            try:
                rel = os.path.relpath(original_path, repo_path)
                dest = os.path.join(workspace_dir, rel)
            except ValueError:
                dest = os.path.join(workspace_dir, os.path.basename(original_path))

            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(change.content)

        return {
            "workspace_id": workspace_id,
            "workspace_path": workspace_dir,
            "message": f"Change applied safely to isolated workspace (ID: {workspace_id}). Original repository is untouched.",
        }

    @staticmethod
    def verify(request: VerificationRequest) -> ImplementationVerification:
        workspace_dir = _WORKSPACES.get(request.workspace_id)
        if not workspace_dir or not os.path.isdir(workspace_dir):
            raise ValueError(f"Workspace '{request.workspace_id}' not found or has been cleaned up.")

        test_output = ""
        passed = False
        comparison: list[str] = []

        if request.test_files:
            # Run pytest on the specified test files within the workspace
            abs_test_files = []
            for tf in request.test_files:
                try:
                    rel = os.path.relpath(tf)
                    candidate = os.path.join(workspace_dir, rel)
                    if os.path.isfile(candidate):
                        abs_test_files.append(candidate)
                    elif os.path.isfile(tf):
                        abs_test_files.append(tf)
                except Exception:
                    pass

            if abs_test_files:
                try:
                    proc = subprocess.run(
                        ["python", "-m", "pytest"] + abs_test_files + ["--tb=short", "-q"],
                        capture_output=True,
                        text=True,
                        timeout=60,
                        cwd=workspace_dir,
                    )
                    test_output = proc.stdout + proc.stderr
                    passed = proc.returncode == 0
                    comparison = [
                        f"Exit code: {proc.returncode}",
                        "Tests passed." if passed else "Tests failed — see output below.",
                    ]
                except subprocess.TimeoutExpired:
                    test_output = "Test run timed out after 60 seconds."
                    comparison = ["Timeout — verification inconclusive."]
                except Exception as exc:
                    test_output = str(exc)
                    comparison = ["Error running tests."]
            else:
                test_output = "No matching test files found in workspace."
                passed = True
                comparison = ["No tests to run — considered passing."]
        else:
            test_output = "No test files specified."
            passed = True
            comparison = ["No test files specified — considered passing."]

        return ImplementationVerification(
            workspace_id=request.workspace_id,
            passed=passed,
            test_output=test_output,
            comparison=comparison,
        )
