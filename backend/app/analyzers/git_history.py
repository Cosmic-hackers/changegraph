"""
git_history.py — Git history context analyzer for ChangeGraph.

Queries the Git log for context about recently changed files and functions.
Provides:
  - Recent commit history for a file
  - Authors who have modified a file
  - Frequency of change (churn)
  - Co-change analysis (files that are often modified together)

Uses GitPython. Gracefully degrades if the repo has no Git history
or GitPython is not installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

try:
    import git
    _GIT_AVAILABLE = True
except ImportError:
    _GIT_AVAILABLE = False


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: datetime
    files_changed: list[str] = field(default_factory=list)


@dataclass
class FileHistory:
    file_path: str
    relative_path: str
    commits: list[CommitInfo] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    churn_score: int = 0  # number of commits touching this file

    @property
    def is_frequently_changed(self) -> bool:
        return self.churn_score >= 5


@dataclass
class GitContext:
    """Aggregated git history context for a set of files."""
    repo_root: str
    file_histories: dict[str, FileHistory] = field(default_factory=dict)
    co_changed_pairs: list[tuple[str, str, int]] = field(default_factory=list)
    git_available: bool = True
    error: Optional[str] = None


class GitHistoryAnalyzer:
    """
    Analyzes the Git history of a repository.

    Parameters:
        repo_path: path to the repository root (must contain .git/)
        max_commits: maximum number of commits to scan (default 200)
    """

    def __init__(self, repo_path: str, max_commits: int = 200):
        self.repo_path = repo_path
        self.max_commits = max_commits
        self._repo: Optional["git.Repo"] = None
        self._available = _GIT_AVAILABLE

    def _open_repo(self) -> bool:
        """Attempt to open the git repository. Returns True on success."""
        if not self._available:
            return False
        if self._repo is not None:
            return True
        try:
            self._repo = git.Repo(self.repo_path, search_parent_directories=True)
            return True
        except Exception:
            self._available = False
            return False

    def get_file_history(self, file_path: str) -> FileHistory:
        """
        Return commit history for a single file.

        file_path may be absolute or relative to repo root.
        Returns a FileHistory with empty lists if git is unavailable.
        """
        rel_path = self._to_relative(file_path)
        history = FileHistory(file_path=file_path, relative_path=rel_path)

        if not self._open_repo() or self._repo is None:
            return history

        try:
            commits_iter = self._repo.iter_commits(
                paths=rel_path,
                max_count=self.max_commits,
            )
            authors_seen: set[str] = set()
            for commit in commits_iter:
                author = str(commit.author)
                authors_seen.add(author)
                ci = CommitInfo(
                    sha=commit.hexsha[:8],
                    message=commit.message.strip().splitlines()[0],
                    author=author,
                    date=datetime.fromtimestamp(commit.committed_date),
                )
                history.commits.append(ci)

            history.authors = sorted(authors_seen)
            history.churn_score = len(history.commits)
        except Exception as exc:
            # Non-fatal: return what we have
            history.commits = []

        return history

    def get_context_for_files(self, file_paths: list[str]) -> GitContext:
        """
        Return git history context for a list of files.

        Also computes co-change analysis (pairs of files frequently
        committed together) for the given set.
        """
        ctx = GitContext(
            repo_root=self.repo_path,
            git_available=self._available,
        )

        if not self._open_repo():
            ctx.git_available = False
            ctx.error = "Git repository not available or GitPython not installed."
            return ctx

        for fp in file_paths:
            ctx.file_histories[fp] = self.get_file_history(fp)

        ctx.co_changed_pairs = self._compute_co_changes(file_paths, ctx)
        return ctx

    def _compute_co_changes(
        self,
        file_paths: list[str],
        ctx: GitContext,
    ) -> list[tuple[str, str, int]]:
        """
        Find pairs of files in the given set that were committed together.

        Returns list of (file_a, file_b, count) sorted by count descending.
        """
        if not self._open_repo() or self._repo is None:
            return []

        # Build a map: commit_sha → set of rel_paths changed in that commit
        rel_paths = {self._to_relative(fp) for fp in file_paths}
        commit_files: dict[str, set[str]] = {}

        try:
            for commit in self._repo.iter_commits(max_count=self.max_commits):
                changed = {
                    item
                    for item in (commit.stats.files or {})
                    if item in rel_paths
                }
                if len(changed) >= 2:
                    commit_files[commit.hexsha] = changed
        except Exception:
            return []

        # Count co-occurrences
        pair_counts: dict[tuple[str, str], int] = {}
        for changed_set in commit_files.values():
            files = sorted(changed_set)
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    pair = (files[i], files[j])
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        return sorted(
            [(a, b, count) for (a, b), count in pair_counts.items()],
            key=lambda x: -x[2],
        )

    def _to_relative(self, file_path: str) -> str:
        """Convert an absolute path to a path relative to the repo root."""
        try:
            return os.path.relpath(file_path, self.repo_path).replace("\\", "/")
        except ValueError:
            return file_path
