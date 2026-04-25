# Shadow

> Watch your desktop. Learn your patterns. Forge them into agents.

Shadow is an open-source, local-first desktop companion that quietly observes
how you work, detects the tasks you repeat, and turns them into runnable
agents with the help of Claude. Think of it as a personal
workflow-to-agent pipeline that runs entirely on your machine.

**Why:** most automation tools make the user describe a workflow up front.
Shadow flips the model — it learns from what you're already doing, then offers
to take it off your plate.

---

## What it does today (v1.0)

**Core:**
- Cross-platform capture of app focus and window titles (macOS, Windows, Linux, plus a generic fallback).
- Local SQLite storage — nothing leaves your machine by default.
- Pattern detection across sessions with edit-distance clustering (near-duplicate patterns merge).
- Per-pattern confidence scoring combining frequency, recency, and consistency.
- Multi-provider intent extraction: Claude, OpenAI, OpenClaw, Ollama, or local transformer models.
- A built-in web dashboard at `http://127.0.0.1:4747` with searchable event log, pattern filters, pin/archive, and tabbed views (Events/Patterns/Agents/Scheduler/Marketplace/Settings).
- Dry-run agent executor that previews each step before anything is actually done.

**Automation & Integration:**
- Scheduler with cron expressions and event-based triggers, plus run history.
- API adapters for Gmail, Slack, Linear, Notion (prefer APIs over GUI automation).
- On-device NER redaction for sensitive values (emails, phones, SSNs, credit cards, IPs).
- Per-app privacy policies (JSON-configurable).

**Agents & Extensibility:**
- Sample agent library with 6 templates: file-triage, meeting-note-router, daily-standup-prep, email-followup, tab-cleanup, expense-logger.
- Agent marketplace to discover, install, and share agent templates.
- Native Tauri desktop app for macOS, Windows, and Linux (in `/tauri` directory).

## What's coming (roadmap)

- [ ] Browser extension for richer web capture (DOM targets + URLs).
- [ ] AT-SPI2 integration on Linux for full accessibility-tree targets.
- [ ] Playwright backend for live browser replay.
- [ ] Community plugin system for custom adapters and agents.
- [ ] Enterprise features (team sync, SSO, RBAC).

See `docs/ROADMAP.md` for the full plan and how to pick up work.

---

## Install and run

### From source

```bash
git clone https://github.com/Peidong-Wang/shadow
cd shadow
python -m venv .venv && source .venv/bin/activate

# Core + all providers, adapters, and agents
pip install -e ".[all-providers,all-adapters]"

# Or pick specific extras:
pip install -e ".[core]"                    # core only
pip install -e ".[all-providers]"           # Claude, OpenAI, OpenClaw, Ollama, local models
pip install -e ".[local]"                   # local ML (no API keys)
pip install -e ".[all-adapters]"            # Gmail, Slack, Linear, Notion
pip install -e ".[agents]"                  # sample templates + marketplace
```

### Start it up

```bash
# Start capture + dashboard (opens your browser automatically)
shadow

# Or just the dashboard
shadow dashboard

# Headless capture
shadow capture

# One-shot pattern detection over existing data
shadow detect
```

The dashboard lives at `http://127.0.0.1:4747`.

### Desktop App (Tauri)

Instead of running via the command line, you can build Shadow as a native desktop application for macOS, Windows, or Linux:

```bash
cd tauri
npm install
npm run tauri build
```

The compiled app will be in `src-tauri/target/release/bundle/`. See `tauri/README.md` for full build instructions and platform-specific prerequisites.

**Why Tauri?** It wraps the Python dashboard in a lightweight native window (~30-50MB vs 150MB+ for Electron), with better performance and zero additional runtime dependencies.

### Enable Claude intent extraction

```bash
export ANTHROPIC_API_KEY=sk-ant-...
shadow   # patterns can now be lifted into structured agent specs
```

Without a key, Shadow generates a best-effort offline spec.

---

## How it works

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Capture    │ ───▶ │   Storage    │ ───▶ │   Patterns   │ ───▶ │    Intent    │
│  (per-OS)    │      │  (SQLite)    │      │ (clustering) │      │ (multi-LLM)  │
└──────────────┘      └──────────────┘      └──────┬───────┘      └──────┬───────┘
                           │                        │                      │
                           │                    Confidence             Privacy
                           │                    Scoring               (Redaction)
                           │                        │                      │
                           ▼                        ▼                      ▼
                        ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
                        │   Adapters   │      │  Dashboard   │      │  Scheduler   │
                        │ (Gmail,Slack,│      │ (searchable, │      │ (cron +      │
                        │  Linear,etc) │      │  filterable) │      │  triggers)   │
                        └──────┬───────┘      └──────────────┘      └──────┬───────┘
                               │                                           │
                               └───────────────────┬──────────────────────┘
                                                   │
                                                   ▼
                                        ┌──────────────────────┐
                                        │   Agent Library      │
                                        │ + Marketplace        │
                                        │ (6 templates, share) │
                                        └──────┬───────────────┘
                                               │
                                               ▼
                                        ┌──────────────────────┐
                                        │   Runtime Executor   │
                                        │ (dry-run + Tauri app)│
                                        └──────────────────────┘
