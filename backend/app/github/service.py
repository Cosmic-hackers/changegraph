from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional

import git

from ..analyzers.repository import AnalysisResult, RepositoryAnalyzer
from ..intelligence.orchestrator import IntelligenceOrchestrator
from ..intelligence.models import ChangeImpactReport
from .client import GitHubAPIError, GitHubClient
from .models import GitHubPullRequestFile, GitHubPullRequestMetadata


class GitHubPRAnalysisResult:
    """Both pipeline stages needed by the existing Phase 3 report."""

    def __init__(self, analysis: AnalysisResult, intelligence: ChangeImpactReport):
        self.analysis = analysis
        self.intelligence = intelligence


class GitHubPRService:
    """Minimal adapter that turns a GitHub PR into the existing ChangeGraph analysis pipeline."""

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()

    def analyze_pull_request(self, repository_url: str, pull_request_number: int):
        owner, repo_name = GitHubClient.parse_repository_url(repository_url)
        pr_payload = self.client.fetch_pull_request(owner, repo_name, pull_request_number)
        files_payload = self.client.fetch_pull_request_files(owner, repo_name, pull_request_number)

        pr_meta = GitHubPullRequestMetadata(
            owner=owner,
            repo=repo_name,
            repository=f"{owner}/{repo_name}",
            number=int(pull_request_number),
            title=pr_payload.get("title", ""),
            body=pr_payload.get("body"),
            base_sha=pr_payload.get("base", {}).get("sha", ""),
            head_sha=pr_payload.get("head", {}).get("sha", ""),
            head_ref=pr_payload.get("head", {}).get("ref", ""),
            changed_files=[
                GitHubPullRequestFile(
                    filename=item.get("filename", ""),
                    status=item.get("status", ""),
                    additions=int(item.get("additions", 0) or 0),
                    deletions=int(item.get("deletions", 0) or 0),
                    patch=item.get("patch"),
                )
                for item in files_payload
            ],
        )

        repo_path = self._clone_pull_request_repository(repository_url, pr_meta)
        try:
            change_request = self._build_change_request(pr_meta)
            phase1_result = RepositoryAnalyzer(repo_path).analyze(change_request)
            intelligence_result = IntelligenceOrchestrator().run_intelligence(phase1_result)
            return GitHubPRAnalysisResult(phase1_result, intelligence_result)
        finally:
            self._cleanup_repo(repo_path)

    def _build_change_request(self, pr_meta: GitHubPullRequestMetadata) -> str:
        parts = [pr_meta.title or f"Pull request #{pr_meta.number}"]
        if pr_meta.changed_files:
            changed_files = [item.filename for item in pr_meta.changed_files[:8]]
            if changed_files:
                parts.append("Files changed: " + ", ".join(changed_files))
            diff_parts = [
                f"{item.filename}\n{item.patch}"
                for item in pr_meta.changed_files[:8]
                if item.patch
            ]
            if diff_parts:
                parts.append("PR diff:\n" + "\n\n".join(diff_parts)[:12000])
        return " | ".join(parts)

    def _clone_pull_request_repository(self, repository_url: str, pr_meta: GitHubPullRequestMetadata) -> str:
        repo_url = repository_url.strip().rstrip("/")
        if not repo_url.endswith(".git"):
            repo_url = f"{repo_url}.git"

        token = os.getenv("GITHUB_TOKEN")
        if token:
            # Embed token in URL — works reliably on all platforms including Windows
            repo_url = repo_url.replace("https://", f"https://x-access-token:{token}@")

        repo_dir = tempfile.mkdtemp(prefix="changegraph-pr-")

        try:
            repo = git.Repo.clone_from(repo_url, repo_dir, depth=1)
            if pr_meta.head_ref:
                try:
                    repo.git.fetch("origin", f"pull/{pr_meta.number}/head:pr-{pr_meta.number}")
                    repo.git.checkout(f"pr-{pr_meta.number}")
                except Exception:
                    repo.git.checkout(pr_meta.head_sha)
            elif pr_meta.head_sha:
                repo.git.checkout(pr_meta.head_sha)
            return repo_dir
        except Exception as exc:
            shutil.rmtree(repo_dir, ignore_errors=True)
            # Scrub token from error message before raising
            token = os.getenv("GITHUB_TOKEN", "")
            safe_msg = str(exc).replace(token, "***") if token else str(exc)
            raise GitHubAPIError(f"Unable to clone the GitHub repository for PR analysis: {safe_msg}")

    @staticmethod
    def _cleanup_repo(repo_path: str) -> None:
        if repo_path and os.path.isdir(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
