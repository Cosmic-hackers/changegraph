"""
backend/app/intelligence/history_agent.py — Git History Context Agent for ChangeGraph.

Analyzes:
- Commit churn and stability of affected files
- Files frequently modified together (co-change patterns)
- Authors and recent modification patterns

Strict rule: Never claim a historical regression or change unless the provided Git data supports it.
"""

from __future__ import annotations

import json
import logging
from typing import Optional
from .models import (
    IntelligenceInput,
    HistoryContextOutput,
    HighChurnFileItem,
    CoChangePatternItem,
)
from .provider import AIProvider

logger = logging.getLogger("changegraph.intelligence.history_agent")


class HistoryAgent:
    """
    Interprets Git churn and co-change patterns discovered by Phase 1.
    """

    def __init__(self, provider: AIProvider):
        self.provider = provider

    def run(self, input_data: IntelligenceInput) -> HistoryContextOutput:
        # Check if git data is available
        if not input_data.git_context or not input_data.git_context.git_available:
            return HistoryContextOutput(
                historical_summary="Git history context is unavailable for this repository.",
                high_churn_files=[],
                co_change_patterns=[],
                historical_risk_notes=["No git repository found or git history analysis was skipped."],
                has_git_data=False,
            )

        if self.provider.is_available() and self.provider.name != "Deterministic Grounded Reasoner":
            try:
                ai_output = self._run_ai(input_data)
                if ai_output:
                    return ai_output
            except Exception as exc:
                logger.warning("AI provider failed in HistoryAgent, falling back to deterministic reasoning: %s", exc)

        return self._run_deterministic(input_data)

    def _run_ai(self, input_data: IntelligenceInput) -> Optional[HistoryContextOutput]:
        system_prompt = (
            "You are the ChangeGraph History Agent powered by IBM Bob. "
            "Analyze git history patterns strictly based on the provided churn scores, author lists, and co-change counts. "
            "CRITICAL: Do NOT invent past bugs, regressions, or author actions unless explicitly evidenced in the commits. "
            "Output your answer strictly in valid JSON matching the required schema."
        )

        git_ctx = input_data.git_context
        histories_summary = []
        if git_ctx:
            for fp, fh in list(git_ctx.file_histories.items())[:8]:
                histories_summary.append({
                    "file": fh.relative_path,
                    "churn_score": fh.churn_score,
                    "authors": fh.authors,
                    "recent_commit_messages": [c.message for c in fh.recent_commits[:3]],
                })

        prompt = (
            f"Git History Evidence:\n{json.dumps(histories_summary, indent=2)}\n\n"
            f"Produce a JSON response with:\n"
            f"- 'historical_summary': High-level summary of repository activity on affected files\n"
            f"- 'high_churn_files': list of objects with 'file_path', 'churn_score', 'authors', 'risk_implication'\n"
            f"- 'co_change_patterns': list of objects with 'file_a', 'file_b', 'co_change_count', 'implication'\n"
            f"- 'historical_risk_notes': list of concrete takeaways grounded in commit records\n"
            f"- 'has_git_data': true"
        )

        raw = self.provider.generate(prompt=prompt, system_prompt=system_prompt, json_schema=HistoryContextOutput)
        data = json.loads(raw)
        return HistoryContextOutput.model_validate(data)

    def _run_deterministic(self, input_data: IntelligenceInput) -> HistoryContextOutput:
        git_ctx = input_data.git_context
        if not git_ctx or not git_ctx.git_available:
            return HistoryContextOutput(
                historical_summary="Git history context unavailable.",
                high_churn_files=[],
                co_change_patterns=[],
                historical_risk_notes=["No git repository available."],
                has_git_data=False,
            )

        high_churn: list[HighChurnFileItem] = []
        risk_notes: list[str] = []

        for fp, fh in git_ctx.file_histories.items():
            if fh.churn_score >= 3:
                high_churn.append(
                    HighChurnFileItem(
                        file_path=fh.relative_path,
                        churn_score=fh.churn_score,
                        authors=fh.authors,
                        risk_implication=(
                            f"File '{fh.relative_path}' exhibits frequent modifications ({fh.churn_score} commits), "
                            "indicating an active area of change with higher risk of regression."
                        ),
                    )
                )

        # Process co-changed pairs
        co_changes: list[CoChangePatternItem] = []
        for pair in git_ctx.co_changed_pairs:
            co_changes.append(
                CoChangePatternItem(
                    file_a=pair.file_a,
                    file_b=pair.file_b,
                    co_change_count=pair.co_change_count,
                    implication=(
                        f"Files '{pair.file_a}' and '{pair.file_b}' were modified together in "
                        f"{pair.co_change_count} past commit(s), suggesting structural coupling."
                    ),
                )
            )

        # Risk notes strictly grounded in facts
        if high_churn:
            most_active = max(high_churn, key=lambda x: x.churn_score)
            risk_notes.append(
                f"Highest churn file: '{most_active.file_path}' ({most_active.churn_score} recorded commits)."
            )
        if co_changes:
            risk_notes.append(
                f"Identified {len(co_changes)} pair(s) of co-modified files. Consider reviewing both files together."
            )
        if not risk_notes:
            risk_notes.append("Files in this change set have modest historical commit activity.")

        summary = (
            f"Git analysis reviewed {len(git_ctx.file_histories)} affected file(s). "
            f"Found {len(high_churn)} high-churn file(s) and {len(co_changes)} co-change coupling pattern(s)."
        )

        return HistoryContextOutput(
            historical_summary=summary,
            high_churn_files=high_churn,
            co_change_patterns=co_changes,
            historical_risk_notes=risk_notes,
            has_git_data=True,
        )
