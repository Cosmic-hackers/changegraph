# ChangeGraph

> **"Know what your code change will affect before you make it."**

**ChangeGraph** is an AI-powered GitHub Change Impact Analyzer. It builds a deterministic dependency graph of your Python repository, finds what a proposed change will affect, recommends relevant tests, explains why each component is impacted — and optionally uses IBM Bob to reason about and implement the change after developer approval.

---

## Problem

Developers make changes to existing code without knowing all the downstream files, functions, APIs, workflows, and tests that may be affected. They typically discover these dependencies manually through code search, Git history, and trial-and-error testing.

## Solution

ChangeGraph analyzes a proposed code change, builds a deterministic call/dependency graph, identifies affected components, maps relevant tests, and explains **why** each component is affected — grounded in actual repository evidence.

---

## Core Workflow

```
GitHub Repository
       ↓
 Pull Request / Change
       ↓
  Detect changed code
       ↓
  Parse repository (AST)
       ↓
  Build dependency graph (NetworkX)
       ↓
  Find direct & indirect impact
       ↓
  Map relevant tests
       ↓
  Analyze Git history
       ↓
  IBM Bob reasoning
       ↓
Impact + Risk + Test Report
       ↓
 Developer approval
       ↓
Optional Bob implementation
       ↓
    Run tests
       ↓
   Verification
```

---

## Project Structure

```
changegraph/
├── analyze.py                        # Phase 1 CLI entry point
├── pytest.ini
├── requirements.txt
│
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI application
│   │   ├── api/
│   │   │   └── analyze.py            # POST /api/analyze route
│   │   ├── analyzers/
│   │   │   ├── repository.py         # Orchestrator
│   │   │   ├── python_ast.py         # AST parser (deterministic)
│   │   │   ├── dependencies.py       # NetworkX graph builder
│   │   │   ├── impact.py             # Impact finder + risk classifier
│   │   │   ├── tests_mapper.py       # Test file identifier
│   │   │   └── git_history.py        # Git context analyzer
│   │   └── models/
│   │       └── analysis.py           # Pydantic API models
│   └── tests/
│       ├── test_python_ast.py
│       ├── test_dependencies.py
│       ├── test_impact.py
│       └── test_repository.py
│
├── frontend/                         # Phase 3 — React/Vite Change Impact Report UI
│
├── sample_repos/
│   └── test_shop/                    # Synthetic demo repository
│       ├── users.py
│       ├── products.py
│       ├── cart.py
│       ├── checkout.py               # Central hub — calculate_total
│       ├── payment.py
│       ├── invoice.py
│       ├── refund.py
│       ├── notifications.py
│       └── tests/
│           ├── test_checkout.py
│           ├── test_payment.py
│           └── test_refund.py
│
├── docs/
├── bob_sessions/                     # IBM Bob 2.0 workflow documentation
└── README.md
```

---

## Quickstart (Phase 1 — CLI)

### Prerequisites

- Python 3.12+
- Dependencies: `networkx`, `gitpython`, `rich`, `fastapi`, `uvicorn`, `pytest`

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the analyzer (Phase 1 CLI & Phase 2 Intelligence)

```bash
# Phase 1: Deterministic impact report
python analyze.py ./sample_repos/test_shop "Change calculate_total to support discounts"

# Phase 2: Add IBM Bob Intelligence reasoning layer
python analyze.py ./sample_repos/test_shop "Change calculate_total to support discounts" --ai
```

### More scenarios

```bash
# Scenario 2: Modify payment processing (with AI reasoning)
python analyze.py ./sample_repos/test_shop "Modify payment processing" --ai

# Scenario 3: Modify authentication
python analyze.py ./sample_repos/test_shop "Update authenticate_user in users.py" --ai

# Scenario 4: Modify a product model
python analyze.py ./sample_repos/test_shop "Change product price field"

# Scenario 5: Modify refund logic
python analyze.py ./sample_repos/test_shop "Update process_refund logic" --ai
```

### Run tests

```bash
pytest
```

Expected: **68 passed** (52 Phase 1 deterministic tests + 16 Phase 2 intelligence layer tests)

### Start the API server

```bash
uvicorn backend.app.main:app --reload
```

Then POST to `http://localhost:8000/api/analyze`:

```json
{
  "repository": "./sample_repos/test_shop",
  "change_request": "Add discount support to checkout"
}
```

### Run the Phase 3 report UI

```bash
cd frontend
npm install
npm run dev
```

The report UI runs at `http://localhost:5173` and expects the FastAPI server at `http://localhost:8000`. Set `VITE_API_URL` to use a different API origin.

---

## Example CLI Output

```
+----------------------------------------------------------------------+
|    ChangeGraph — Change Impact Analysis                              |
+----------------------------------------------------------------------+

Repository:  ./sample_repos/test_shop
Change Request: Change calculate_total to support discounts

Graph: 79 nodes, 161 edges, 11 modules

 Changed / Target Component(s)
  checkout.calculate_total
  ↳ Function name 'calculate_total' appears in the change request.

 Direct Impact  (5 component(s))
  • checkout.checkout
    ↳ checkout.checkout() is potentially affected because:
      checkout.calculate_total() → checkout.checkout()
  • refund.calculate_refund_amount
    ↳ refund.calculate_refund_amount() is potentially affected because:
      checkout.calculate_total() → refund.calculate_refund_amount()
  • [3 test functions in test_checkout.py]

 Indirect Impact  (8 component(s))
  • refund.process_refund  (depth 2)
  • test_refund.*  (depth 3)
  • [more...]

 Recommended Tests
  • test_checkout — naming convention + imports checkout
  • test_refund   — imports checkout (affected module)

 Risk Assessment
  Level: HIGH
  • Changed symbol has 5 direct dependents across multiple modules.
  • Change propagates transitively to 8 additional components.
  • Affected modules include sensitive business logic: refund.
  • 'calculate_total' is called from 6 locations — high coupling.
```

