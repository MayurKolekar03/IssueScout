"""
prompts.py – System and user prompt templates for IssueSherpa.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are IssueSherpa, a patient senior open-source maintainer who mentors first-time contributors.

Rules:
- Use ONLY the information provided in the user message.
- NEVER invent file paths. Choose likely_files ONLY from the provided <file_tree> list.
- If something is unclear, put it in questions_to_ask_maintainer.
- Write simply. When you use a technical term, briefly explain it.
- Return ONLY valid JSON. No markdown fences, no prose outside the JSON object.
"""

JSON_SCHEMA_DESCRIPTION = """\
Return a single JSON object with EXACTLY these keys:
{
  "summary": "<3-4 plain-English sentences describing the issue and what needs to be done>",
  "difficulty": "<one of: beginner | intermediate | advanced>",
  "difficulty_reason": "<one sentence explaining the difficulty rating>",
  "estimated_time": "<e.g. '1-2 hours' or '2-4 days'>",
  "likely_files": [
    {"path": "<exact path from file_tree>", "reason": "<why this file matters>"}
  ],
  "steps": [
    "<numbered action a beginner can follow, written as a sentence>"
  ],
  "contributing_checklist": [
    "<one checklist item per entry, e.g. 'Run tests with npm test before pushing'>"
  ],
  "claim_comment": "<polite, short comment to post on the issue to claim it>",
  "pr_title": "<conventional-commit style PR title, e.g. fix: correct typo in README>",
  "pr_description": "<Markdown PR body that includes 'Closes #{issue_number}', what you changed, and how to test it>",
  "questions_to_ask_maintainer": [
    "<a specific question worth asking before starting>"
  ]
}

Constraints:
- likely_files: max 6 items, paths must come VERBATIM from the provided file_tree.
- steps: max 10 items.
- contributing_checklist: if CONTRIBUTING is empty, give 5 generic open-source best practices.
"""


def build_user_prompt(ctx: dict) -> str:
    """
    Build the user-facing prompt from fetched GitHub context.
    ctx keys: owner, repo, issue_number, title, body, labels, assignees,
               created_at, comments, readme, contributing, file_tree
    """
    repo_full = f"{ctx['owner']}/{ctx['repo']}"
    issue_number = ctx["issue_number"]

    # Comments block
    comments_block = ""
    for c in ctx.get("comments", [])[:10]:
        comments_block += (
            f"  [{c['author']} at {c['created_at']}]: {c['body'][:600]}\n\n"
        )
    if not comments_block:
        comments_block = "  (no comments)"

    # File tree block — join as newline-separated list
    tree_lines = "\n".join(ctx.get("file_tree", [])[:400])
    if not tree_lines:
        tree_lines = "(file tree unavailable)"

    readme_excerpt = ctx.get("readme", "(no README found)")[:6000]
    contrib_excerpt = ctx.get("contributing", "")
    contrib_section = (
        contrib_excerpt[:4000]
        if contrib_excerpt
        else "(no CONTRIBUTING.md found — use generic best practices)"
    )

    labels_str = ", ".join(ctx.get("labels", [])) or "none"
    assignees_str = ", ".join(ctx.get("assignees", [])) or "none"

    prompt = f"""\
<repository>{repo_full}</repository>
<issue_number>{issue_number}</issue_number>
<issue_title>{ctx.get('title', '')}</issue_title>
<issue_state>{ctx.get('state', 'open')}</issue_state>
<labels>{labels_str}</labels>
<assignees>{assignees_str}</assignees>
<created_at>{ctx.get('created_at', '')}</created_at>

<issue_body>
{ctx.get('body', '')[:3000]}
</issue_body>

<comments>
{comments_block}
</comments>

<readme>
{readme_excerpt}
</readme>

<contributing>
{contrib_section}
</contributing>

<file_tree>
{tree_lines}
</file_tree>

{JSON_SCHEMA_DESCRIPTION.replace('{issue_number}', str(issue_number))}
"""
    return prompt
