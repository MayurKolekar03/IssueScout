"""
app.py – IssueSherpa: Turn any GitHub issue into a clear plan to contribute.
Aesthetic, mobile-friendly redesign with responsive CSS, intuitive guidance,
and real-time validation.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from collections import Counter
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from github_client import fetch_issue_context, parse_issue_url
from llm import LLM_MODEL, get_issue_plan
from utils import format_markdown_export, run_pre_checks, verify_file_paths

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="IssueSherpa 🧗 - Open Source AI Mentor",
    page_icon="🧗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Helper functions ───────────────────────────────────────────────────────────

def _time_ago(iso: str) -> str:
    """Convert ISO timestamp to human-readable 'X days ago'."""
    if not iso:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        days = delta.days
        if days == 0:
            hours = delta.seconds // 3600
            return f"{hours}h ago" if hours else "just now"
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        return f"{months}mo ago"
    except Exception:
        return ""


def _detect_tech_stack(file_tree: list[str]) -> list[str]:
    """Infer tech stack from file extensions in the repo tree."""
    ext_map = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".tsx": "React / TSX", ".jsx": "React / JSX", ".java": "Java",
        ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
        ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
        ".kt": "Kotlin", ".dart": "Dart", ".vue": "Vue",
        ".scss": "SCSS", ".css": "CSS", ".html": "HTML",
        ".dockerfile": "Docker", ".sh": "Shell", ".sql": "SQL",
    }
    counts: Counter = Counter()
    for path in file_tree:
        ext = os.path.splitext(path)[1].lower()
        if ext in ext_map:
            counts[ext_map[ext]] += 1

    filtered = [k for k, _ in counts.most_common(6)]
    return filtered


def _fmt_num(n: int) -> str:
    """Format large numbers: 12345 → '12.3k'."""
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


# ── CSS Styling (Mobile-friendly, Modern, Accessible) ──────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* Reset & Fonts */
html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
#MainMenu, footer, header { visibility: hidden; }

/* Base background */
.stApp {
    background: linear-gradient(180deg, #f8faff 0%, #f1f5f9 100%);
    color: #0f172a;
}

/* Container constraints for clean reading */
.block-container {
    max-width: 1100px !important;
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* ── Hero Banner ── */
.sherpa-hero {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4338ca 70%, #6366f1 100%);
    border-radius: 20px;
    padding: 2.2rem 2.2rem;
    color: white;
    box-shadow: 0 16px 36px -8px rgba(49, 46, 129, 0.35);
    position: relative;
    overflow: hidden;
    margin-bottom: 1.5rem;
}
.sherpa-hero::after {
    content: "🧗";
    position: absolute;
    right: 1.5rem;
    bottom: -0.5rem;
    font-size: 7rem;
    opacity: 0.15;
    pointer-events: none;
}
.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(255, 255, 255, 0.16);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.28);
    padding: 0.3rem 0.85rem;
    border-radius: 9999px;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 0.8rem;
}
.hero-title {
    font-size: clamp(1.8rem, 4vw, 2.7rem);
    font-weight: 800;
    line-height: 1.15;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.02em;
}
.hero-subtitle {
    font-size: clamp(0.95rem, 2vw, 1.12rem);
    color: #e0e7ff;
    line-height: 1.5;
    margin: 0;
    max-width: 650px;
}

/* ── Card Containers ── */
.sherpa-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.05);
    margin-bottom: 1.25rem;
}

/* ── Explainer Box (Repo URL vs Issue URL) ── */
.url-guide-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 1.4rem;
    border: 1px solid #e0e7ff;
    box-shadow: 0 4px 18px rgba(99, 102, 241, 0.06);
    margin-bottom: 1.2rem;
}
.url-guide-header {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1e1b4b;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.6rem;
}
.url-comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.8rem;
    margin-top: 0.8rem;
    margin-bottom: 0.8rem;
}
@media (max-width: 640px) {
    .url-comparison {
        grid-template-columns: 1fr;
    }
}
.url-comp-bad {
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
    font-size: 0.82rem;
}
.url-comp-good {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
    padding: 0.75rem 0.9rem;
    font-size: 0.82rem;
}

/* URL anatomy badge bar */
.url-anatomy {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    margin: 0.6rem 0;
}
.url-seg {
    padding: 0.25rem 0.45rem;
    border-radius: 6px;
    font-weight: 600;
}
.seg-base   { background: #f1f5f9; color: #475569; }
.seg-owner  { background: #dbeafe; color: #1e40af; }
.seg-repo   { background: #e0e7ff; color: #3730a3; }
.seg-issues { background: #fef08a; color: #854d0e; }
.seg-num    { background: #bbf7d0; color: #166534; }
.seg-slash  { color: #94a3b8; font-weight: bold; }

/* ── Validation Alerts ── */
.val-valid {
    background: #ecfdf5;
    border-left: 4px solid #10b981;
    color: #065f46;
    padding: 0.65rem 0.9rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 500;
    margin-top: 0.4rem;
}
.val-warning {
    background: #fffbeb;
    border-left: 4px solid #f59e0b;
    color: #92400e;
    padding: 0.65rem 0.9rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 500;
    margin-top: 0.4rem;
}
.val-info {
    background: #eff6ff;
    border-left: 4px solid #3b82f6;
    color: #1e40af;
    padding: 0.65rem 0.9rem;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 500;
    margin-top: 0.4rem;
}

/* ── Streamlit UI Elements Customization ── */
div[data-testid="stTextInput"] > div > input {
    border: 2px solid #cbd5e1 !important;
    border-radius: 12px !important;
    padding: 0.75rem 1rem !important;
    font-size: 0.95rem !important;
    font-family: 'JetBrains Mono', monospace !important;
    background: #ffffff !important;
    color: #0f172a !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stTextInput"] > div > input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15) !important;
}

div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.75rem 1.8rem !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 0.2px !important;
    box-shadow: 0 8px 20px -4px rgba(79, 70, 229, 0.4) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    width: 100% !important;
    max-width: 320px !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 24px -4px rgba(79, 70, 229, 0.5) !important;
}

/* Example chip buttons */
div[data-testid="stButton"] button:not([kind="primary"]) {
    border-radius: 10px !important;
    border: 1px solid #cbd5e1 !important;
    background: #ffffff !important;
    color: #334155 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    padding: 0.4rem 0.75rem !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stButton"] button:not([kind="primary"]):hover {
    background: #f1f5f9 !important;
    border-color: #94a3b8 !important;
    color: #0f172a !important;
}

/* Tabs styling */
div[data-testid="stTabs"] {
    margin-top: 1rem;
}
div[data-testid="stTabs"] [data-testid="stTab"] {
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    padding: 0.6rem 1rem !important;
    color: #64748b !important;
}
div[data-testid="stTabs"] [aria-selected="true"] {
    color: #4f46e5 !important;
    border-bottom: 3px solid #4f46e5 !important;
}

/* ── Stats & Chips Grid ── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.6rem;
    margin-bottom: 1.2rem;
}
.stat-box {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.7rem 0.9rem;
    display: flex;
    flex-direction: column;
    box-shadow: 0 2px 6px rgba(0,0,0,0.02);
}
.stat-box-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 0.15rem;
}
.stat-box-val {
    font-size: 1.15rem;
    font-weight: 800;
    color: #1e1b4b;
}

/* Tech badges */
.tech-badge-container {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.8rem;
}
.tech-pill {
    background: #e0e7ff;
    color: #3730a3;
    border: 1px solid #c7d2fe;
    border-radius: 9999px;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 0.25rem 0.7rem;
}

/* Difficulty Card */
.diff-container {
    border-radius: 14px;
    padding: 1.25rem;
    display: flex;
    align-items: center;
    gap: 1.2rem;
    margin-bottom: 1.2rem;
}
.diff-easy {
    background: #f0fdf4;
    border: 1px solid #86efac;
}
.diff-med {
    background: #fffbeb;
    border: 1px solid #fde047;
}
.diff-hard {
    background: #fff1f2;
    border: 1px solid #fca5a5;
}

/* Steps list */
.step-item {
    display: flex;
    gap: 0.9rem;
    align-items: flex-start;
    margin-bottom: 0.9rem;
}
.step-num {
    min-width: 2rem;
    height: 2rem;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 0.85rem;
    flex-shrink: 0;
}
.step-body {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.92rem;
    color: #1e293b;
    line-height: 1.6;
    width: 100%;
}

/* File items */
.file-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin-bottom: 0.6rem;
}
.file-name {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 0.88rem;
    color: #0f172a;
}
.file-desc {
    font-size: 0.82rem;
    color: #475569;
    margin-top: 0.2rem;
}

/* Mobile Media Queries */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    .sherpa-hero {
        padding: 1.4rem 1.2rem;
    }
    .sherpa-hero::after {
        display: none;
    }
    .sherpa-card {
        padding: 1rem;
    }
    .url-guide-card {
        padding: 1rem;
    }
    .diff-container {
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    active_model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    st.markdown(f"""
    <div style="background:#e0e7ff;border:1px solid #c7d2fe;border-radius:12px;padding:0.9rem;margin-bottom:1rem;">
      <div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;color:#4338ca;">Active Intelligence</div>
      <div style="font-size:0.92rem;font-weight:800;color:#1e1b4b;margin-top:0.2rem;">🤖 {active_model}</div>
      <div style="font-size:0.75rem;color:#6366f1;margin-top:0.2rem;">Open-weight &amp; zero data retention</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🧗 3-Step Guide")
    st.markdown("""
    1. **Find an open issue** on GitHub (filter by `good first issue`).
    2. **Paste the URL** into IssueSherpa.
    3. **Get your custom roadmap**, checklist, and draft pull request.
    """)

    st.divider()

    st.markdown("### 💡 Beginner Pro-Tips")
    st.markdown("""
    - Look for issues with **0 or 1 comment**.
    - Avoid issues already assigned to someone.
    - Ask clarifying questions before writing complex code!
    """)


