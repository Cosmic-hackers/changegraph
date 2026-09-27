"""
api/analyze.py — All API routes for ChangeGraph (Phases 1–6).
"""

import os

from fastapi import APIRouter, HTTPException

from ..analyzers.repository import AnalysisResult, RepositoryAnalyzer
from ..github.client import GitHubAPIError, GitHubNotFoundError, GitHubRateLimitError
from ..github.service import GitHubPRService
from ..implementation.models import (
    ApplyRequest,
    ImplementationPlan,
    ImplementationPlanRequest,
    ImplementationVerification,
    ProposedChangeResponse,
    ProposeRequest,
    VerificationRequest,
)
from ..implementation.service import ImplementationService
from ..intelligence.models import ChangeImpactReport
from ..intelligence.orchestrator import IntelligenceOrchestrator
from ..models.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    FileHistoryOut,
    GitCommitOut,
    GitContextOut,
    GitHubPRAnalyzeRequest,
    GitHubPRAnalyzeResponse,
    IntelligenceAnalyzeRequest,
)
from ..simulation.engine import SimulationEngine
from ..simulation.models import SimulationRequest, WhatIfReport

router = APIRouter()


@router.post("/implementation/plan", response_model=ImplementationPlan)
async def create_implementation_plan(request: ImplementationPlanRequest):
    """Phase 6: create an evidence-grounded, Bob-assisted implementation plan."""
    try:
        return ImplementationService.create_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/implementation/propose", response_model=ProposedChangeResponse)
async def propose_implementation_change(request: ProposeRequest):
    """Phase 6: validate and render developer-supplied proposed file changes."""
    try:
        return ImplementationService.propose(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/implementation/apply")
async def apply_implementation_change(request: ApplyRequest):
    """Phase 6: apply an explicitly approved proposal only to an isolated copy."""
    try:
        return ImplementationService.apply(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/implementation/verify", response_model=ImplementationVerification)
async def verify_implementation(request: VerificationRequest):
    """Phase 6: rerun deterministic analysis and selected tests in the isolated copy."""
    try:
        return ImplementationService.verify(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate", response_model=WhatIfReport)
async def simulate_change(request: SimulationRequest):
    """Phase 5: read-only what-if simulation over the current repository graph."""
    repo_path = os.path.abspath(request.repository)
    if not os.path.isdir(repo_path):
        raise HTTPException(
            status_code=400, detail=f"Repository path not found: {repo_path}"
        )
    if not request.scenario.strip():
        raise HTTPException(status_code=422, detail="scenario must not be empty")
    return SimulationEngine().simulate(request)


def _format_analysis_response(result: AnalysisResult) -> AnalyzeResponse:
    git_out = None
    if result.git_context:
        histories = {}
        for fp, fh in result.git_context.file_histories.items():
            commits = [
                GitCommitOut(
                    sha=c.sha,
                    message=c.message,
                    author=c.author,
                    date=str(c.date),
                    files_changed=c.files_changed,
                )
                for c in fh.commits
            ]
            histories[fp] = FileHistoryOut(
                file_path=fh.file_path,
                relative_path=fh.relative_path,
                churn_score=fh.churn_score,
                authors=fh.authors,
                commits=commits,
            )

        git_out = GitContextOut(
            repo_root=result.git_context.repo_root,
            git_available=result.git_context.git_available,
            file_histories=histories,
            co_changed_pairs=[list(p) for p in result.git_context.co_changed_pairs],
            error=result.git_context.error,
        )

    return AnalyzeResponse(
        repository_path=result.repository_path,
        change_request=result.change_request,
        changed_components=[
            {
                "key": c.key,
                "symbol": c.symbol,
                "module": c.module,
                "file_path": c.file_path,
                "reason": c.reason,
            }
            for c in result.changed_components
        ],
        direct_impact=[
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
            for n in result.direct_impact
        ],
        indirect_impact=[
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
            for n in result.indirect_impact
        ],
        affected_files=result.affected_files,
        recommended_tests=[
            {
                "file_path": t.file_path,
                "module_name": t.module_name,
                "match_reasons": t.match_reasons,
                "matched_functions": t.matched_functions,
            }
            for t in result.recommended_tests
        ],
        risk_level=result.risk_level,
        risk_reasons=result.risk_reasons,
        dependency_paths=result.dependency_paths,
        graph_summary=result.graph_summary,
        warnings=result.warnings,
        git_context=git_out,
    )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest):
    """Phase 1: Deterministic repository change impact analysis."""
    repo_path = os.path.abspath(request.repository)
    if not os.path.isdir(repo_path):
        raise HTTPException(status_code=400, detail=f"Repository path not found: {repo_path}")
    analyzer = RepositoryAnalyzer(repo_path)
    result = analyzer.analyze(request.change_request)
    return _format_analysis_response(result)


@router.post("/analyze/intelligence", response_model=ChangeImpactReport)
async def analyze_intelligence(request: IntelligenceAnalyzeRequest):
    """Phase 2: AI-Powered Intelligence Reasoning Layer (IBM Bob)."""
    orchestrator = IntelligenceOrchestrator()

    if request.analysis is not None:
        return orchestrator.run_intelligence(request.analysis)

    if request.repository and request.change_request:
        repo_path = os.path.abspath(request.repository)
        if not os.path.isdir(repo_path):
            raise HTTPException(status_code=400, detail=f"Repository path not found: {repo_path}")
        analyzer = RepositoryAnalyzer(repo_path)
        phase1_result = analyzer.analyze(request.change_request)
        return orchestrator.run_intelligence(phase1_result)

    raise HTTPException(
        status_code=400,
        detail="Must provide either pre-computed 'analysis' object or 'repository' + 'change_request'.",
    )


@router.post("/github/pr/analyze", response_model=GitHubPRAnalyzeResponse)
async def analyze_github_pull_request(request: GitHubPRAnalyzeRequest):
    """Phase 4: GitHub PR analysis via the existing deterministic + intelligence pipeline."""
    if request.pull_request <= 0:
        raise HTTPException(status_code=400, detail="pull_request must be a positive integer.")

    try:
        service = GitHubPRService()
        result = service.analyze_pull_request(request.repository, request.pull_request)
        return GitHubPRAnalyzeResponse(
            analysis=_format_analysis_response(result.analysis),
            intelligence=result.intelligence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GitHubRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GitHubAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