---

## How Impact Analysis Works

### 1. Deterministic AST Parsing

ChangeGraph uses Python's `ast` module to parse every `.py` file without executing it:

- **Functions** and their call lists
- **Classes** and their method lists
- **Imports** (both `import x` and `from x import y`)

### 2. NetworkX Dependency Graph

All symbols become nodes. Relationships become directed edges:

| Edge kind | Meaning |
|-----------|---------|
| `calls` | function A calls function B |
| `imports` | module A imports module B |
| `contains` | module/class A contains function B |
| `inherits` | class A inherits from class B |

### 3. Impact Traversal

The graph is reversed and BFS-traversed from the changed symbol:
- **Depth 1** = direct dependents
- **Depth 2+** = indirect/transitive dependents

### 4. Risk Classification

Risk is classified as **LOW / MEDIUM / HIGH** based on concrete evidence:
- Number of direct dependents
- Transitive spread
- Presence of sensitive modules (payment, refund, auth)
- Call-site coupling

No arbitrary numeric scores are generated.

### 5. Explainability

Every impacted node includes a dependency chain explanation:

> `refund.process_refund() is potentially affected because:`  
> `checkout.calculate_total() → refund.calculate_refund_amount() → refund.process_refund()`

---

## API Reference

### `POST /api/analyze`

**Request:**
```json
{
  "repository": "./sample_repos/test_shop",
  "change_request": "Add discount support to checkout"
}
```

**Response:**
```json
{
  "repository_path": "...",
  "change_request": "...",
  "changed_components": [...],
  "direct_impact": [...],
  "indirect_impact": [...],
  "affected_files": [...],
  "recommended_tests": [...],
  "risk_level": "HIGH",
  "risk_reasons": [...],
  "dependency_paths": [...],
  "graph_summary": { "nodes": 79, "edges": 161, "modules": 11 },
  "warnings": []
}
```

### `POST /api/analyze/intelligence`

Runs the IBM Bob Intelligence Layer over the repository or over a pre-computed Phase 1 analysis.

**Option A (End-to-End):**
```json
{
  "repository": "./sample_repos/test_shop",
  "change_request": "Change calculate_total to support discounts"
}
```

**Option B (From Phase 1 Analysis):**
```json
{
  "analysis": { ... }
}
```

**Response:**
Returns the unified `ChangeImpactReport` with:
- `executive_summary`
- `impact_reasoning` (affected workflows, propagation chains)
- `risk_analysis` (assessed risk level, failure scenarios, sensitive domains)
- `test_strategy` (recommended suites, coverage gaps, regression scenarios)
- `history_context` (high churn files, co-change patterns)
- `suggested_developer_actions` (ordered step-by-step checklist)
- `evidence` (facts evaluated, unverified claims filtered count, zero-hallucination verification)

### `GET /health`

Returns `{"status": "ok", "version": "0.2.0"}`

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ **Complete** | Deterministic Python AST repository analyzer + CLI |
| 2 | ✅ **Complete** | IBM Bob Intelligence Layer (Impact, Risk, Test, History & Synthesis agents) |
| 3 | 🔜 | GitHub PR support (URL + PR number) |
| 4 | 🔜 | Impact Report web UI (React + React Flow) |
| 5 | 🔜 | Optional Bob implementation after approval & automated change verification |

---

## Sample Repository Dependency Map

```
users.py
  ├── get_user()          ← called by checkout, payment, invoice, refund, notifications
  └── authenticate_user() ← called by checkout

products.py
  ├── get_product_price() ← called by checkout.calculate_total
  └── check_stock()       ← called by cart, checkout

cart.py
  └── get_cart()          ← called by checkout

checkout.py  ← CENTRAL HUB
  ├── calculate_total()   ← called by refund.calculate_refund_amount
  ├── apply_discount()
  ├── validate_cart()
  ├── create_order()
  └── checkout()          ← orchestrates payment + invoice + cart

payment.py
  ├── process_payment()   ← called by checkout
  └── refund_payment()    ← called by refund

invoice.py
  └── generate_invoice()  ← called by checkout

refund.py
  ├── calculate_refund_amount() ← calls checkout.calculate_total
  └── process_refund()    ← calls payment.refund_payment

notifications.py
  └── send_*()            ← called by checkout, refund
```

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI
- **Analysis**: Python `ast`, NetworkX, GitPython
- **Frontend**: React, Vite, Tailwind CSS, React Flow *(Phase 4)*
- **Database**: SQLite *(Phase 4)*
- **AI**: IBM Bob 2.0 *(Phase 5)*
- **CLI**: Rich

---

## Bob Sessions

See [`bob_sessions/`](./bob_sessions/) for documented IBM Bob 2.0 workflows used during development and analysis.

---

## License

MIT
