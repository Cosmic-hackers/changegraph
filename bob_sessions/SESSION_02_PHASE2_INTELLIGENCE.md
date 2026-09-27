# ChangeGraph — Bob Sessions

This directory documents IBM Bob 2.0 workflows and architectural sessions for ChangeGraph.

---

## Session 2 — Phase 2: IBM Bob Intelligence Layer

**Objective:**
Build the AI Intelligence Layer over Phase 1's deterministic AST analyzer without rewriting or replacing Phase 1.
Bob must NOT invent dependencies — reasoning occurs ONLY over facts supplied by the deterministic analyzer.

### Architecture Built:

```
                    Phase 1
            Deterministic Analyzer
                    │
                    ▼
             Structured Analysis (IntelligenceInput)
                    │
          ┌─────────┴─────────┐
          │         │         │
          ▼         ▼         ▼
       Impact      Risk      Test
       Agent       Agent     Agent
          │         │         │
          └─────────┬─────────┘
                    │
                    ▼
              History Agent
                    │
                    ▼
        Grounding & Hallucination Guard
          (Strict Fact Verification)
                    │
                    ▼
             Synthesis Agent
                    │
                    ▼
        Change Impact Report (Phase 2)
```

### Key Components Created:

1. **Structured Data Contracts (`backend/app/intelligence/models.py`)**:
   - `IntelligenceInput`: Ingests Phase 1 results (`AnalysisResult` or `AnalyzeResponse`).
   - `ImpactReasoningOutput`, `RiskReasoningOutput`, `TestRecommendationsOutput`, `HistoryContextOutput`.
   - `GroundingValidator` & `EvidenceAudit`: Guarantees auditability and records facts evaluated vs filtered claims.
   - `ChangeImpactReport`: Complete final report model.

2. **AI Provider Abstraction (`backend/app/intelligence/provider.py`)**:
   - `AIProvider`: Abstract base class.
   - `BobProvider`: IBM Bob runtime / API integration with environment configuration.
   - `DeterministicFallbackProvider`: 100% reliable, zero-hallucination grounded reasoner for offline/local execution.
   - `MockAIProvider`: Configurable provider for testing canned outputs and fault injection.

3. **Specialized Reasoning Agents**:
   - `ImpactAgent` (`backend/app/intelligence/impact_agent.py`): Reasons about propagation paths and business workflows.
   - `RiskAgent` (`backend/app/intelligence/risk_agent.py`): Evaluates concrete failure scenarios and sensitive domains.
   - `TestAgent` (`backend/app/intelligence/test_agent.py`): Detects coverage gaps and specifies regression tests.
   - `HistoryAgent` (`backend/app/intelligence/history_agent.py`): Analyzes churn and co-change coupling.
   - `SynthesisAgent` (`backend/app/intelligence/synthesizer.py`): Unifies agent outputs into executive summary & step-by-step developer actions.

4. **Hallucination Guard (`backend/app/intelligence/validation.py`)**:
   - Compares all entity claims against the AST-grounded symbol table.
   - Automatically prunes or filters ungrounded symbols and logs them in the evidence audit.

5. **Orchestrator (`backend/app/intelligence/orchestrator.py`)**:
   - End-to-end execution of the intelligence pipeline.

6. **FastAPI Route (`backend/app/api/analyze.py`)**:
   - `POST /api/analyze/intelligence`: Accepts either pre-computed `analysis` or `repository` + `change_request`.

7. **CLI Integration (`analyze.py`)**:
   - Added `--ai` / `--bob` CLI flag rendering the full synthesized Change Impact Report.

8. **Test Suite (`backend/tests/test_intelligence.py`)**:
   - 16 new tests covering conversion, each agent, full pipeline, API endpoint, edge cases, provider failure resilience, and hallucination rejection.

### Verification:
- Total tests: **68 passed in 2.74s** (52 Phase 1 tests + 16 Phase 2 tests).
- 0 failures, 0 regressions.
