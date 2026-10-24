"""
utils.py – Pre-checks (no LLM needed) and helper functions for IssueScout.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

# Phrases that suggest someone is already working on the issue
CLAIM_PHRASES = [
    r"\bi.?ll take this\b",
    r"\bcan i work on\b",
    r"\bworking on this\b",
    r"\bassign me\b",
    r"\bi.?m working on\b",
    r"\bi.?d like to (work on|fix|tackle|take)\b",
    r"\btaking this\b",
    r"\bclaiming this\b",
    r"\bi.?ve started\b",
    r"\bwip\b",
]
_CLAIM_RE = re.compile("|".join(CLAIM_PHRASES), re.IGNORECASE)

# Labels that are good signals for beginners
GOOD_LABELS = {"good first issue", "help wanted", "beginner friendly", "easy", "starter", "first-timers-only"}


def run_pre_checks(ctx: dict) -> list[dict]:
    """
    Run quick pre-checks that don't need the LLM.

    Returns a list of check result dicts:
      {
        "type": "warning" | "success" | "info",
        "icon": str,
        "message": str
      }
    """
    checks: list[dict] = []
    labels_lower = {lbl.lower() for lbl in ctx.get("labels", [])}

    # ── Closed issue ──────────────────────────────────────────────────────────
    if ctx.get("state") == "closed":
        checks.append(
            {
                "type": "warning",
                "icon": "🔒",
                "message": "This issue is **closed**. It may already be resolved — double-check before contributing.",
            }
        )

    # ── Assigned to someone ───────────────────────────────────────────────────
    assignees = ctx.get("assignees", [])
    if assignees:
        names = ", ".join(f"`@{a}`" for a in assignees)
        checks.append(
            {
                "type": "warning",
                "icon": "👤",
                "message": f"Already assigned to {names}. Check with the maintainer before starting.",
            }
        )

    # ── Comment claiming ──────────────────────────────────────────────────────
    claimers: list[str] = []
    for comment in ctx.get("comments", []):
        body = comment.get("body", "")
        if _CLAIM_RE.search(body):
            claimers.append(comment["author"])

    if claimers:
        unique = list(dict.fromkeys(claimers))  # preserve order, deduplicate
        names_str = ", ".join(f"`@{u}`" for u in unique)
        checks.append(
            {
                "type": "warning",
                "icon": "🙋",
                "message": f"Someone may already be working on this — {names_str} posted a claim comment.",
            }
        )

    # ── Good labels ───────────────────────────────────────────────────────────
    matched_good = [lbl for lbl in ctx.get("labels", []) if lbl.lower() in GOOD_LABELS]
    if matched_good:
        label_badges = " ".join(f"`{lbl}`" for lbl in matched_good)
        checks.append(
            {
                "type": "success",
                "icon": "✅",
                "message": f"Labelled as {label_badges} — great for contributors!",
            }
        )

    # ── All other labels (info) ───────────────────────────────────────────────
    other_labels = [lbl for lbl in ctx.get("labels", []) if lbl.lower() not in GOOD_LABELS]
    if other_labels:
        label_str = " ".join(f"`{lbl}`" for lbl in other_labels)
        checks.append({"type": "info", "icon": "🏷️", "message": f"Labels: {label_str}"})

    # ── No issues found (all green) ───────────────────────────────────────────
    if not checks:
        checks.append(
            {
                "type": "success",
                "icon": "🟢",
                "message": "No blockers found. This issue looks open and unclaimed!",
            }
        )

    return checks


def verify_file_paths(likely_files: list[dict], real_tree: list[str]) -> list[dict]:
    """
    Anti-hallucination check: mark each suggested file as verified (exists)
    or unverified (model guess) against the real repo file tree.
    """
    tree_set = set(real_tree)
    annotated = []
    for item in likely_files:
        path = item.get("path", "")
        exists = path in tree_set
        annotated.append(
            {
                "path": path,
                "reason": item.get("reason", ""),
                "verified": exists,
                "badge": "✅ exists in repo" if exists else "⚠️ not found (model guess)",
            }
        )
    return annotated


def format_markdown_export(ctx: dict, plan: dict, verified_files: list[dict]) -> str:
    """
    Generate a Markdown string summarising the full IssueScout plan.
    Used for the "Download plan as Markdown" button.
    """
    owner, repo = ctx["owner"], ctx["repo"]
    issue_number = ctx["issue_number"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    difficulty_emoji = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(
        plan.get("difficulty", "").lower(), "⚪"
    )

    lines = [
        f"# IssueScout Plan",
        f"",
        f"**Repo:** [{owner}/{repo}](https://github.com/{owner}/{repo})  ",
        f"**Issue:** [#{issue_number}]({ctx.get('html_url', '')}) — {ctx.get('title', '')}  ",
        f"**Generated:** {now}  ",
        f"",
        f"---",
        f"",
        f"## 🧭 Summary",
        f"",
        plan.get("summary", ""),
        f"",
        f"## 🎯 Difficulty",
        f"",
        f"{difficulty_emoji} **{plan.get('difficulty', '').capitalize()}** — {plan.get('difficulty_reason', '')}  ",
        f"⏱️ Estimated time: **{plan.get('estimated_time', '')}**",
        f"",
        f"## 📂 Files to Look At",
        f"",
    ]
    for f in verified_files:
        path = f.get("path", "")
        reason = f.get("reason", "")
        badge = f.get("badge", "✅ exists in repo" if f.get("verified") else "⚠️ not found (model guess)")
        lines.append(f"- `{path}` — {reason} _{badge}_")
    lines.append("")

    lines += [
        f"## 🪜 Step-by-Step Plan",
        f"",
    ]
    for i, step in enumerate(plan.get("steps", []), 1):
        lines.append(f"{i}. {step}")
    lines.append("")

    lines += [
        f"## ✅ Contributor Checklist",
        f"",
    ]
    for item in plan.get("contributing_checklist", []):
        lines.append(f"- [ ] {item}")
    lines.append("")

    lines += [
        f"## 💬 Draft Claim Comment",
        f"",
        f"```",
        plan.get("claim_comment", ""),
        f"```",
        f"",
        f"## 🔀 Draft PR",
        f"",
        f"**Title:** `{plan.get('pr_title', '')}`",
        f"",
        plan.get("pr_description", ""),
        f"",
        f"## ❓ Questions for the Maintainer",
        f"",
    ]
    for q in plan.get("questions_to_ask_maintainer", []):
        lines.append(f"- {q}")
    lines.append("")

    lines += [
        f"---",
        f"",
        f"> *This plan was generated by [IssueScout](https://github.com/your-org/issuescout) "
        f"using an open-weight AI model. Verify all suggestions before acting.*",
    ]

    return "\n".join(lines)
