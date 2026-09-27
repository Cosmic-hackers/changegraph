#!/usr/bin/env python3
"""
analyze.py — ChangeGraph Phase 1 CLI

Usage:
    python analyze.py <repository_path> "<change_request>"

Example:
    python analyze.py ./sample_repos/test_shop "Change calculate_total to support discounts"

Prints a structured change impact report to stdout.
"""

import sys
import os
import textwrap

# ── Make backend importable when running from repo root ──────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.analyzers.repository import RepositoryAnalyzer, AnalysisResult
from app.analyzers.impact import ImpactedNode

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    _RICH = True
    console = None  # initialized below after stdout wrapper
except ImportError:
    _RICH = False
    console = None


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

import io
RISK_COLORS = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green", "UNKNOWN": "white"}

if _RICH:
    # Force UTF-8 on Windows to avoid cp1252 encoding errors in the terminal
    import sys as _sys
    if hasattr(_sys.stdout, "buffer"):
        console = Console(file=io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8"))
    else:
        console = Console()

def _risk_badge(level: str) -> str:
    return f"[bold {RISK_COLORS.get(level, 'white')}]{level}[/]" if _RICH else level


_SEP = "-" * 56

def _section(title: str) -> None:
    if _RICH:
        console.print(f"\n[bold cyan]{_SEP}[/]")
        console.print(f"[bold white] {title}[/]")
        console.print(f"[bold cyan]{_SEP}[/]")
    else:
        print(f"\n{_SEP}")
        print(f" {title}")
        print(_SEP)


def _print(msg: str) -> None:
    if _RICH:
        console.print(msg)
    else:
        # Strip rich markup for plain output
        import re
        plain = re.sub(r"\[/?[^\]]*\]", "", msg)
        print(plain)


def _wrap(text: str, indent: int = 4) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=72, initial_indent=prefix, subsequent_indent=prefix)


# ─────────────────────────────────────────────────────────────────────────────
# Report renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_report(result: AnalysisResult) -> None:
    # ── Header ──────────────────────────────────────────────────────────────
    if _RICH:
        console.print(Panel(
            "[bold white]ChangeGraph — Change Impact Analysis[/]",
            style="bold blue",
            padding=(0, 4),
        ))
    else:
        print("╔══════════════════════════════════════════════════════╗")
        print("║           ChangeGraph — Impact Analysis              ║")
        print("╚══════════════════════════════════════════════════════╝")

    _print(f"\n[bold]Repository:[/]  {result.repository_path}")
    _print(f"[bold]Change Request:[/] {result.change_request}")
    _print(f"\n[bold]Graph:[/] {result.graph_summary.get('nodes', 0)} nodes, "
           f"{result.graph_summary.get('edges', 0)} edges, "
           f"{result.graph_summary.get('modules', 0)} modules")

    # ── Warnings ────────────────────────────────────────────────────────────
    if result.warnings:
        _section("⚠ Warnings")
        for w in result.warnings:
            _print(f"  [yellow]{w}[/]")

    # ── Changed components ──────────────────────────────────────────────────
    _section("Changed / Target Component(s)")
    if not result.changed_components:
        _print("  [yellow]None identified.[/]")
    for c in result.changed_components:
        _print(f"  [bold green]{c.symbol}[/]")
        _print(f"  [dim]{c.file_path}[/]")
        _print(f"  ↳ {c.reason}")

    # ── Direct impact ────────────────────────────────────────────────────────
    _section(f"Direct Impact  ({len(result.direct_impact)} component(s))")
    if not result.direct_impact:
        _print("  [dim]None identified.[/]")
    for node in result.direct_impact:
        _print(f"  • [bold]{node.module}.{node.name}[/]  [dim]({node.node_type})[/]")
        _print(f"    [dim]{node.file_path}[/]")
        if node.explanation:
            _print(f"    [italic]{node.explanation}[/]")

    # ── Indirect impact ──────────────────────────────────────────────────────
    _section(f"Indirect Impact  ({len(result.indirect_impact)} component(s))")
    if not result.indirect_impact:
        _print("  [dim]None identified.[/]")
    for node in result.indirect_impact:
        _print(f"  • [bold]{node.module}.{node.name}[/]  [dim](depth {node.depth}, {node.node_type})[/]")
        _print(f"    [dim]{node.file_path}[/]")
        if node.explanation:
            _print(f"    [italic]{node.explanation}[/]")

    # ── Affected files ───────────────────────────────────────────────────────
    _section(f"Affected Files  ({len(result.affected_files)})")
    if not result.affected_files:
        _print("  [dim]None identified.[/]")
    for fp in result.affected_files:
        _print(f"  • {fp}")

    # ── Recommended tests ────────────────────────────────────────────────────
    _section(f"Recommended Tests  ({len(result.recommended_tests)})")
    if not result.recommended_tests:
        _print("  [dim]No test files identified.[/]")
    for t in result.recommended_tests:
        _print(f"  • [bold]{t.module_name}[/]  [dim]{t.file_path}[/]")
        for reason in t.match_reasons[:2]:
            _print(f"    ↳ {reason}")

    # ── Risk ─────────────────────────────────────────────────────────────────
    _section("Risk Assessment")
    _print(f"  Level: {_risk_badge(result.risk_level)}")
    _print("")
    for reason in result.risk_reasons:
        _print(f"  • {reason}")

    # ── Git context ──────────────────────────────────────────────────────────
    if result.git_context and result.git_context.git_available:
        _section("Git History Context")
        for fp, fh in result.git_context.file_histories.items():
            if fh.commits:
                _print(f"\n  [bold]{fh.relative_path}[/]  (churn: {fh.churn_score} commits)")
                _print(f"  Authors: {', '.join(fh.authors)}")
                for commit in fh.commits[:3]:
                    _print(f"    [{commit.sha}] {commit.date.strftime('%Y-%m-%d')} — {commit.message}")
    elif result.git_context and not result.git_context.git_available:
        _section("Git History Context")
        _print("  [dim]Git history not available (no .git directory or GitPython error).[/]")

    # ── Footer ───────────────────────────────────────────────────────────────
    if _RICH:
        console.print("\n")
        console.print(Panel(
            "[dim]ChangeGraph · IBM Bob 2.0 · Phase 1 Analysis Complete[/]",
            style="dim",
            padding=(0, 2),
        ))
    else:
        print("\n─" * 30)
        print(" ChangeGraph · Phase 1 Analysis Complete")
        print("─" * 30)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze.py <repository_path> \"<change_request>\"")
        print()
        print("Examples:")
        print('  python analyze.py ./sample_repos/test_shop "Change calculate_total to support discounts"')
        print('  python analyze.py ./sample_repos/test_shop "Modify payment processing"')
        print('  python analyze.py ./sample_repos/test_shop "Update authenticate_user in users.py"')
        sys.exit(1)

    repo_path = sys.argv[1]
    change_request = sys.argv[2]

    if not os.path.isdir(repo_path):
        print(f"Error: '{repo_path}' is not a directory.")
        sys.exit(1)

    analyzer = RepositoryAnalyzer(repo_path)
    result = analyzer.analyze(change_request)
    render_report(result)


if __name__ == "__main__":
    main()
