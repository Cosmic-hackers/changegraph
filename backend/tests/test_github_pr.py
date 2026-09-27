"""
tests/test_github_pr.py — Tests for Phase 4 GitHub PR analysis.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.github.client import GitHubClient, GitHubAPIError, GitHubNotFoundError, GitHubRateLimitError

client = TestClient(app)

SAMPLE_PR_PAYLOAD = {
    "title": "feat: add discount support",
    "body": "Adds discount_percent to calculate_total",
    "base": {"sha": "abc123"},
    "head": {"sha": "def456", "ref": "feature/discount"},
    "number": 1,
}

SAMPLE_FILES_PAYLOAD = [
    {
        "filename": "sample_repos/test_shop/checkout.py",
        "status": "modified",
        "additions": 5,
        "deletions": 2,
        "patch": "@@ -29,6 +29,7 @@ def calculate_total(cart_items):\n+    discount_percent: float = 0.0",
    }
]


def test_parse_repository_url_valid():
    owner, repo = GitHubClient.parse_repository_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_repository_url_strips_git():
    owner, repo = GitHubClient.parse_repository_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"


def test_parse_repository_url_invalid_scheme():
    with pytest.raises(ValueError, match="http or https"):
        GitHubClient.parse_repository_url("ftp://github.com/owner/repo")


def test_parse_repository_url_not_github():
    with pytest.raises(ValueError, match="Only GitHub"):
        GitHubClient.parse_repository_url("https://gitlab.com/owner/repo")


def test_parse_repository_url_missing_repo():
    with pytest.raises(ValueError, match="owner/repository"):
        GitHubClient.parse_repository_url("https://github.com/owner")


def test_parse_repository_url_empty():
    with pytest.raises(ValueError, match="required"):
        GitHubClient.parse_repository_url("")


def test_parse_repository_url_invalid_chars():
    with pytest.raises(ValueError, match="invalid"):
        GitHubClient.parse_repository_url("https://github.com/own er/repo")


def test_github_pr_analyze_invalid_pr_number():
    response = client.post("/api/github/pr/analyze", json={
        "repository": "https://github.com/owner/repo",
        "pull_request": 0,
    })
    assert response.status_code == 400


def test_github_pr_analyze_negative_pr_number():
    response = client.post("/api/github/pr/analyze", json={
        "repository": "https://github.com/owner/repo",
        "pull_request": -1,
    })
    assert response.status_code == 400


def test_github_pr_analyze_not_found():
    with patch("backend.app.api.analyze.GitHubPRService") as mock_svc:
        mock_svc.return_value.analyze_pull_request.side_effect = GitHubNotFoundError("Not found")
        response = client.post("/api/github/pr/analyze", json={
            "repository": "https://github.com/owner/repo",
            "pull_request": 999,
        })
    assert response.status_code == 404


def test_github_pr_analyze_rate_limit():
    with patch("backend.app.api.analyze.GitHubPRService") as mock_svc:
        mock_svc.return_value.analyze_pull_request.side_effect = GitHubRateLimitError("Rate limited")
        response = client.post("/api/github/pr/analyze", json={
            "repository": "https://github.com/owner/repo",
            "pull_request": 1,
        })
    assert response.status_code == 429


def test_github_pr_analyze_api_error():
    with patch("backend.app.api.analyze.GitHubPRService") as mock_svc:
        mock_svc.return_value.analyze_pull_request.side_effect = GitHubAPIError("API error")
        response = client.post("/api/github/pr/analyze", json={
            "repository": "https://github.com/owner/repo",
            "pull_request": 1,
        })
    assert response.status_code == 502


def test_github_client_auth_header():
    c = GitHubClient(token="test-token-abc")
    assert c.token == "test-token-abc"


def test_github_client_no_token():
    with patch.dict("os.environ", {}, clear=True):
        c = GitHubClient(token=None)
    assert c.token is None


def test_github_client_request_401():
    c = GitHubClient(token="bad-token")
    mock_response = MagicMock()
    mock_response.status_code = 401
    with patch.object(c._client, "get", return_value=mock_response):
        with pytest.raises(GitHubAPIError, match="authentication failed"):
            c._request("/repos/owner/repo/pulls/1")


def test_github_client_request_404():
    c = GitHubClient(token="tok")
    mock_response = MagicMock()
    mock_response.status_code = 404
    with patch.object(c._client, "get", return_value=mock_response):
        with pytest.raises(GitHubNotFoundError):
            c._request("/repos/owner/repo/pulls/999")


def test_github_client_request_429_rate_limit():
    c = GitHubClient(token="tok")
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.headers = {"x-ratelimit-remaining": "0"}
    with patch.object(c._client, "get", return_value=mock_response):
        with pytest.raises(GitHubRateLimitError):
            c._request("/repos/owner/repo/pulls/1")
