# ChangeGraph — Bob Sessions

This directory documents how IBM Bob 2.0 was used during the development of ChangeGraph.

---

## Session 1 — Phase 1 Architecture & Build

**Task:** Build the Phase 1 deterministic Python AST analyzer from scratch.

**What Bob did:**

1. **Inspected the existing repository state** — found the partial skeleton (`users.py`, `products.py`) and the README.
2. **Created the full project structure** — `backend/app/{api,analyzers,models,services}`, `backend/tests/`, `bob_sessions/`, `docs/`, `frontend/`.
3. **Built the synthetic test repository** (`sample_repos/test_shop/`) with intentional dependency chains:
   - `checkout.py` ← central hub with `calculate_total()`
   - `refund.py` ← imports `checkout.calculate_total`
   - `payment.py` ← called by `checkout`, `refund`
   - `invoice.py` ← called by `checkout`
   - `cart.py`, `users.py`, `products.py`, `notifications.py`
   - `tests/test_checkout.py`, `tests/test_payment.py`, `tests/test_refund.py`

4. **Built the analyzer stack** (all in `backend/app/analyzers/`):

   | File | Responsibility |
   |------|---------------|
   | `python_ast.py` | Parse `.py` files using Python `ast` — extracts functions, classes, imports, call lists |
   | `dependencies.py` | Build a directed NetworkX graph — nodes are symbols, edges are `calls/imports/contains/inherits` |
   | `impact.py` | BFS traversal of reversed graph — find direct (depth=1) and indirect (depth=2+) dependents; classify risk |
   | `tests_mapper.py` | Map affected modules to test files via naming convention + import scanning + function name matching |
   | `git_history.py` | Query GitPython for file churn and co-change analysis |
   | `repository.py` | Orchestrator — ties all analyzers together; implements deterministic change request → symbol resolution |

5. **Built the CLI** (`analyze.py`) — Rich-powered terminal output with:
   - Changed/target components
   - Direct impact with dependency chain explanation
   - Indirect impact with depth and full path
   - Affected files
   - Recommended tests with match reasons
   - Risk assessment (LOW / MEDIUM / HIGH) with concrete reasons
   - Git history context

6. **Built the FastAPI API** (`backend/app/main.py`, `backend/app/api/analyze.py`) — `POST /api/analyze` endpoint.

7. **Wrote 52 tests** across 4 test files:
   - `test_python_ast.py` — parser correctness
   - `test_dependencies.py` — graph structure and edge types
   - `test_impact.py` — impact traversal, risk classification, explanation generation
   - `test_repository.py` — 5 end-to-end scenarios

8. **Fixed two bugs** discovered during the test run:
   - `NetworkX.in_degree()` returns a view when called without a node argument — added `has_node()` guard
   - `AnalysisResult` missing `affected_modules` property — added it

9. **Validated the CLI** against 3 scenarios:
   - "Change calculate_total to support discounts" → HIGH risk, 5 direct + 8 indirect
   - "Modify payment processing" → HIGH risk, 4 direct + 1 indirect
   - "Update authenticate_user in users.py" → MEDIUM risk

**Final test result:** 52/52 passed in 0.34s

---

## Key Design Decisions Made During This Session

### Deterministic over LLM

The dependency graph is 100% built from Python AST analysis. Bob does not invent or guess dependencies. Every edge in the graph traces back to a real `import` or function `call` in the source code.

### Explainability first

Every impacted node receives a full dependency chain explanation:
> `refund.process_refund() is potentially affected because: checkout.calculate_total() → refund.calculate_refund_amount() → refund.process_refund().`

### Risk without numbers

Risk is classified as LOW / MEDIUM / HIGH with a list of concrete reasons — never an opaque numeric score.

### BFS on reversed graph

Impact traversal reverses the dependency graph so edges point "upstream" (from dependents to dependencies). BFS from the changed symbol then naturally discovers all downstream dependents at each depth level.

### Test detection strategy

Test files are matched against affected modules using three independent signals:
1. **Naming convention** — `test_checkout.py` → `checkout`
2. **Import scanning** — any test file that imports an affected module
3. **Function name matching** — test functions that reference affected function names

---

## Phase 5 Plan — IBM Bob Reasoning Agents

When Phase 5 is built, Bob will operate as a set of specialized agents:

```
Deterministic Analyzer Results (Phase 1 output)
           ↓
  ┌─────────────────────────────────────────┐
  │  Impact Agent                           │
  │  Reason about which components matter   │
  │  most and why                           │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  Risk Agent                             │
  │  Evaluate the severity of the impact    │
  │  based on business context              │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  Test Agent                             │
  │  Identify gaps in test coverage and     │
  │  recommend additional tests to write    │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  History Agent                          │
  │  Analyze git churn, co-change patterns  │
  │  and recent author activity             │
  └──────────────┬──────────────────────────┘
                 │
  ┌──────────────▼──────────────────────────┐
  │  Synthesis                              │
  │  Produce final Change Impact Report     │
  └─────────────────────────────────────────┘
```

Bob's role is to **reason about the evidence** produced by the deterministic analyzer — not to replace it.

---

## Session Log

| Date | Phase | Action | Result |
|------|-------|--------|--------|
| Phase 1 build | 1 | Build all analyzers, CLI, tests | 52/52 tests pass |
| Phase 1 demo  | 1 | Run `analyze.py` on 3 scenarios | All produce correct HIGH/MEDIUM risk reports |
