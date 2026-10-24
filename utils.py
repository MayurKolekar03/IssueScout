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


def generate_pdf_export(ctx: dict, plan: dict, verified_files: list[dict]) -> bytes:
    """
    Generate a styled, multi-page PDF report for the IssueScout plan using reportlab.
    Returns bytes suitable for Streamlit st.download_button.
    """
    import io
    import html
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e1b4b"),
        alignment=0,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#6366f1"),
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1e1b4b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=6,
    )
    code_style = ParagraphStyle(
        "CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=6,
        spaceAfter=8,
    )
    step_num_style = ParagraphStyle(
        "StepNum",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#4338ca"),
    )

    story = []

    # Title & Header
    story.append(Paragraph("IssueScout 🧭 Contribution Roadmap", title_style))
    now = datetime.now(timezone.utc).strftime("%B %d, %Y - %H:%M UTC")
    story.append(Paragraph(f"Generated on {now} &nbsp;·&nbsp; AI Open-Source Mentor Plan", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5"), spaceAfter=10))

    owner = html.escape(str(ctx.get("owner", "")))
    repo = html.escape(str(ctx.get("repo", "")))
    num = html.escape(str(ctx.get("issue_number", "")))
    title = html.escape(str(ctx.get("title", "")))

    # Metadata Table
    diff = plan.get("difficulty", "Beginner").capitalize()
    time_est = plan.get("estimated_time", "1-2 hours")

    meta_data = [
        [
            Paragraph("<b>Repository:</b>", body_style),
            Paragraph(f"{owner}/{repo}", body_style),
            Paragraph("<b>Difficulty:</b>", body_style),
            Paragraph(f"<b>{diff}</b> ({time_est})", body_style),
        ],
        [
            Paragraph("<b>Issue:</b>", body_style),
            Paragraph(f"#{num}: {title}", body_style),
            Paragraph("<b>Status:</b>", body_style),
            Paragraph(html.escape(str(ctx.get("state", "open"))).upper(), body_style),
        ],
    ]
    t = Table(meta_data, colWidths=[70, 230, 65, 175])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(t)
    story.append(Spacer(1, 10))

    # Executive Summary
    story.append(Paragraph("🧭 Executive Summary", h2_style))
    summary_text = html.escape(plan.get("summary", "No summary provided."))
    story.append(Paragraph(summary_text, body_style))

    # Step-by-Step Implementation
    story.append(Paragraph("🪜 Step-by-Step Implementation", h2_style))
    steps = plan.get("steps", [])
    if steps:
        step_rows = []
        for i, s in enumerate(steps, 1):
            step_rows.append([
                Paragraph(f"<b>{i}.</b>", step_num_style),
                Paragraph(html.escape(str(s)), body_style),
            ])
        st_table = Table(step_rows, colWidths=[24, 516])
        st_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ])
        )
        story.append(st_table)
    else:
        story.append(Paragraph("No steps generated.", body_style))

    # Suggested Files Table
    story.append(Paragraph("📂 Target Files to Inspect / Modify", h2_style))
    if verified_files:
        file_rows = [[
            Paragraph("<b>File Path</b>", body_style),
            Paragraph("<b>Purpose / Reason</b>", body_style),
            Paragraph("<b>Verification</b>", body_style),
        ]]
        for f in verified_files:
            v_text = "Verified (in repo)" if f.get("verified") else "Predicted"
            file_rows.append([
                Paragraph(f"<code>{html.escape(str(f.get('path','')))}</code>", code_style),
                Paragraph(html.escape(str(f.get("reason", ""))), body_style),
                Paragraph(v_text, body_style),
            ])
        ft_table = Table(file_rows, colWidths=[180, 240, 120])
        ft_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e7ff")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ])
        )
        story.append(ft_table)
    else:
        story.append(Paragraph("No specific target files specified.", body_style))

    # Contributor Checklist
    checklist = plan.get("contributing_checklist", [])
    if checklist:
        story.append(Paragraph("✅ Contributor Checklist", h2_style))
        for item in checklist:
            story.append(Paragraph(f"[  ] &nbsp; {html.escape(str(item))}", body_style))

    # Draft Claim Comment
    claim = plan.get("claim_comment", "").strip()
    if claim:
        story.append(KeepTogether([
            Paragraph("💬 Draft Claim Comment (Post on GitHub)", h2_style),
            Paragraph(html.escape(claim).replace("\n", "<br/>"), code_style),
        ]))

    # Draft PR
    pr_t = plan.get("pr_title", "")
    pr_d = plan.get("pr_description", "")
    if pr_t or pr_d:
        pr_content = []
        pr_content.append(Paragraph("🔀 Draft Pull Request", h2_style))
        if pr_t:
            pr_content.append(Paragraph(f"<b>Title:</b> {html.escape(pr_t)}", body_style))
        if pr_d:
            pr_content.append(Paragraph(html.escape(pr_d).replace("\n", "<br/>"), code_style))
        story.append(KeepTogether(pr_content))

    # Questions for Maintainers
    questions = plan.get("questions_to_ask_maintainer", [])
    if questions:
        q_elements = [Paragraph("❓ Clarifying Questions for Maintainers", h2_style)]
        for q in questions:
            q_elements.append(Paragraph(f"• {html.escape(str(q))}", body_style))
        story.append(KeepTogether(q_elements))

    # Footer
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=8))
    story.append(Paragraph(
        "Report generated by <b>IssueScout</b> (https://github.com/MayurKolekar03/IssueScout). "
        "AI-generated roadmap — please verify requirements with project maintainers.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontName="Helvetica-Oblique", fontSize=8, textColor=colors.HexColor("#64748b"))
    ))

    doc.build(story)
    return buf.getvalue()
