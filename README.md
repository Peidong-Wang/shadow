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

## What it does today (v0.1)

-  Cross-platform capture of app focus and window titles (macOS, Windows, Linux, plus a generic fallback).
-  Local SQLite storage — nothing leaves your machine by default.
-  Pattern detection across sessions (n-gram frequency over event signatures).
-  Claude-powered intent extraction — turns a repeated sequence into a structured `AgentSpec` in JSON.
-  A built-in web dashboard at `http://127.0.0.1:4747` with zero runtime dependencies.
-  Dry-run agent executor that previews each step before anything is actually done.

## What it will do (roadmap)

- [ ] Browser extension for richer web capture (DOM targets + URLs).
- [ ] AT-SPI2 integration on Linux for full accessibility-tree targets.
- [ ] Edit-distance clustering so near-duplicate patterns merge.
- [ ] Playwright backend for live browser replay.
- [ ] Tauri shell for a proper installable desktop app (replaces `python -m shadow`).
- [ ] Local-only ML for intent extraction (no API key required).
- [ ] Scheduler UI — cron-style + event-triggered agent runs.

See `docs/ROADMAP.md` for the full plan and how to pick up work.

---

## Install and run

### From source

```bash
git clone https://github.com/peidong-wang/shadow
cd shadow
python -m venv .venv && source .venv/bin/activate
pip install -e ".[intent]"                  # core + Claude integration
# Optional per-OS extras:
pip install -e ".[macos]"                   # macOS capture
pip install -e ".[windows]"                 # Windows capture
pip install -e ".[generic]"                 # cross-platform fallback
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
│  (per-OS)    │      │  (SQLite)    │      │ (n-gram freq)│      │  (Claude)    │
└──────────────┘      └──────────────┘      └──────────────┘      └──────┬───────┘
                                                                         │
                                                                         ▼
                                                                 ┌──────────────┐
                                                                 │   Runtime    │
                                                                 │ (dry-run +   │
                                                                 │  Playwright) │
                                                                 └──────────────┘
```

1. **Capture** (`shadow/capture/`) — per-OS backends yield `Event` objects over a polling loop. macOS uses AppKit/Quartz, Windows uses the Win32 API, Linux uses xdotool/wmctrl, with a `psutil`-based fallback.
2. **Storage** (`shadow/storage/`) — one SQLite file in the platform-appropriate data dir. Session segmentation based on idle gaps. Raw keystrokes are **never** stored.
3. **Patterns** (`shadow/patterns/`) — sliding n-gram frequency counter over event signatures. Configurable min length and occurrence thresholds.
4. **Intent** (`shadow/intent/`) — anonymized pattern sent to Claude with a structured-output prompt. Returns an `AgentSpec` (name, summary, trigger, steps, inputs).
5. **Runtime** (`shadow/runtime/`) — dry-run executor walks each step and describes what it would do. Live execution is opt-in and currently limited to browser navigation.

Full architecture deep-dive: `docs/ARCHITECTURE.md`.

---

## Privacy

Shadow is built around five rules. Read them in full at `docs/PRIVACY.md`:

1. **Local-first.** Everything is stored in an SQLite file on your machine.
2. **No raw keystrokes.** The capture layer records app/window/URL — never what you typed.
3. **Hashed sensitive values.** Form values and similar strings are SHA-256 hashed before storage.
4. **Explicit Claude calls.** Pattern → Claude only happens when you click **Extract intent**. The payload is shown in the dashboard before it's sent.
5. **Dry-run by default.** Agents preview every step. Live execution is an explicit toggle.

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
