from __future__ import annotations

import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

import httpx


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API request fails."""


class GitHubNotFoundError(GitHubAPIError):
    """Raised when the repository or PR cannot be found."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub rate limiting blocks the API call."""


class GitHubClient:
    """Minimal GitHub REST client for PR analysis."""

    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.github.com"):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=20.0)

    @staticmethod
    def parse_repository_url(repository_url: str) -> tuple[str, str]:
        if not repository_url or not isinstance(repository_url, str):
            raise ValueError("Repository URL is required.")

        normalized = repository_url.strip().rstrip("/")
        if normalized.endswith(".git"):
            normalized = normalized[:-4]

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Repository URL must use http or https.")
        if parsed.netloc.lower() != "github.com":
            raise ValueError("Only GitHub repository URLs are supported.")

        path_parts = [segment for segment in parsed.path.split("/") if segment]
        if len(path_parts) != 2:
            raise ValueError("Repository URL must be in the form https://github.com/owner/repository.")

        owner, repo = path_parts[0], path_parts[1]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
            raise ValueError("Repository URL contains an invalid GitHub owner or repository name.")

        return owner, repo

    def _request(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ChangeGraph/Phase4",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = self._client.get(f"{self.base_url}{path}", params=params, headers=headers)

        if response.status_code == 401:
            raise GitHubAPIError("GitHub authentication failed or token is invalid.")
        if response.status_code == 404:
            raise GitHubNotFoundError("GitHub repository or pull request was not found.")
        if response.status_code == 403:
            remaining = response.headers.get("x-ratelimit-remaining")
            if remaining == "0":
                raise GitHubRateLimitError("GitHub API rate limit reached.")
            raise GitHubAPIError("GitHub API request forbidden.")
        if response.status_code >= 400:
            raise GitHubAPIError(f"GitHub API request failed with status {response.status_code}: {response.text}")

        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - defensive fallback
            raise GitHubAPIError("GitHub API returned malformed JSON.") from exc

    def fetch_pull_request(self, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        return self._request(f"/repos/{owner}/{repo}/pulls/{pull_number}")

    def fetch_pull_request_files(self, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        return self._request(f"/repos/{owner}/{repo}/pulls/{pull_number}/files")

    def close(self) -> None:
        self._client.close()
