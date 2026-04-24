# Contributing to Shadow

Thanks for your interest! Shadow is an ambitious cross-platform project
and we genuinely need help in every layer. This guide is short — if
anything is unclear, open an issue.

## Ways to contribute

- **Per-OS capture backends.** If you run Windows, macOS, or Linux as your
  daily driver, you can probably make one of these backends noticeably better.
- **Pattern detection.** Edit-distance clustering, time-aware weighting,
  per-app heuristics — lots of room here.
- **Runtime adapters.** Playwright for browsers, `pyautogui` for desktop,
  direct API adapters for popular SaaS tools (Gmail, Slack, Notion, ...).
- **Docs + examples.** Real-world "I automated X" write-ups are gold.
- **Polishing the dashboard.** It's intentionally minimal right now.

## Setup

```bash
git clone https://github.com/peidong-wang/shadow
cd shadow
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,intent]"
pytest
```

## Project layout

```
shadow/
├── capture/        # per-OS event capture
├── storage/        # SQLite event store
├── patterns/       # offline pattern detection
├── intent/         # Claude-powered intent extraction
├── runtime/        # agent executor (dry-run / live)
├── dashboard/      # zero-dep HTTP server + HTML UI
├── config.py       # single source of truth for runtime settings
├── __main__.py     # CLI entry point
└── __init__.py
```

## Coding style

- Line length 100, Ruff-formatted. Run `ruff check --fix` before pushing.
- Type hints on all public surfaces. `from __future__ import annotations` in every file.
- Keep dependency footprint small. Heavy deps (pywin32, pyobjc, anthropic) are optional extras.
- Never log or persist raw user input. If you must record a value, hash it via `shadow.storage.db.hash_value`.

## Tests

`pytest` should stay green. For capture backends, prefer a smoke test that
imports cleanly on every platform — full validation is best done manually
on the target OS.

## PR checklist

- [ ] Tests pass (`pytest`)
- [ ] Lints clean (`ruff check .`)
- [ ] No secrets, credentials, or personal data in examples or tests
- [ ] README / docs updated if behavior changed
- [ ] New deps landed behind an optional extra, not in the base install

## Good first issues

- Add a "clear database" button to the dashboard (already has a modal; wire it to an API route).
- Move the pattern detector from exact-match n-grams to edit-distance clustering.
- Add a "rename session" UI in the dashboard, with a POST route on the server.
- Add a packaged-binary build for macOS/Windows via PyInstaller.

## Code of conduct

Be kind. Assume good faith. This is a tool a lot of people will entrust
with their desktop activity — bring that level of care to reviews too.
