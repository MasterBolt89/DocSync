# DocSync

> Keep your docs aligned with your code.

DocSync analyzes public GitHub repositories and detects outdated, conflicting, or inaccurate documentation by extracting claims from Markdown/RST documents and comparing them against the actual source code and configuration.

Built for the **Best Use of Gemma 4** hackathon challenge.

---

## 🚀 Features

- **Public Repository Scanning**: Validates repository URLs and retrieves source trees via the GitHub REST API without requiring git clone.
- **Deterministic Check Engine**:
  - **Removed / Renamed Symbols**: Flags deprecated functions, renamed classes, and moved methods with suggested replacements.
  - **Signature Mismatches**: Catches incorrect argument counts, missing required parameters, and unexpected keyword arguments.
  - **Config Drift**: Detects obsolete environment variables and config keys removed from the codebase.
  - **Conflicting Docs**: Catches contradictory values or defaults documented across different files.
  - **Outdated Install Commands**: Compares `pip install` / `npm install` packages against package manifests (`pyproject.toml`, `package.json`).
- **Gemma 4 Semantic Auditing**:
  - Semantic consistency analysis distinguishing harmless differences from real bugs.
  - Generates clear explanations and suggested documentation fixes.
  - Size-bounded context prompts preventing token overflow.
- **Byte-Exact Finding Validation**:
  - Verifies file references, line numbers, and quoted code excerpts against repository files.
  - Rejects hallucinated line numbers or non-existent files.
  - Generates direct clickable GitHub links to exact lines.
- **Standalone Demo Mode**:
  - Pre-bundled with an authentic repository fixture (`demo-org/awesome-cache-lib`).
  - Runs 100% offline without any API keys or GitHub rate limits.

---

## 🛠️ Architecture

```
DocSync/
├── backend/                  # FastAPI Application (Python 3.10+)
│   ├── app/
│   │   ├── api/routes.py     # Endpoints: /api/analyze, /api/config-status, /api/health
│   │   ├── core/config.py    # Environment settings & limits
│   │   ├── models/schemas.py # Pydantic schemas (Finding, CodeFact, DocClaim)
│   │   ├── services/
│   │   │   ├── github_client.py # GitHub tree & blob fetcher
│   │   │   ├── parser.py        # AST fact extractor & doc claim extractor
│   │   │   ├── checker.py       # Deterministic consistency checks
│   │   │   ├── gemma_client.py  # Gemma 4 client (AI Studio & OpenAI endpoints)
│   │   │   ├── ai_analyzer.py   # AI prompt builder & finding validator
│   │   │   ├── analyzer.py      # Pipeline orchestrator & cross-source dedup
│   │   │   └── demo.py          # Offline sample repository fixture
│   │   └── main.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # React 18 + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.tsx
│   │   │   ├── LandingPage.tsx
│   │   │   └── Dashboard.tsx
│   │   ├── utils/api.ts
│   │   └── index.css         # Dark developer-tool design system
│   └── package.json
└── .env.example              # Root template for environment variables
```

---

## ⚡ Quick Start

### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Configure Gemma 4 & GitHub credentials
cp .env.example .env
# Edit .env with your Gemma API credentials (see below)

# Start backend server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend API will be available at `http://127.0.0.1:8000`. You can test health at `http://127.0.0.1:8000/api/health`.

### 2. Frontend Setup

In a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 🔑 Where to Enter Gemma 4 Credentials

To enable live Gemma 4 AI semantic auditing, configure `backend/.env`:

```bash
# Full URL to your Gemma 4 endpoint
# Example for Google AI Studio:
# GEMMA_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemma-4-it:generateContent
# Example for OpenAI-compatible endpoint (vLLM / Ollama / Groq / LiteLLM):
# GEMMA_API_URL=https://your-host/v1/chat/completions
GEMMA_API_URL=https://your-endpoint-here

# Your API Key
GEMMA_API_KEY=your-api-key-here

# Optional: Model identifier (if required by endpoint)
GEMMA_MODEL=gemma-4-it

# Optional: GitHub token to raise public API rate limit from 60 to 5,000 req/hr
GITHUB_TOKEN=
```

> **Note**: If Gemma credentials are not provided, DocSync continues to function seamlessly with full deterministic checks and offline demo mode.

---

## 🧪 Testing

### Run Backend Verification Tests
```bash
source backend/.venv/bin/activate
python -c "
import asyncio
from app.services.analyzer import run_demo_analysis
res = asyncio.run(run_demo_analysis())
print(f'Demo test passed with {res.total_findings} findings!')
"
```

### Build Frontend
```bash
cd frontend
npm run build
```

---

## 🔒 Security & Reliability

- **No Code Execution**: Repository files are parsed statically via Python AST and regex. Code is never evaluated or executed.
- **Untrusted Input Handling**: Repository contents are treated as untrusted data; size and file count limits protect against resource exhaustion.
- **Credential Protection**: API keys and tokens are loaded strictly on the backend and are never sent to the browser or leaked in logs or error traces.
