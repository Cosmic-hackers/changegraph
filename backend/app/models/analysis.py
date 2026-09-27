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
