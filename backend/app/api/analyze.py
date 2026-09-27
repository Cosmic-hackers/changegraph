"""
api/analyze.py — /api/analyze route for ChangeGraph.
"""

import os
from fastapi import APIRouter, HTTPException

from ..analyzers.repository import RepositoryAnalyzer
from ..models.analysis import AnalyzeRequest, AnalyzeResponse

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_repository(request: AnalyzeRequest):
    """
    Analyze a repository for the impact of a proposed change.

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

    # Map dataclass result to Pydantic response model
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
    )
