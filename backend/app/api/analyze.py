"""
api/analyze.py — /api/analyze and /api/analyze/intelligence routes for ChangeGraph.
"""

import os
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..analyzers.repository import RepositoryAnalyzer, AnalysisResult
from ..models.analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    IntelligenceAnalyzeRequest,
    GitContextOut,
    FileHistoryOut,
    GitCommitOut,
)
from ..intelligence.orchestrator import IntelligenceOrchestrator
from ..intelligence.models import ChangeImpactReport

router = APIRouter()


def _format_analysis_response(result: AnalysisResult) -> AnalyzeResponse:
    """Helper to convert an AnalysisResult dataclass into AnalyzeResponse Pydantic model."""
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
    """
    Phase 1: Deterministic repository change impact analysis.

    POST /api/analyze
    Body: { "repository": "<path>", "change_request": "<description>" }
    """
    repo_path = os.path.abspath(request.repository)

    if not os.path.isdir(repo_path):
        raise HTTPException(
            status_code=400,
            detail=f"Repository path not found: {repo_path}",
        )

    analyzer = RepositoryAnalyzer(repo_path)
    result = analyzer.analyze(request.change_request)

    return _format_analysis_response(result)


@router.post("/analyze/intelligence", response_model=ChangeImpactReport)
async def analyze_intelligence(request: IntelligenceAnalyzeRequest):
    """
    Phase 2: AI-Powered Intelligence Reasoning Layer (IBM Bob).

    POST /api/analyze/intelligence
    Body:
      Option A: { "analysis": <Phase 1 AnalyzeResponse> }
      Option B: { "repository": "<path>", "change_request": "<description>" }
    """
    orchestrator = IntelligenceOrchestrator()

    if request.analysis is not None:
        return orchestrator.run_intelligence(request.analysis)

    if request.repository and request.change_request:
        repo_path = os.path.abspath(request.repository)
        if not os.path.isdir(repo_path):
            raise HTTPException(
                status_code=400,
                detail=f"Repository path not found: {repo_path}",
            )
        analyzer = RepositoryAnalyzer(repo_path)
        phase1_result = analyzer.analyze(request.change_request)
        return orchestrator.run_intelligence(phase1_result)

    raise HTTPException(
        status_code=400,
        detail="Must provide either pre-computed 'analysis' object or 'repository' + 'change_request'.",
    )