# ── Main Header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sherpa-hero">
  <div class="hero-badge">🎃 Open Source &amp; Hacktoberfest Mentor</div>
  <h1 class="hero-title">IssueSherpa 🧗</h1>
  <p class="hero-subtitle">
    Turn any GitHub issue into a beginner-friendly, step-by-step contribution plan in seconds.
  </p>
</div>
""", unsafe_allow_html=True)


# ── URL Input & Educational Walkthrough Section ──────────────────────────────────
st.markdown("""
<div class="url-guide-card">
  <div class="url-guide-header">
    <span>📌 How to input a GitHub Issue URL</span>
  </div>
  <p style="font-size:0.86rem;color:#475569;margin:0 0 0.5rem 0;line-height:1.5;">
    IssueSherpa analyzes a <strong>specific task or bug</strong>, so it needs a link directly to an <strong>Issue</strong>, not just a repository home page.
  </p>

  <div class="url-anatomy">
    <span class="url-seg seg-base">https://github.com</span>
    <span class="url-seg seg-slash">/</span>
    <span class="url-seg seg-owner">{owner}</span>
    <span class="url-seg seg-slash">/</span>
    <span class="url-seg seg-repo">{repository}</span>
    <span class="url-seg seg-slash">/</span>
    <span class="url-seg seg-issues">issues</span>
    <span class="url-seg seg-slash">/</span>
    <span class="url-seg seg-num">{number}</span>
  </div>

  <div class="url-comparison">
    <div class="url-comp-bad">
      <strong style="color:#b91c1c;">❌ Incorrect (Repo URL):</strong><br>
      <code>https://github.com/psf/requests</code><br>
      <span style="font-size:0.75rem;color:#7f1d1d;">(Missing /issues/ and issue number)</span>
    </div>
    <div class="url-comp-good">
      <strong style="color:#15803d;">✅ Correct (Issue URL):</strong><br>
      <code>https://github.com/psf/requests/issues/6523</code><br>
      <span style="font-size:0.75rem;color:#14532d;">(Points to a specific task)</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Session state initialization
