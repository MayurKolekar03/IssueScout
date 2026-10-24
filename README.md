# IssueSherpa 🧗

> **Turn any GitHub issue into a clear, beginner-friendly action plan — powered by an open-weight LLM.**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b)](https://streamlit.io)

---

## 📸 Screenshot

<!-- Replace with an actual screenshot after first run -->
![IssueSherpa Screenshot](screenshot.png)

---

## 🤔 Why does IssueSherpa exist?

Every Hacktoberfest season, thousands of developers open a GitHub issue and freeze:

- *"Where do I even start?"*
- *"Which file should I edit?"*
- *"What does this label mean?"*
- *"Will I break something?"*

IssueSherpa answers all of these questions automatically. You paste a URL; it reads the issue, the README, the CONTRIBUTING guide, and the repo's file tree — then an **open-weight LLM** produces a plain-English plan tailored to that specific issue.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Issue analysis | Title, body, labels, comments, state |
| 📖 Repo context | README + CONTRIBUTING (truncated) |
| 🗂️ File tree scan | Filtered, capped at 400 paths |
| 🚦 Pre-checks | Closed? Assigned? Already claimed? |
| 🤖 Open-weight LLM | Llama 3.3 70B by default |
| 🛡️ Anti-hallucination | Every suggested file verified against real tree |
| 📋 Action plan | Summary, steps, checklist, draft PR, claim comment |
| 📥 Export | Download full plan as Markdown |

---

## 🔄 How it works

```
User pastes URL
      │
      ▼
github_client.py ──► GitHub REST API
  • Issue metadata
  • First 10 comments
  • README (≤6000 chars)
  • CONTRIBUTING.md (≤4000 chars)
  • File tree (≤400 paths, filtered)
      │
      ▼
utils.py ──► Pre-checks (no LLM)
  • Closed? Assigned? Claimed in comments?
  • Good labels?
      │
      ▼
llm.py ──► Open-weight LLM (via OpenAI-compatible API)
  • Single structured prompt
  • JSON response, robustly parsed
  • Retry on bad JSON
      │
      ▼
utils.verify_file_paths() ──► Anti-hallucination
  Every "likely_file" checked against real tree
      │
      ▼
app.py ──► Streamlit UI
  Renders plan in expandable sections
```

---

## 🚀 Quick Start (local)

### 1. Clone & install

```bash
git clone https://github.com/your-org/issuesherpa.git
cd issuesherpa

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Run

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_BASE_URL` | ✅ | `https://inference.do-ai.run/v1` | OpenAI-compatible base URL |
| `LLM_API_KEY` | ✅ | — | API key for the LLM provider |
| `LLM_MODEL` | ✅ | `llama3.3-70b-instruct` | Model name to request |
| `GITHUB_TOKEN` | ⚠️ recommended | — | Fine-grained PAT (no scopes needed for public repos). Without it, rate limit is 60 req/hr. |

---

## 🔀 Switching LLM providers

### DigitalOcean Serverless Inference (default)

```env
LLM_BASE_URL=https://inference.do-ai.run/v1
LLM_API_KEY=<your DO GenAI key>
LLM_MODEL=llama3.3-70b-instruct
```

Get your key at [cloud.digitalocean.com/gen-ai](https://cloud.digitalocean.com/gen-ai).

### Ollama (fully local, free)

```bash
# Install Ollama: https://ollama.com
ollama pull llama3.2
ollama serve   # starts on port 11434
```

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2
```

### Groq (fast, free tier)

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your Groq key>
LLM_MODEL=llama-3.3-70b-versatile
```

### Together.ai / Fireworks / any OpenAI-compatible provider

Just swap the three env vars — no code changes needed.

---

## 🐳 Docker

```bash
docker build -t issuesherpa .
docker run -p 8080:8080 \
  -e LLM_BASE_URL=https://inference.do-ai.run/v1 \
  -e LLM_API_KEY=your_key \
  -e LLM_MODEL=llama3.3-70b-instruct \
  -e GITHUB_TOKEN=your_github_token \
  issuesherpa
```

Open [http://localhost:8080](http://localhost:8080).

---

## ☁️ Deploy on DigitalOcean App Platform

1. Push this repo to GitHub.
2. Go to [cloud.digitalocean.com/apps](https://cloud.digitalocean.com/apps) → **Create App**.
3. Connect your GitHub repo.
4. DigitalOcean auto-detects the `Dockerfile`.
5. Set environment variables under **App → Settings → App-Level Environment Variables**:
   - `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `GITHUB_TOKEN`
6. Set **HTTP Port** to `8080`.
7. Deploy. IssueSherpa is live in ~2 minutes.

> **Tip:** Use DigitalOcean's own [serverless inference](https://docs.digitalocean.com/products/gen-ai/reference/inference/) — no external API key needed, billed per token.

---

## 🤖 The Open-Weight Model

**Default: Llama 3.3 70B Instruct** (Meta, Apache 2.0 license)

Why Llama 3.3?
- State-of-the-art reasoning in the open-weight category
- Instruction-following is reliable enough for structured JSON output
- Available on DigitalOcean, Ollama, Groq, Together.ai, and more
- No vendor lock-in — swap to any model that fits an OpenAI-compatible API

---

## ⚠️ Known Limitations

1. **Private repos** — GitHub token must have `repo` scope; CONTRIBUTING and README may still be inaccessible.
2. **Large file trees** — capped at 400 paths; very large monorepos may miss some files.
3. **LLM hallucinations** — all suggested file paths are verified against the real tree and flagged, but step content is not verified.
4. **Token context** — prompt is truncated at ~12k tokens; very long issues or READMEs are cut.
5. **Rate limits** — without a `GITHUB_TOKEN` you get 60 API calls/hour. Each analysis uses ~5 calls.
6. **Model quality variance** — smaller models (e.g., `llama3.2:3b`) produce weaker plans. Use 70B for best results.

---

## 🤝 Contributing

1. Fork → branch → PR.
2. Keep `app.py` under 350 lines — add new modules instead.
3. Add a test in `tests/` if fixing a bug.
4. Follow existing docstring style (one-line summary, blank line, details).

---

## 📄 License

MIT — see [LICENSE](LICENSE).
