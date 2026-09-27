"""
simulation/models.py — Pydantic models for Phase 5 What-If Simulation.
"""
from __future__ import annotations
from typing import Optional, Any
from pydantic import BaseModel


class SimulationRequest(BaseModel):
    repository: str
    scenario: str


class WhatIfReport(BaseModel):
    scenario: str
    simulation_type: str = "what_if"
    deterministic_evidence: dict[str, Any] = {}
    hypothetical_impact: list[str] = []
    developer_actions: list[str] = []
    uncertainty: list[str] = []
    intelligence: Optional[Any] = None
