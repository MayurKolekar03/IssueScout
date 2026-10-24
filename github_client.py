"""
github_client.py – Fetches issue data, repo context, and file tree from GitHub REST API.
"""

from __future__ import annotations

import os
import re
from typing import Optional

import requests

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# ── helpers ────────────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    """Build request headers, including auth if a token is available."""
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def _get(url: str, params: Optional[dict] = None) -> requests.Response:
    """Thin wrapper around requests.get with standard headers."""
    return requests.get(url, headers=_headers(), params=params, timeout=15)


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """
    Parse a GitHub issue URL into (owner, repo, issue_number).
    Raises ValueError for invalid or PR URLs.
    """
    url = url.strip().rstrip("/")
    pattern = r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)"
    pr_pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"

    if re.match(pr_pattern, url):
        raise ValueError(
            "🔀 That looks like a **Pull Request** URL, not an issue. "
            "Paste a URL that contains `/issues/`."
        )

    m = re.match(pattern, url)
    if not m:
        raise ValueError(
            "❌ Invalid URL format. Expected: `https://github.com/{owner}/{repo}/issues/{number}`"
        )
    return m.group(1), m.group(2), int(m.group(3))


# ── main fetcher ───────────────────────────────────────────────────────────────

def fetch_issue_context(owner: str, repo: str, issue_number: int) -> dict:
    """
    Fetch everything IssueSherpa needs:
      - Issue metadata + first 10 comments
      - README (truncated)
      - CONTRIBUTING.md (truncated)
      - Repo file tree (filtered)

    Returns a dict with all context, or raises on fatal errors.
    """

    # ── 1. Issue ──────────────────────────────────────────────────────────────
    resp = _get(f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}")

    if resp.status_code == 404:
        raise ValueError(
            "🔍 Issue not found. The repo or issue number may be wrong, "
            "or the repository is private."
        )
    if resp.status_code == 403:
        data = resp.json()
        if "rate limit" in data.get("message", "").lower():
            raise ValueError(
                "⏳ GitHub API rate limit exceeded. Set a `GITHUB_TOKEN` "
                "to get 5,000 requests/hour instead of 60."
            )
        raise ValueError("🔒 Access denied. The repository may be private.")
    if resp.status_code != 200:
        raise ValueError(f"GitHub API error {resp.status_code}: {resp.text[:200]}")

    issue = resp.json()

    # ── 2. Comments ───────────────────────────────────────────────────────────
    comments: list[dict] = []
    if issue.get("comments", 0) > 0:
        c_resp = _get(
            f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={"per_page": 10},
        )
        if c_resp.status_code == 200:
            for c in c_resp.json():
                comments.append(
                    {
                        "author": c["user"]["login"],
                        "body": (c.get("body") or "")[:800],
                        "created_at": c["created_at"],
                    }
                )

    # ── 3. README ─────────────────────────────────────────────────────────────
    readme_text = _fetch_file_content(owner, repo, candidates=["README.md", "README.rst", "README"])
    readme_text = readme_text[:6000] if readme_text else ""

    # ── 4. CONTRIBUTING ───────────────────────────────────────────────────────
    contrib_text = _fetch_file_content(
        owner,
        repo,
        candidates=["CONTRIBUTING.md", ".github/CONTRIBUTING.md", "docs/CONTRIBUTING.md"],
    )
    contrib_text = contrib_text[:4000] if contrib_text else ""

    # ── 5. File tree ──────────────────────────────────────────────────────────
    file_tree = _fetch_file_tree(owner, repo)

    # ── 6. Repo stats ─────────────────────────────────────────────────────────
    repo_stats = {}
    repo_resp = _get(f"{GITHUB_API}/repos/{owner}/{repo}")
    if repo_resp.status_code == 200:
        rd = repo_resp.json()
        repo_stats = {
            "stars": rd.get("stargazers_count", 0),
            "forks": rd.get("forks_count", 0),
            "open_issues": rd.get("open_issues_count", 0),
            "language": rd.get("language") or "Unknown",
            "description": rd.get("description") or "",
            "topics": rd.get("topics", []),
        }

    # ── 7. Assemble ───────────────────────────────────────────────────────────
    return {
        "owner": owner,
        "repo": repo,
        "issue_number": issue_number,
        "title": issue.get("title", ""),
        "body": (issue.get("body") or "")[:3000],
        "state": issue.get("state", "open"),
        "labels": [lbl["name"] for lbl in issue.get("labels", [])],
        "assignees": [a["login"] for a in issue.get("assignees", [])],
        "created_at": issue.get("created_at", ""),
        "updated_at": issue.get("updated_at", ""),
        "html_url": issue.get("html_url", ""),
        "comments": comments,
        "comment_count": issue.get("comments", 0),
        "readme": readme_text,
        "contributing": contrib_text,
        "file_tree": file_tree,
        "repo_stats": repo_stats,
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _fetch_file_content(owner: str, repo: str, candidates: list[str]) -> str:
    """Try each candidate path; return decoded content of the first that exists."""
    import base64

    for path in candidates:
        resp = _get(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("encoding") == "base64":
                try:
                    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                except Exception:
                    return ""
    return ""


# Patterns to drop from the file tree (noisy / irrelevant)
_SKIP_PATTERNS = re.compile(
    r"(node_modules/|dist/|build/|\.lock$|package-lock\.json|yarn\.lock|"
    r"pnpm-lock\.yaml|\.png$|\.jpg$|\.jpeg$|\.gif$|\.svg$|\.ico$|\.woff|\.ttf|"
    r"\.eot$|\.mp4$|\.pdf$|__pycache__|\.pyc$|\.min\.js$|\.min\.css$)",
    re.IGNORECASE,
)


def _fetch_file_tree(owner: str, repo: str) -> list[str]:
    """
    Fetch the full recursive file tree via the git trees API.
    Returns up to 400 filtered file paths.
    """
    # Get default branch first
    repo_resp = _get(f"{GITHUB_API}/repos/{owner}/{repo}")
    if repo_resp.status_code != 200:
        return []
    default_branch = repo_resp.json().get("default_branch", "main")

    tree_resp = _get(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}",
        params={"recursive": "1"},
    )
    if tree_resp.status_code != 200:
        return []

    data = tree_resp.json()
    paths = []
    for item in data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path = item["path"]
        if not _SKIP_PATTERNS.search(path):
            paths.append(path)
        if len(paths) >= 400:
            break

    return paths
