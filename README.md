# WebAPT — Web Application Access & Analysis Toolkit

WebAPT is an AI-powered CLI tool that audits web applications for **accessibility**, **application structure**, and **QA quality** using a multi-agent pipeline. It generates detailed Markdown reports and exports them as polished PDFs.

---

## Features

- 🔍 **Accessibility Agent** — checks WCAG compliance, contrast, keyboard navigation, ARIA labels, and more
- 🧠 **Application Analyzer Agent** — maps routes, UI structure, and application behaviour
- ✅ **QA Verifier Agent** — cross-validates findings and produces a final QA report
- 📄 **PDF Export** — converts all Markdown reports to PDF via WeasyPrint (screenshots included)
- 🖥️ **Headed / Headless** — Playwright-powered browser, switchable at runtime
- 🔌 **Dual provider support** — LiteLLM proxy (Azure GPT-4.1) or Google Gemini

---

## Installation

```bash
# Clone the repo
git clone https://github.com/Sam-2552/Accessibility-Checker.git
cd Accessibility-Checker

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install the package
pip install -e .

# (Optional) Gemini provider support
pip install -e ".[gemini]"

# Install Playwright browsers
playwright install chromium
```

---

## Configuration

Copy `.env.template` to `.env` and fill in your values:

```bash
cp .env.template .env
```

```env
# Provider: "litellm" or "gemini"
MODEL_PROVIDER=litellm

# LiteLLM proxy
LITELLM_V_KEY=your_api_key
LITELLM_BASE_URL=https://your-proxy.example.com/
LITELLM_MODEL_ID=azure/gpt-4.1

# Gemini (alternative)
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL_ID=gemini-2.0-flash

# Project defaults
WEBAPT_PROJECT=web_analysis
WEBAPT_OUTPUT_ROOT=./outputs
WEBAPT_HEADLESS=true
```

---

## Usage

### Interactive mode

```bash
webapt --project my_audit
```

```
webapt> https://example.com — check full accessibility and structure
webapt> accessibility https://example.com
webapt> analysis https://example.com
webapt> qa
webapt> pdf
webapt> exit
```

### Non-interactive (single run)

```bash
# Full pipeline
webapt --project my_audit --task "audit https://example.com"

# Single agent
webapt --project my_audit --agent accessibility --task "check https://example.com"
webapt --project my_audit --agent analysis    --task "analyse https://example.com"

# PDF conversion only (no agent run)
webapt --project my_audit --convert-pdf

# Skip PDF after run
webapt --project my_audit --task "audit https://example.com" --no-pdf

# Headed browser (visible)
webapt --project my_audit --task "..." --headed
```

---

## Output Structure

```
outputs/
└── <project>/
    ├── accessibility_reports/   # Per-page accessibility Markdown reports
    ├── analysis_reports/        # Application analysis Markdown report
    ├── screenshots/             # Browser screenshots (PNG)
    ├── pdf/                     # Generated PDFs (with screenshots embedded)
    └── qa_report.md             # Final QA verification report
```

---

## Agents

| Agent | Description |
|-------|-------------|
| `accessibility` | Scans each page for WCAG issues, contrast problems, missing ARIA roles, keyboard traps |
| `analysis` | Maps the application's routes, components, forms, and user flows |
| `qa` | Reviews all reports, cross-checks findings, and produces a final verification summary |

---

## Requirements

- Python ≥ 3.11
- Playwright (Chromium)
- WeasyPrint (and its system dependencies — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html))

---

## License

MIT