if "issue_url" not in st.session_state:
    st.session_state.issue_url = ""

# ── 1-Click Example Issues ──────────────────────────────────────────────────────
st.markdown('<div style="font-size:0.82rem;font-weight:700;color:#64748b;margin-bottom:0.4rem;text-transform:uppercase;">⚡ Quick test with popular repos:</div>', unsafe_allow_html=True)

ex_cols = st.columns(3)
with ex_cols[0]:
    if st.button("🐍 Python Algorithms #10017", use_container_width=True):
        st.session_state.issue_url = "https://github.com/the-algorithms/python/issues/10017"
        st.session_state.url_text_input = "https://github.com/the-algorithms/python/issues/10017"
        st.rerun()

with ex_cols[1]:
    if st.button("🌐 Requests Library #6523", use_container_width=True):
        st.session_state.issue_url = "https://github.com/psf/requests/issues/6523"
        st.session_state.url_text_input = "https://github.com/psf/requests/issues/6523"
        st.rerun()

with ex_cols[2]:
    if st.button("📚 Public APIs #4666", use_container_width=True):
        st.session_state.issue_url = "https://github.com/public-apis/public-apis/issues/4666"
        st.session_state.url_text_input = "https://github.com/public-apis/public-apis/issues/4666"
        st.rerun()


