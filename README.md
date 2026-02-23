# WebAPT — Web Application Access & Analysis Toolkit

WebAPT is an AI-powered tool that audits web applications for **accessibility**, **application structure**, and **QA quality** using a multi-agent pipeline. It generates detailed Markdown reports and exports them as polished PDFs.

This branch (`feature/webapp`) extends the base CLI with **AppLens** — a full Flask web interface for managing and monitoring audit tasks through a browser.

---

## What's New in This Branch

| Feature | Description |
|---------|-------------|
| 🌐 **AppLens Web UI** | Browser-based dashboard to submit and track audit tasks |
| 👤 **User Authentication** | Login/logout with session management |
| 🗂️ **Task Queue** | Submit tasks, monitor progress, view results — all from the browser |
| 👑 **Admin Panel** | Create users, view all tasks, manage the queue |
| ⚡ **Live Updates** | Real-time task status via Server-Sent Events (SSE) |
| 📥 **Download Reports** | Download PDFs and screenshots directly from the UI |
| 🔒 **Credential Redaction** | Passwords in task inputs are automatically redacted from display |

---

## Features (Full)

- 🔍 **Accessibility Agent** — checks WCAG compliance, contrast, keyboard navigation, ARIA labels, and more
- 🧠 **Application Analyzer Agent** — maps routes, UI structure, and application behaviour
- ✅ **QA Verifier Agent** — cross-validates findings and produces a final QA report
- 📄 **PDF Export** — converts all Markdown reports to PDF via WeasyPrint (screenshots embedded)
- 🖥️ **Headed / Headless** — Playwright-powered browser, switchable at runtime
- 🔌 **Dual provider support** — LiteLLM proxy (Azure GPT-4.1) or Google Gemini

---

## Installation

```bash
# Clone and switch to this branch
git clone https://github.com/Sam-2552/Accessibility-Checker.git
cd Accessibility-Checker
git checkout feature/webapp

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install the webapt core package
pip install -e .

# Install webapp dependencies
pip install -r webapp/requirements.txt

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

# Flask
FLASK_SECRET_KEY=your-secret-key-here
```

---

## Running AppLens (Web UI)

```bash
cd webapp

# Development
python app.py

# Production (Gunicorn)
gunicorn -w 1 -b 0.0.0.0:5000 app:app
```

Open `http://localhost:5000` in your browser.

> **Note:** Use `-w 1` (single worker) — the background task queue is in-process and not safe for multiple Gunicorn workers.

### First Run

On first launch, a default admin account is created automatically:

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin` |

**Change the admin password immediately after first login.**

---

## Web UI Overview

### Dashboard (`/dashboard`)
- Submit new audit tasks with a URL and optional login credentials
- View your task queue with live status updates
- Cancel pending or running tasks

### Task Detail (`/task/<id>`)
- Live log streaming as the task runs
- Download generated PDFs and screenshots
- View the full file tree of outputs

### Admin Panel (`/admin`)
- Create and manage user accounts
- View all tasks across all users
- Monitor system queue

---

## CLI Usage (also available)

The full CLI is still available alongside the web UI:

```bash
# Interactive mode
webapt --project my_audit

# Full pipeline (non-interactive)
webapt --project my_audit --task "audit https://example.com"

# Single agent
webapt --project my_audit --agent accessibility --task "check https://example.com"
webapt --project my_audit --agent analysis    --task "analyse https://example.com"

# PDF conversion only
webapt --project my_audit --convert-pdf

# Headed browser
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

## Tech Stack

| Layer | Technology |
|-------|------------|
| AI Agents | Strands Agents (LiteLLM / Gemini) |
| Browser Automation | Playwright (Chromium) |
| Web UI | Flask + Gunicorn |
| Database | SQLite |
| PDF Generation | WeasyPrint + Markdown |
| Live Updates | Server-Sent Events (SSE) |

---

## Requirements

- Python ≥ 3.11
- Playwright (Chromium)
- WeasyPrint system dependencies — see [WeasyPrint docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html)

---

## License

MIT
