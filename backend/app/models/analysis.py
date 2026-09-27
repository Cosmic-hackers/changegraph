"""
models/analysis.py — Pydantic models for the ChangeGraph API.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    repository: str
    change_request: str


class ChangedComponentOut(BaseModel):
    key: str
    symbol: str
    module: str
    file_path: str
    reason: str


class ImpactedNodeOut(BaseModel):
    key: str
    node_type: str
    name: str
    module: str
    file_path: str
    depth: int
    path: list[str]
    explanation: str


class TestFileOut(BaseModel):
    file_path: str
    module_name: str
    match_reasons: list[str]
    matched_functions: list[str]


class GitCommitOut(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str] = []


class FileHistoryOut(BaseModel):
    file_path: str
    relative_path: str
    churn_score: int = 0
    authors: list[str] = []
    commits: list[GitCommitOut] = []


class GitContextOut(BaseModel):
    repo_root: str
    git_available: bool = True
    file_histories: dict[str, FileHistoryOut] = {}
    co_changed_pairs: list[list] = []
    error: Optional[str] = None


class AnalyzeResponse(BaseModel):
    repository_path: str
    change_request: str
    changed_components: list[ChangedComponentOut]
    direct_impact: list[ImpactedNodeOut]
    indirect_impact: list[ImpactedNodeOut]
    affected_files: list[str]
    recommended_tests: list[TestFileOut]
    risk_level: str
    risk_reasons: list[str]
    dependency_paths: list[list[str]]
    graph_summary: dict
    warnings: list[str]
    git_context: Optional[GitContextOut] = None


class IntelligenceAnalyzeRequest(BaseModel):
    """
    Request model for POST /api/analyze/intelligence.
    Supports either passing pre-computed Phase 1 'analysis',
    or providing 'repository' + 'change_request' to run Phase 1 + Phase 2 end-to-end.
    """
    analysis: Optional[AnalyzeResponse] = None
    repository: Optional[str] = None
    change_request: Optional[str] = None
