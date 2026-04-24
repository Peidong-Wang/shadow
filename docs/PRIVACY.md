# Privacy

Shadow observes your desktop. That imposes an unusually high bar on what we do with the data. This document spells out the rules and how we enforce them.

## The five rules

1. **Local-first by default.** Every event lives in one SQLite file in your platform's data directory (`~/Library/Application Support/shadow/shadow.db` on macOS, `%APPDATA%\shadow\shadow.db` on Windows, `~/.local/share/shadow/shadow.db` on Linux). We do not upload anything to any server.

2. **No raw keystrokes.** The capture layer does not install keyloggers. It observes application focus changes, window title changes, and (when you enable the browser extension) URLs and DOM element targets. What you type into those elements is never recorded.

3. **Hashed sensitive values.** When a future capture path needs to remember *that* a value was entered (for pattern matching) but not *what* it was, we store a truncated SHA-256 hash via `shadow.storage.db.hash_value`. You can audit this with one grep.

4. **Explicit Claude calls.** Nothing is sent to Claude automatically. Claude calls happen only when you click **Extract intent** on a specific pattern in the dashboard. The payload is deterministic — it's the signatures you can see in the UI plus one concrete example — and the model returns a generalized workflow spec, not raw data.

5. **Dry-run by default.** Learned agents do not run unprompted. The first "execution" of any learned agent is a dry-run that prints each step. Live execution is an explicit opt-in with a clear confirmation.

## What Shadow does record

- Application focus changes (process name, window title).
- Window title changes within an app.
- Browser URL (if the browser extension is installed — not shipped in v0.1).
- Timestamps.

## What Shadow never records

- Keystrokes.
- Clipboard contents.
- File contents.
- Screenshots.
- Microphone, webcam, or any biometric data.
- Network traffic.

## What leaves your machine

- When you click **Extract intent**: one pattern's worth of event signatures and up to one example event's window titles / URL.
- When you open the dashboard: nothing — the dashboard is served from localhost.
- When you install updates via pip: the usual pip telemetry, which is out of our control.

## Enterprise and teams

The architecture is compatible with an opt-in sync layer for teams that want to share discovered workflows. This is not shipped in v0.1 and would land behind explicit per-org configuration.

## Reporting a privacy issue

If you find a place where Shadow is recording something that violates these rules, please open a GitHub issue tagged `privacy` or email the maintainers.