# ── Text Input ──────────────────────────────────────────────────────────────────
url_input = st.text_input(
    "Paste GitHub Issue URL here",
    value=st.session_state.issue_url,
    placeholder="https://github.com/owner/repository/issues/123",
    label_visibility="visible",
    key="url_text_input",
)
st.session_state.issue_url = url_input.strip()


# ── Live Validation & Guidance Feedback ─────────────────────────────────────────
is_valid_url = False
if st.session_state.issue_url:
    val = st.session_state.issue_url
    if re.match(r"^https?://github\.com/[^/]+/[^/]+/issues/\d+/?$", val):
        is_valid_url = True
        st.markdown('<div class="val-valid">✅ <strong>Valid Issue URL!</strong> Click the button below to generate your plan.</div>', unsafe_allow_html=True)
    elif re.match(r"^https?://github\.com/[^/]+/[^/]+/pull/\d+/?$", val):
        st.markdown('<div class="val-warning">⚠️ <strong>This is a Pull Request, not an Issue.</strong> Change <code>/pull/</code> to <code>/issues/</code> or select an issue to fix.</div>', unsafe_allow_html=True)
    elif re.match(r"^https?://github\.com/[^/]+/[^/]+/?$", val):
        st.markdown('<div class="val-warning">⚠️ <strong>This is a Repository Home Page.</strong> To get an issue URL: go to this repository on GitHub, click the <strong>"Issues"</strong> tab at the top, click any issue, and copy that link!</div>', unsafe_allow_html=True)
    elif re.match(r"^https?://github\.com/[^/]+/[^/]+/issues/?$", val):
        st.markdown('<div class="val-warning">⚠️ <strong>This is the list of all issues.</strong> Click on any individual issue title in that list, and copy its specific link.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="val-info">ℹ️ Expected format: <code>https://github.com/{owner}/{repo}/issues/{number}</code></div>', unsafe_allow_html=True)

st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

# Analyse button
analyze_btn = st.button("🧗 Analyse This Issue", type="primary", use_container_width=True)

st.markdown("<hr style='border:none;border-top:1px solid #e2e8f0;margin:1.8rem 0;'>", unsafe_allow_html=True)


# ── Cached GitHub Fetch ─────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def cached_fetch(owner: str, repo: str, issue_number: int) -> dict:
    return fetch_issue_context(owner, repo, issue_number)


