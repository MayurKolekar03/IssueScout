"""
test_suite.py – Comprehensive automated test suite for IssueScout.
Tests URL parsing, pre-checks, file verification, JSON extraction, and export.
"""

import unittest
from github_client import parse_issue_url
from utils import verify_file_paths, run_pre_checks, format_markdown_export
from llm import _extract_json


class TestIssueScout(unittest.TestCase):

    # ── 1. URL Parsing Tests ──────────────────────────────────────────────────
    def test_parse_valid_urls(self):
        cases = [
            ("https://github.com/owner/repo/issues/123", ("owner", "repo", 123)),
            ("http://github.com/psf/requests/issues/6523", ("psf", "requests", 6523)),
            ("https://github.com/facebook/react/issues/31113/", ("facebook", "react", 31113)),
            ("https://github.com/the-algorithms/python/issues/10017?param=value", ("the-algorithms", "python", 10017)),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(parse_issue_url(url), expected)

    def test_parse_invalid_urls(self):
        invalid_urls = [
            "https://github.com/owner/repo",                # repo url, not issue
            "https://github.com/owner/repo/pull/123",        # pull request
            "https://github.com/owner/repo/issues",          # issue list
            "https://gitlab.com/owner/repo/issues/123",      # non-github
            "not a url",                                    # junk
            "",                                             # empty
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    parse_issue_url(url)

    # ── 2. JSON Extraction Tests ──────────────────────────────────────────────
    def test_extract_clean_json(self):
        data = '{"summary": "Test summary", "steps": ["Step 1"]}'
        result = _extract_json(data)
        self.assertEqual(result["summary"], "Test summary")
        self.assertEqual(result["steps"], ["Step 1"])

    def test_extract_json_with_code_fences(self):
        data = '```json\n{"summary": "Test fenced", "steps": []}\n```'
        result = _extract_json(data)
        self.assertEqual(result["summary"], "Test fenced")

    def test_extract_json_with_surrounding_prose(self):
        data = 'Here is the plan:\n```json\n{"difficulty": "beginner"}\n```\nHope this helps!'
        result = _extract_json(data)
        self.assertEqual(result["difficulty"], "beginner")

    def test_extract_invalid_json(self):
        with self.assertRaises(ValueError):
            _extract_json("No json here at all")

    # ── 3. Anti-Hallucination File Verification ───────────────────────────────
    def test_verify_file_paths(self):
        repo_files = [
            "src/index.ts",
            "src/utils/math.ts",
            "README.md",
            "package.json",
        ]
        suggested = [
            {"path": "src/index.ts", "reason": "Main entry point"},
            {"path": "src/utils/math.ts", "reason": "Helper functions"},
            {"path": "src/nonexistent/file.ts", "reason": "Fantasy file"},
        ]
        verified = verify_file_paths(suggested, repo_files)
        self.assertEqual(len(verified), 3)
        self.assertTrue(verified[0]["verified"])
        self.assertTrue(verified[1]["verified"])
        self.assertFalse(verified[2]["verified"])

    # ── 4. Pre-Flight Checks ──────────────────────────────────────────────────
    def test_pre_checks_closed_issue(self):
        ctx = {
            "state": "closed",
            "assignees": [],
            "comments": [],
            "created_at": "2026-01-01T00:00:00Z",
            "contributing": "Guide",
            "labels": [],
        }
        checks = run_pre_checks(ctx)
        closed_warning = any("closed" in c["message"].lower() for c in checks)
        self.assertTrue(closed_warning)

    def test_pre_checks_assigned_issue(self):
        ctx = {
            "state": "open",
            "assignees": ["alice"],
            "comments": [],
            "created_at": "2026-01-01T00:00:00Z",
            "contributing": "Guide",
            "labels": ["good first issue"],
        }
        checks = run_pre_checks(ctx)
        assigned_warning = any("assigned" in c["message"].lower() for c in checks)
        good_first_flag = any("good first issue" in c["message"].lower() for c in checks)
        self.assertTrue(assigned_warning)
        self.assertTrue(good_first_flag)

    # ── 5. Markdown Export Formatting ─────────────────────────────────────────
    def test_markdown_export(self):
        ctx = {
            "owner": "testorg",
            "repo": "testrepo",
            "issue_number": 42,
            "title": "Fix memory leak",
            "html_url": "https://github.com/testorg/testrepo/issues/42",
        }
        plan = {
            "difficulty": "Intermediate",
            "estimated_time": "2 hours",
            "summary": "Fix buffer allocation leak.",
            "steps": ["Step 1", "Step 2"],
            "contributing_checklist": ["Run tests"],
            "claim_comment": "I'd like to take this.",
            "pr_title": "fix: resolve memory leak #42",
            "pr_description": "Fixes #42",
            "questions_to_ask_maintainer": ["Which branch?"],
        }
        verified_files = [{"path": "leak.c", "reason": "Origin of leak", "verified": True}]
        md = format_markdown_export(ctx, plan, verified_files)

        self.assertIn("# IssueScout Plan", md)
        self.assertIn("Fix memory leak", md)
        self.assertIn("testorg/testrepo", md)
        self.assertIn("#42", md)
        self.assertIn("leak.c", md)
        self.assertIn("I'd like to take this.", md)


if __name__ == "__main__":
    unittest.main()
