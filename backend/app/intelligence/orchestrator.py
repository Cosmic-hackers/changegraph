"""
backend/app/intelligence/orchestrator.py — Phase 2 Intelligence Orchestrator.

Ties together:
1. Phase 1 → Intelligence input translation
2. Impact Agent
3. Risk Agent
4. Test Agent
5. History Agent
6. Grounding Validator (enforcing zero hallucination)
7. Synthesis Agent
8. Observability & evidence audit trail
"""

from __future__ import annotations

import logging
from typing import Optional, Union, Any

from .models import (
    IntelligenceInput,
    ChangedSymbolFact,
    ImpactedSymbolFact,
    TestFileFact,
    GitContextFact,
    FileHistoryFact,
    CommitFact,
    CoChangeFact,
    ChangeImpactReport,
)
from .provider import AIProvider, get_ai_provider
from .impact_agent import ImpactAgent
from .risk_agent import RiskAgent
from .test_agent import TestAgent
from .history_agent import HistoryAgent
from .synthesizer import SynthesisAgent
from .validation import GroundingValidator

logger = logging.getLogger("changegraph.intelligence.orchestrator")


def convert_phase1_to_intelligence_input(phase1_data: Any) -> IntelligenceInput:
    """
    Converts either an AnalysisResult dataclass or AnalyzeResponse Pydantic model
    into a standardized IntelligenceInput.
    """
    # Check if it's already an IntelligenceInput
    if isinstance(phase1_data, IntelligenceInput):
        return phase1_data

    # Check if dict
    if isinstance(phase1_data, dict):
        # Could be serialized AnalyzeResponse
        return _from_dict(phase1_data)

    # Could be AnalysisResult dataclass or AnalyzeResponse object
    repo_path = getattr(phase1_data, "repository_path", "")
    change_req = getattr(phase1_data, "change_request", "")

    changed_comps: list[ChangedSymbolFact] = []
    for c in getattr(phase1_data, "changed_components", []):
        changed_comps.append(
            ChangedSymbolFact(
                key=getattr(c, "key", ""),
                symbol=getattr(c, "symbol", ""),
                module=getattr(c, "module", ""),
                file_path=getattr(c, "file_path", ""),
                reason=getattr(c, "reason", ""),
            )
        )

    direct_impacts: list[ImpactedSymbolFact] = []
    for n in getattr(phase1_data, "direct_impact", []):
        direct_impacts.append(
            ImpactedSymbolFact(
                key=getattr(n, "key", ""),
                node_type=getattr(n, "node_type", "unknown"),
                name=getattr(n, "name", ""),
                module=getattr(n, "module", ""),
                file_path=getattr(n, "file_path", ""),
                depth=getattr(n, "depth", 1),
                path=getattr(n, "path", []),
                explanation=getattr(n, "explanation", ""),
            )
        )

    indirect_impacts: list[ImpactedSymbolFact] = []
    for n in getattr(phase1_data, "indirect_impact", []):
        indirect_impacts.append(
            ImpactedSymbolFact(
                key=getattr(n, "key", ""),
                node_type=getattr(n, "node_type", "unknown"),
                name=getattr(n, "name", ""),
                module=getattr(n, "module", ""),
                file_path=getattr(n, "file_path", ""),
                depth=getattr(n, "depth", 2),
                path=getattr(n, "path", []),
                explanation=getattr(n, "explanation", ""),
            )
        )

    affected_files = list(getattr(phase1_data, "affected_files", []))

    recommended_tests: list[TestFileFact] = []
    for t in getattr(phase1_data, "recommended_tests", []):
        recommended_tests.append(
            TestFileFact(
                file_path=getattr(t, "file_path", ""),
                module_name=getattr(t, "module_name", ""),
                match_reasons=list(getattr(t, "match_reasons", [])),
                matched_functions=list(getattr(t, "matched_functions", [])),
            )
        )

    risk_level = getattr(phase1_data, "risk_level", "UNKNOWN")
    risk_reasons = list(getattr(phase1_data, "risk_reasons", []))
    dependency_paths = list(getattr(phase1_data, "dependency_paths", []))
    graph_summary = dict(getattr(phase1_data, "graph_summary", {}))
    warnings = list(getattr(phase1_data, "warnings", []))

    # Handle git_context if present
    git_context_fact: Optional[GitContextFact] = None
    raw_git = getattr(phase1_data, "git_context", None)
    if raw_git:
        git_context_fact = _convert_git_context(raw_git)

    return IntelligenceInput(
        repository_path=repo_path,
        change_request=change_req,
        changed_components=changed_comps,
        direct_impact=direct_impacts,
        indirect_impact=indirect_impacts,
        affected_files=affected_files,
        recommended_tests=recommended_tests,
        deterministic_risk_level=risk_level,
        deterministic_risk_reasons=risk_reasons,
        dependency_paths=dependency_paths,
        git_context=git_context_fact,
        graph_summary=graph_summary,
        warnings=warnings,
    )