# ── Execution Logic ─────────────────────────────────────────────────────────────
if analyze_btn:
    if not st.session_state.issue_url:
        st.warning("⚠️ Please paste a GitHub issue URL first or select one of the quick test buttons above.")
        st.stop()

    try:
        owner, repo, issue_number = parse_issue_url(st.session_state.issue_url)
    except ValueError as e:
        st.error(f"❌ {e}")
        st.stop()

    # Progress Indicator
    prog_placeholder = st.empty()
    prog_placeholder.info("🌐 1/3: Fetching repository context, README, guidelines & file tree from GitHub...")

    ctx: dict = {}
    try:
        ctx = cached_fetch(owner, repo, issue_number)
    except ValueError as e:
        prog_placeholder.empty()
        st.error(f"❌ GitHub API Error: {e}")
        st.stop()
    except Exception as e:
        prog_placeholder.empty()
        st.error(f"❌ Unexpected Error: {e}")
        st.stop()

    active_model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    prog_placeholder.info(f"🤖 2/3: {active_model} is crafting your step-by-step contribution plan...")

    # Run Pre-checks
    checks = run_pre_checks(ctx)

    # Call LLM
    plan: dict = {}
    try:
        plan = get_issue_plan(ctx)
    except ValueError as e:
        prog_placeholder.empty()
        st.error(f"⚠️ Could not complete AI reasoning: {e}")
        st.stop()
    except Exception as e:
        prog_placeholder.empty()
        st.error(f"⚠️ LLM Error: {e}")
        st.stop()

    # Anti-hallucination file path check
    verified_files = verify_file_paths(plan.get("likely_files", []), ctx.get("file_tree", []))
    prog_placeholder.empty()

    # ── Repo Overview Header ────────────────────────────────────────────────────
    rs = ctx.get("repo_stats", {})
    tech_stack = _detect_tech_stack(ctx.get("file_tree", []))
    age = _time_ago(ctx.get("created_at", ""))
    comment_count = ctx.get("comment_count", 0)
    issue_url = ctx.get("html_url", f"https://github.com/{owner}/{repo}/issues/{issue_number}")

    st.markdown(f"""
    <div class="sherpa-card" style="border-left: 6px solid #4f46e5;">
      <div style="font-size:0.75rem;font-weight:700;color:#6366f1;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.25rem;">
        {owner} / {repo} &nbsp;•&nbsp; Issue #{issue_number}
      </div>
      <h2 style="font-size:1.35rem;font-weight:800;color:#0f172a;margin:0 0 0.5rem 0;">
        {ctx.get('title','')}
      </h2>
      <a href="{issue_url}" target="_blank" style="display:inline-block;font-size:0.85rem;color:#4f46e5;font-weight:700;text-decoration:none;margin-bottom:0.8rem;">
        🔗 Open Issue on GitHub &nearr;
      </a>
      
      <div class="stats-grid">
        <div class="stat-box">
          <span class="stat-box-label">Stars</span>
          <span class="stat-box-val">⭐ {_fmt_num(rs.get('stars',0))}</span>
        </div>
        <div class="stat-box">
          <span class="stat-box-label">Forks</span>
          <span class="stat-box-val">🔀 {_fmt_num(rs.get('forks',0))}</span>
        </div>
        <div class="stat-box">
          <span class="stat-box-label">Open Issues</span>
          <span class="stat-box-val">🐛 {_fmt_num(rs.get('open_issues',0))}</span>
        </div>
        <div class="stat-box">
          <span class="stat-box-label">Comments</span>
          <span class="stat-box-val">💬 {comment_count}</span>
        </div>
        <div class="stat-box">
          <span class="stat-box-label">Opened</span>
          <span class="stat-box-val">🕒 {age}</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Tech stack detected
    if tech_stack:
        pills_html = "".join(f'<span class="tech-pill">{t}</span>' for t in tech_stack)
        st.markdown(f"""
        <div style="margin-bottom:1rem;">
          <span style="font-size:0.78rem;font-weight:700;color:#475569;text-transform:uppercase;">Detected Tech Stack:</span>
          <div class="tech-badge-container" style="margin-top:0.3rem;">{pills_html}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Pre-flight Checks ───────────────────────────────────────────────────────
    with st.expander("🔍 Issue Pre-flight Health Checks", expanded=True):
        for check in checks:
            icon = check.get("icon", "ℹ️")
            msg = check.get("message", "")
            ctype = check.get("type", "info")
            if ctype == "warning":
                st.markdown(f'<div class="val-warning">{icon} {msg}</div>', unsafe_allow_html=True)
            elif ctype == "success":
                st.markdown(f'<div class="val-valid">{icon} {msg}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="val-info">{icon} {msg}</div>', unsafe_allow_html=True)

    # ── Difficulty Assessment ───────────────────────────────────────────────────
    diff = plan.get("difficulty", "beginner").lower()
    diff_style = "diff-easy"
    diff_icon = "🟢"
    diff_label = "Beginner Friendly"
    diff_color = "#166534"

    if "intermediate" in diff or "medium" in diff:
        diff_style = "diff-med"
        diff_icon = "🟡"
        diff_label = "Intermediate"
        diff_color = "#854d0e"
    elif "advanced" in diff or "hard" in diff:
        diff_style = "diff-hard"
        diff_icon = "🔴"
        diff_label = "Advanced"
        diff_color = "#991b1b"

    st.markdown(f"""
    <div class="diff-container {diff_style}">
      <div style="font-size:2.4rem;line-height:1;">{diff_icon}</div>
      <div>
        <div style="font-size:1.15rem;font-weight:800;color:{diff_color};">
          {diff_label}
        </div>
        <div style="font-size:0.88rem;color:#334155;margin-top:0.2rem;">
          {plan.get('difficulty_reason', 'Great task for open source contributors.')}
        </div>
        <div style="font-size:0.82rem;font-weight:700;color:#475569;margin-top:0.3rem;">
          ⏱️ Estimated Time: {plan.get('estimated_time', '1-2 hours')}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── 6 Result Tabs ───────────────────────────────────────────────────────────
    tab_plan, tab_files, tab_check, tab_claim, tab_pr, tab_q = st.tabs([
        "🧭 Action Plan",
        "📂 Target Files",
        "✅ Guidelines",
        "💬 Claim Comment",
        "🔀 Draft PR",
        "❓ Clarifications",
    ])

    # Tab 1: Action Plan
    with tab_plan:
        st.markdown("### 🧭 Executive Summary")
        st.markdown(f"""
        <div style="background:#f8fafc;border-left:4px solid #6366f1;padding:1rem 1.2rem;border-radius:0 10px 10px 0;font-size:0.95rem;color:#1e293b;line-height:1.65;margin-bottom:1.5rem;">
          {plan.get('summary', 'No summary provided.')}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🪜 Step-by-Step Implementation")
        steps = plan.get("steps", [])
        if steps:
            for idx, s in enumerate(steps, 1):
                st.markdown(f"""
                <div class="step-item">
                  <div class="step-num">{idx}</div>
                  <div class="step-body">{s}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No explicit steps generated.")

    # Tab 2: Files to touch
    with tab_files:
        verified_count = sum(1 for f in verified_files if f.get("verified"))
        st.markdown(f"### 📂 Suggested Files to Modify ({verified_count}/{len(verified_files)} verified in repo)")
        if verified_files:
            for f in verified_files:
                is_v = f.get("verified", False)
                v_badge = "✅ Exists in repository" if is_v else "⚠️ Predicted file path (verify before editing)"
                v_color = "#15803d" if is_v else "#b45309"
                st.markdown(f"""
                <div class="file-card">
                  <div class="file-name">📄 {f.get('path')}</div>
                  <div class="file-desc">{f.get('reason')}</div>
                  <div style="font-size:0.75rem;font-weight:700;color:{v_color};margin-top:0.3rem;">{v_badge}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No specific files targeted by the model.")

    # Tab 3: Checklist
    with tab_check:
        st.markdown("### ✅ Contributor Checklist")
        checklist = plan.get("contributing_checklist", [])
        if checklist:
            for item in checklist:
                st.checkbox(item, value=False)
        else:
            st.info("No checklist items generated.")

    # Tab 4: Claim Comment
    with tab_claim:
        st.markdown("### 💬 Ready-to-post Claim Comment")
        st.caption("Post this comment on the GitHub issue before you start coding to claim it politely.")
        claim_comment = plan.get("claim_comment", "Hi maintainers! I would love to work on this issue. Could you please assign it to me?")
        st.code(claim_comment, language=None)
        st.link_button("🚀 Go to GitHub to Post Claim Comment", issue_url)

    # Tab 5: Draft Pull Request
    with tab_pr:
        st.markdown("### 🔀 Ready-to-use Pull Request")
        st.caption("When your code is tested and pushed, copy these into your GitHub PR.")
        pr_title = plan.get("pr_title", f"fix: solve issue #{issue_number}")
        pr_desc = plan.get("pr_description", f"Resolves #{issue_number}")

        st.markdown("**PR Title:**")
        st.code(pr_title, language=None)

        st.markdown("**PR Description (Markdown):**")
        st.code(pr_desc, language="markdown")

    # Tab 6: Questions for Maintainers
    with tab_q:
        st.markdown("### ❓ Clarifying Questions for Maintainers")
        st.caption("Asking smart questions early prevents wasted effort and proves you understand the codebase.")
        questions = plan.get("questions_to_ask_maintainer", [])
        if questions:
            for q in questions:
                st.markdown(f"- ❓ **{q}**")
        else:
            st.success("🎉 This issue is very well-specified! You can begin right away.")

    # ── Export & Reset Action Bar ───────────────────────────────────────────────
    st.markdown("<hr style='border:none;border-top:1px solid #e2e8f0;margin:2rem 0 1rem 0;'>", unsafe_allow_html=True)
    down_col, reset_col = st.columns(2)
    with down_col:
        md_content = format_markdown_export(ctx, plan, verified_files)
        st.download_button(
            label="📥 Download Plan (.md)",
            data=md_content,
            file_name=f"IssueSherpa_{owner}_{repo}_{issue_number}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with reset_col:
        if st.button("🔄 Analyse Another Issue", use_container_width=True):
            st.session_state.issue_url = ""
            st.session_state.url_text_input = ""
            st.rerun()

else:
    # ── Clean Default Landing Card ─────────────────────────────────────────────
    st.markdown("""
    <div style="background:#ffffff;border-radius:18px;border:1px solid #e2e8f0;padding:2.5rem 1.5rem;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,0.03);margin-top:1rem;">
      <div style="font-size:3.5rem;margin-bottom:0.8rem;">🏔️</div>
      <h3 style="font-size:1.35rem;font-weight:800;color:#0f172a;margin-bottom:0.4rem;">
        Your Open-Source Contribution Guide
      </h3>
      <p style="font-size:0.92rem;color:#64748b;max-width:560px;margin:0 auto 1.5rem auto;line-height:1.6;">
        Paste any public GitHub issue URL above or click one of the quick test buttons to see how IssueSherpa breaks down complex tasks into beginner-friendly milestones.
      </p>
      <div style="display:inline-flex;flex-wrap:wrap;gap:0.75rem;justify-content:center;font-size:0.82rem;font-weight:600;color:#4f46e5;">
        <span style="background:#f1f5f9;padding:0.35rem 0.75rem;border-radius:9999px;">⚡ Instant Pre-checks</span>
        <span style="background:#f1f5f9;padding:0.35rem 0.75rem;border-radius:9999px;">🛡️ Anti-Hallucination Verified</span>
        <span style="background:#f1f5f9;padding:0.35rem 0.75rem;border-radius:9999px;">🔒 No Data Retention</span>
      </div>
    </div>
    """, unsafe_allow_html=True)
