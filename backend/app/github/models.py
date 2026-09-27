from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GitHubPullRequestFile:
    filename: str
    status: str
    additions: int
    deletions: int
    patch: Optional[str] = None


@dataclass
class GitHubPullRequestMetadata:
    owner: str
    repo: str
    repository: str
    number: int
    title: str
    body: Optional[str]
    base_sha: str
    head_sha: str
    head_ref: str
    changed_files: list[GitHubPullRequestFile] = field(default_factory=list)