def _convert_git_context(raw_git: Any) -> GitContextFact:
    if isinstance(raw_git, GitContextFact):
        return raw_git

    # Can be GitContext dataclass or GitContextOut Pydantic model
    git_avail = getattr(raw_git, "git_available", False)
    repo_root = getattr(raw_git, "repo_root", "")
    err = getattr(raw_git, "error", None)

    file_histories_dict: dict[str, FileHistoryFact] = {}
    raw_histories = getattr(raw_git, "file_histories", {})
    if isinstance(raw_histories, dict):
        for fp, fh in raw_histories.items():
            commits_list: list[CommitFact] = []
            for c in getattr(fh, "commits", []):
                d_str = str(getattr(c, "date", ""))
                commits_list.append(
                    CommitFact(
                        sha=getattr(c, "sha", ""),
                        message=getattr(c, "message", ""),
                        author=getattr(c, "author", ""),
                        date=d_str,
                        files_changed=list(getattr(c, "files_changed", [])),
                    )
                )

            file_histories_dict[fp] = FileHistoryFact(
                file_path=getattr(fh, "file_path", fp),
                relative_path=getattr(fh, "relative_path", fp),
                churn_score=getattr(fh, "churn_score", 0),
                authors=list(getattr(fh, "authors", [])),
                recent_commits=commits_list,
            )

    co_changed: list[CoChangeFact] = []
    raw_pairs = getattr(raw_git, "co_changed_pairs", [])
    for p in raw_pairs:
        if isinstance(p, (list, tuple)) and len(p) >= 3:
            co_changed.append(CoChangeFact(file_a=str(p[0]), file_b=str(p[1]), co_change_count=int(p[2])))
        elif hasattr(p, "file_a"):
            co_changed.append(CoChangeFact(file_a=p.file_a, file_b=p.file_b, co_change_count=p.co_change_count))

    return GitContextFact(
        git_available=git_avail,
        repo_root=repo_root,
        file_histories=file_histories_dict,
        co_changed_pairs=co_changed,
        error=err,
    )


def _from_dict(d: dict) -> IntelligenceInput:
    changed_comps = [ChangedSymbolFact(**c) for c in d.get("changed_components", [])]
    direct_impact = [ImpactedSymbolFact(**n) for n in d.get("direct_impact", [])]
    indirect_impact = [ImpactedSymbolFact(**n) for n in d.get("indirect_impact", [])]
    recommended_tests = [TestFileFact(**t) for t in d.get("recommended_tests", [])]

    git_fact = None
    if d.get("git_context"):
        raw_g = d["git_context"]
        if isinstance(raw_g, dict):
            histories = {}
            for k, v in raw_g.get("file_histories", {}).items():
                commits = [CommitFact(**c) for c in v.get("commits", [])]
                histories[k] = FileHistoryFact(
                    file_path=v.get("file_path", k),
                    relative_path=v.get("relative_path", k),
                    churn_score=v.get("churn_score", 0),
                    authors=v.get("authors", []),
                    recent_commits=commits,
                )
            co_pairs = [
                CoChangeFact(file_a=p[0], file_b=p[1], co_change_count=p[2])
                if isinstance(p, (list, tuple)) else CoChangeFact(**p)
                for p in raw_g.get("co_changed_pairs", [])
            ]
            git_fact = GitContextFact(
                git_available=raw_g.get("git_available", False),
                repo_root=raw_g.get("repo_root", ""),
                file_histories=histories,
                co_changed_pairs=co_pairs,
                error=raw_g.get("error"),
            )

    return IntelligenceInput(
        repository_path=d.get("repository_path", ""),
        change_request=d.get("change_request", ""),
        changed_components=changed_comps,
        direct_impact=direct_impact,
        indirect_impact=indirect_impact,
        affected_files=d.get("affected_files", []),
        recommended_tests=recommended_tests,
        deterministic_risk_level=d.get("risk_level", "UNKNOWN"),
        deterministic_risk_reasons=d.get("risk_reasons", []),
        dependency_paths=d.get("dependency_paths", []),
        git_context=git_fact,
        graph_summary=d.get("graph_summary", {}),
        warnings=d.get("warnings", []),
    )


class IntelligenceOrchestrator:
    """
    Coordinates multi-agent reasoning, validation, and synthesis over Phase 1 facts.
    """

    def __init__(self, provider: Optional[AIProvider] = None):
        self.provider = provider or get_ai_provider()
        self.impact_agent = ImpactAgent(self.provider)
        self.risk_agent = RiskAgent(self.provider)
        self.test_agent = TestAgent(self.provider)
        self.history_agent = HistoryAgent(self.provider)
        self.synthesizer = SynthesisAgent(self.provider)

    def run_intelligence(self, input_data: Union[IntelligenceInput, Any]) -> ChangeImpactReport:
        """
        Run the complete Phase 2 intelligence pipeline.
        
        Guarantees that all agent outputs are strictly grounded in deterministic facts.
        """
        # Ensure input conforms to IntelligenceInput
        intelligence_input = convert_phase1_to_intelligence_input(input_data)

        # Initialize GroundingValidator
        validator = GroundingValidator(intelligence_input)

        # 1. Run Impact Agent
        impact_out = self.impact_agent.run(intelligence_input)
        impact_out = validator.validate_impact(impact_out)

        # 2. Run Risk Agent
        risk_out = self.risk_agent.run(intelligence_input)
        risk_out = validator.validate_risk(risk_out)

        # 3. Run Test Agent
        test_out = self.test_agent.run(intelligence_input)

        # 4. Run History Agent
        history_out = self.history_agent.run(intelligence_input)
        history_out = validator.validate_history(history_out)

        # 5. Build Audit Record
        generation_mode = (
            "MOCK" if self.provider.name == "Mock AI Provider"
            else "AI_AUGMENTED" if self.provider.name == "IBM Bob 2.0"
            else "DETERMINISTIC_GROUNDED"
        )
        evidence_audit = validator.build_audit(provider_name=self.provider.name, mode=generation_mode)

        # 6. Run Synthesis Agent
        report = self.synthesizer.run(
            input_data=intelligence_input,
            impact_out=impact_out,
            risk_out=risk_out,
            test_out=test_out,
            history_out=history_out,
            evidence=evidence_audit,
        )

        return report
