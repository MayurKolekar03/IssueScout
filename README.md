# IssueScout 🧭

> **Turn any GitHub issue into a clear, beginner-friendly action plan — powered by an open-weight LLM.**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-ff4b4b)](https://streamlit.io)

---

## 📸 Overview

<!-- Replace with an actual screenshot after first run -->
![IssueScout Screenshot](screenshot.png)

---

## 🤔 Why does IssueScout exist?

Every open-source contributor has opened a GitHub issue and asked:

- *"Where do I even start?"*
- *"Which file should I edit?"*
- *"What does this label mean?"*
- *"Will I break something?"*

IssueScout answers all of these questions automatically. You paste an issue URL; it fetches the issue context, the README, the CONTRIBUTING guidelines, and the repo's file tree — then an **open-weight LLM** produces a plain-English roadmap tailored to that specific issue.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔍 Issue analysis | Title, body, labels, comments, open/closed state |
| 📖 Repo context | README + CONTRIBUTING guidelines (truncated) |
| 🗂️ File tree scan | Filtered repository file tree |
| 🚦 Pre-checks | Closed? Assigned? Already claimed in comments? |
| 🤖 Open-weight LLM | Powered by open-weight models via OpenAI-compatible API |
| 🛡️ Anti-hallucination | Every suggested file is verified against the real repository |
| 📋 Action plan | Summary, steps, checklist, draft PR, claim comment, and questions |
| 📥 Export | Download complete plan as Markdown (.md) |

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
utils.py ──► Pre-checks (instant, no LLM)
  • Closed? Assigned? Claimed in comments?
  • Good labels?
      │
      ▼
llm.py ──► Open-weight LLM (via OpenAI-compatible API)
  • Structured prompt with repository context
  • JSON schema response, robustly parsed
  • Automatic retry on malformed JSON
      │
      ▼
utils.verify_file_paths() ──► Anti-hallucination
  Every "likely_file" checked against real repo tree
      │
      ▼
app.py ──► Streamlit UI
  Renders plan in clean, responsive tabs with copy buttons
```

---

## 🚀 Quick Start (local)

### 1. Clone & install

```bash
git clone https://github.com/your-org/issuescout.git
cd issuescout

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
| `LLM_BASE_URL` | ✅ | `https://api.groq.com/openai/v1` | OpenAI-compatible base URL |
| `LLM_API_KEY` | ✅ | — | API key for the LLM provider |
| `LLM_MODEL` | ✅ | `openai/gpt-oss-120b` | Model name to request |
| `GITHUB_TOKEN` | ⚠️ recommended | — | Personal access token (no scopes needed for public repos). Rate limit: 60 req/hr without token, 5,000 req/hr with token. |

---

## 🔀 Switching LLM providers

### Groq (fast, free tier)

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your Groq key>
LLM_MODEL=openai/gpt-oss-120b
```

### Ollama (fully local, free)

```bash
ollama pull llama3.2
ollama serve
```

```env
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2
```

### DigitalOcean Serverless Inference

```env
LLM_BASE_URL=https://inference.do-ai.run/v1
LLM_API_KEY=<your DO GenAI key>
LLM_MODEL=llama3.3-70b-instruct
```

---

## 🧪 Testing

Run the automated test suite:

```bash
python -m unittest test_suite.py
```

---

## 🐳 Docker Deployment

```bash
docker build -t issuescout .
docker run -p 8501:8501 \
  -e LLM_BASE_URL=https://api.groq.com/openai/v1 \
  -e LLM_API_KEY=your_key \
  -e LLM_MODEL=openai/gpt-oss-120b \
  -e GITHUB_TOKEN=your_github_token \
  issuescout
```

Open [http://localhost:8501](http://localhost:8501).

---

## ☁️ Cloud Deployment

### Option A: Streamlit Community Cloud (Free)
1. Push this repo to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io).
3. Select your repository and `app.py`.
4. Under **Advanced Settings**, paste your `.env` variables into Secrets.
5. Click **Deploy**.

### Option B: Render / Railway / DigitalOcean App Platform
1. Connect your repository.
2. The platform automatically detects the provided `Dockerfile` or `Procfile`.
3. Set your environment variables in the dashboard.
4. Deploy — IssueScout handles dynamic cloud `$PORT` automatically.

---

## 📄 License

MIT — see [LICENSE](LICENSE).