```

1. **Capture** (`shadow/capture/`) — per-OS backends yield `Event` objects over a polling loop. macOS uses AppKit/Quartz, Windows uses the Win32 API, Linux uses xdotool/wmctrl, with a `psutil`-based fallback.
2. **Storage** (`shadow/storage/`) — one SQLite file in the platform-appropriate data dir. Session segmentation based on idle gaps. Raw keystrokes are **never** stored.
3. **Patterns** (`shadow/patterns/`) — edit-distance clustering merges near-duplicate patterns. Configurable n-gram frequency, min length, and occurrence thresholds.
4. **Confidence** (`shadow/patterns/`) — per-pattern scoring based on frequency, recency, and consistency.
5. **Intent** (`shadow/intent/`) — multi-provider intent extraction. Claude, OpenAI, OpenClaw, Ollama, or local transformer models. Anonymized pattern sent with a structured-output prompt. Returns an `AgentSpec` (name, summary, trigger, steps, inputs).
6. **Privacy** (`shadow/privacy/`) — on-device NER redacts sensitive values (emails, phones, SSNs, credit cards, IPs) before any API call. Per-app configurable policies.
7. **Adapters** (`shadow/adapters/`) — Gmail, Slack, Linear, Notion API integrations. Preferred over GUI automation.
8. **Dashboard** (`shadow/dashboard/`) — searchable event log, pattern filters, pin/archive, tabbed views for Events, Patterns, Agents, Scheduler, Marketplace, Settings.
9. **Scheduler** (`shadow/scheduler/`) — cron-style + event-triggered agent execution with run history.
10. **Agents** (`shadow/agents/`) — sample library of 6 templates (file-triage, meeting-note-router, daily-standup-prep, email-followup, tab-cleanup, expense-logger) and marketplace for sharing.
11. **Runtime** (`shadow/runtime/`) — dry-run executor walks each step and describes what it would do. Live execution is opt-in. Tauri desktop app wraps the Python backend for a native installable UI.

Full architecture deep-dive: `docs/ARCHITECTURE.md`.

---

## Multi-Provider Intent Extraction

Shadow supports multiple LLM backends for turning patterns into agents. Pick the one that suits you best:

```bash
# Use Claude (default)
export ANTHROPIC_API_KEY=sk-ant-...

# Or OpenAI
export OPENAI_API_KEY=sk-...

# Or Ollama (local)
export OLLAMA_MODEL=mistral
ollama serve  # in another terminal

# Or a local transformer model
pip install -e ".[local]"

# Or OpenClaw
export OPENCLAW_API_KEY=...
```

Each provider returns the same `AgentSpec` structure, so you can mix and match without rewriting agents.

---

## Adapters

Shadow ships with API-first adapters to reach common SaaS platforms without brittle GUI automation:

- **Gmail** — read, send, archive emails programmatically.
- **Slack** — send/update messages, list channels, manage reminders.
- **Linear** — create/update issues, move tasks across cycles.
- **Notion** — read/write database entries, manage pages.

Build your own adapter by subclassing `shadow.adapters.BaseAdapter` and registering it in the adapter registry.

---

## Privacy & On-Device Redaction

Shadow is built around five rules. Read them in full at `docs/PRIVACY.md`:

1. **Local-first.** Everything is stored in an SQLite file on your machine.
2. **No raw keystrokes.** The capture layer records app/window/URL — never what you typed.
3. **On-device NER redaction.** Before any API call, sensitive values (emails, phones, SSNs, credit cards, IPs) are detected and hashed locally.
4. **Per-app privacy policies.** JSON-configurable rules let you decide what data each app can see.
5. **Explicit intent extraction.** Pattern → LLM only happens when you click **Extract intent**. The payload is shown in the dashboard before it's sent.
6. **Dry-run by default.** Agents preview every step. Live execution is an explicit toggle.

---

## Agent Library & Marketplace

Shadow ships with a curated library of 6 sample agent templates:

- **file-triage** — detect repeated file management tasks and automate them.
- **meeting-note-router** — extract action items from meeting notes and route them to Slack/Linear.
- **daily-standup-prep** — compile recent activity and open issues each morning.
- **email-followup** — remind you of unanswered emails or flag overdue responses.
- **tab-cleanup** — organize and close old browser tabs on a schedule.
- **expense-logger** — detect receipt forwarding and auto-log expenses.

Discover, install, and share agent templates via the **Marketplace** tab in the dashboard. Every agent is a portable JSON spec that you can fork, customize, and contribute back.

---

## Native Tauri Desktop App

Shadow includes a native desktop app built with Tauri (~30-50MB, lightweight and fast):

```bash
cd tauri
npm install
npm run tauri dev      # development
npm run tauri build    # release bundle
```

The app is available for macOS, Windows, and Linux. Signed installers are coming soon.

**Why Tauri?** It bundles the Python dashboard in a lightweight native window with better UX than running `shadow` from the command line. No Electron bloat, no heavy runtime.

---

## Contributing

We welcome contributions of any size — especially for the per-OS capture backends and the Playwright runtime. See `CONTRIBUTING.md` to get started. Pick up anything marked `good first issue` or help shape the roadmap.

Project principles:

- **Local-first, always.** If a feature sends data off the box by default, it needs a very good reason.
- **Graceful degradation.** Accessibility APIs fail often — always fall back to a coarser signal instead of crashing.
- **Boring tech for the core.** Stdlib where possible. Heavy deps live behind optional extras.
- **Everything is a contract.** The `Event`, `Pattern`, and `AgentSpec` shapes are the seams between modules.

---

## License

MIT — see `LICENSE`.
