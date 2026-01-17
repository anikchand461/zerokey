<div align="center">

# zerokey

**Unified API Key Management for Developers**  
Securely store, manage, rotate, and call **multiple AI/LLM API keys** (OpenAI, Anthropic, Groq, Gemini, and more) from one place — with zero plaintext leaks and unified interface.

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CLI on PyPI](https://img.shields.io/pypi/v/zerokey-cli?label=zerokey-cli&logo=pypi)](https://pypi.org/project/zerokey-cli/) <!-- update when published -->

</div>

## The Problem Developers Face Every Day

Juggling **10–50+ API keys** across providers is painful:

- Scattered `.env` files everywhere → easy to commit by mistake to Git
- Plaintext keys on disk → security nightmare
- Different API signatures → constant code changes when switching providers
- No visibility into usage → surprise bills, no idea which key is burning tokens
- Hard to rotate or expire keys → manual, error-prone process

**ZeroKey solves all of this** — one secure vault, one unified interface, beautiful CLI + web dashboard, **zero vendor lock-in**.

## Key Features

- **AES-256 client-side encryption** — keys never touch the server in plaintext
- **Local-first & self-hosted** — runs on localhost (or your own server), no cloud forced
- **Unified proxy** — call any provider with the same format (`/proxy/u/<provider>/<slug>`)
- **CLI power tool** (`zerokey`): add, list, delete, call, stats — with **Rich** beautiful tables, sparklines & panels
- **Modern Vue.js + Vite dashboard** — visual vault, real-time usage graphs, quick actions
- **Automatic provider detection** (e.g. `sk-` → OpenAI)
- **Built-in usage tracking** — tokens used, latency, status codes, errors — per key/provider
- **Expiration & rotation reminders** — set dates, never forget to rotate
- **Flexible auth** — JWT (username/password) + OAuth (GitHub / GitLab)
- **Normalized responses** — consistent output across OpenAI, Groq, Anthropic, Gemini…
- **Pure Python CLI** — install via `pipx install zerokey-cli`, works everywhere (macOS/Linux/Windows)

## Architecture

```
zerokey/
├── backend/          # FastAPI server (auth, vault, proxy, usage)
├── frontend/         # frontend on valinna js , HTML and css
├── zerokey_cli/      # Typer + Rich CLI (published as zerokey-cli on PyPI)
├── Dockerfile        # Easy containerization
└── ... (pyproject.toml, requirements.txt, etc.)
```

- Database: **SQLite** (simple & local) — PostgreSQL support planned
- Encryption: **AES-256** at rest (client-side)
- Auth: **Argon2** password hashing + **JWT** (short-lived)
- Proxy: Normalizes requests/responses + retries + logging

## Quick Start

### 1. CLI (recommended for daily use)

```bash
# Install CLI (once published – for now: pip install -e zerokey_cli/)
pipx install zerokey-cli    # or from source

zerokey login               # OAuth or username/password
zerokey add-key             # Add your OpenAI / Groq / etc. key
zerokey ls                  # Beautiful table of all keys
zerokey call gpt-4o "Hello world"   # Test call using unified key
zerokey stats               # Usage overview with sparklines
```

### 2. Full stack (backend + dashboard)

```bash
# Run backend
cd backend
poetry install          # or pip install -r ../requirements.txt
uvicorn main:app --reload

# In another terminal - dashboard
cd ../frontend
npm install
npm run dev             # opens http://localhost:5173
```

Default: backend on `http://localhost:8000`, frontend proxies to it.

## Security Highlights

- Keys encrypted **client-side** before ever hitting the database
- No plaintext in logs, memory, or disk
- Short-lived JWTs + secure OAuth flows
- Strict input validation (Pydantic)
- Security headers & CORS in FastAPI
- Designed with **zero-trust** principles

## Who Is This For?

- ML/AI engineers juggling multiple LLM providers
- Competitive programmers using many judge APIs
- Indie hackers & solo devs tired of `.env` chaos
- Anyone who wants **usage visibility** and **safe key rotation**

## Roadmap (2026 Goals)

- More providers (easy plugin system)
- Team sharing & basic RBAC
- Export/backup/import keys
- AI-powered anomaly detection
- PostgreSQL + better scaling
- Full e2e tests

## License

[MIT License](LICENSE) — free to use, modify, distribute.

---

Built with ❤️ by **[Anik Chand](https://github.com/anikchand461)** and **[Abhiraj Adhikary](https://github.com/abhirajadhikary06)**
**ZeroKey** — because your keys deserve better than a `.env` file.

