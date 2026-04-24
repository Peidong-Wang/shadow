# Architecture

Shadow is five layers that communicate through two small data contracts: `Event` and `AgentSpec`.

```
┌──────────┐   Event   ┌──────────┐   Event   ┌──────────┐   Pattern    ┌──────────┐   AgentSpec   ┌──────────┐
│ Capture  │ ────────▶ │ Storage  │ ────────▶ │ Patterns │ ──────────▶  │  Intent  │ ────────────▶ │ Runtime  │
└──────────┘           └──────────┘           └──────────┘              └──────────┘               └──────────┘
    per-OS               SQLite                  n-grams                   Claude                   dry-run /
    daemon                                                                                         live exec
```

## Contracts

### `Event` (`shadow.storage.Event`)

Canonical capture unit. Every backend emits these; the store persists them verbatim.

```python
@dataclass
class Event:
    ts: float
    event_type: str          # "app_focus", "window_change", "navigate", ...
    app: str | None
    window_title: str | None
    url: str | None
    target_element: str | None
    value_hash: str | None   # SHA-256[:16], never the raw value
    extra: dict
    session_id: int | None
```

### `AgentSpec` (`shadow.intent.AgentSpec`)

Normalized, executable description of a learned workflow. Lives in the DB alongside the pattern that produced it.

```python
@dataclass
class AgentSpec:
    name: str                       # kebab-case id
    summary: str                    # one-line English summary
    trigger: str                    # "weekdays at 9am", "when user opens Gmail", ...
    steps: list[dict]               # [{action, target, args}, ...]
    inputs: list[dict]              # inputs the agent needs when triggered
    notes: str
```

## Why local-first

Three reasons:

1. **Trust.** Users hand us their entire desktop activity. Anything else is a nonstarter.
2. **Latency.** Pattern detection over months of data needs to be a local index, not a round-trip.
3. **Compliance.** An enterprise-ready version ships the same day as the consumer one if we never built in a cloud dependency.

The single concession: we do call out to Claude on explicit user action to lift a pattern into a generalized agent spec. That payload is:

- One pattern's event sequence (signatures only — app names, event types, generic targets).
- One concrete example with window titles for context.
- Never raw values, never keystrokes, never file contents.

## Platform capture strategy

| Platform | Library       | Signal quality  | Notes                                                                     |
|----------|---------------|-----------------|---------------------------------------------------------------------------|
| macOS    | AppKit/Quartz | High            | Requires Accessibility permission. Fallback to `pygetwindow` + `psutil`.  |
| Windows  | pywin32       | High            | No special permission needed. Fallback to `pygetwindow` + `psutil`.       |
| Linux    | xdotool/wmctrl| Medium          | Full AT-SPI2 support is on the roadmap for richer DOM-like tree capture.  |
| Any      | pygetwindow   | Low (app focus) | Pure-python fallback. Enough to seed pattern detection.                    |

All backends share the same interface (`CaptureBackend.poll() -> list[Event]`) and the same session-segmentation logic in `Capture`.

## Pattern detection (v0.1)

Given all events in all recent sessions, for each n in `[min_len..max_len]`:

1. Slide an n-window across each session's event-signature sequence.
2. Count occurrences across all sessions.
3. Any n-gram that appears ≥ `min_pattern_occurrences` times becomes a candidate `Pattern`.

This is intentionally dumb-simple and exact-match — it ships reliable signal while we build the more sophisticated edit-distance clustering in v0.2.

A "signature" concatenates `event_type | app | target_element` so two clicks on the same button in the same app look identical, while the exact window title or URL (which are noisy) are ignored.

## Intent extraction

The prompt is deliberately tight and asks for a single JSON object. The model sees:

- How many times the pattern was seen.
- The ordered step summary (event type, app, generic target).
- One concrete example with window titles and URLs for grounding.

It returns an `AgentSpec`. The dashboard renders it, the user approves, and only then does the runtime touch it.

## Runtime

v0.1 is **dry-run only**. Every handler in `AgentExecutor` prints what it would do rather than actually doing it. The only "live" action is opening a URL via `webbrowser` when the user explicitly passes `live=True`.

Future live adapters:

- **Browser:** Playwright, driven by `navigate`/`click`/`type` steps with real selectors.
- **Desktop GUI:** `pyautogui` + per-OS accessibility APIs for element-level targeting.
- **APIs:** First-class adapters (Gmail, Slack, Linear, Notion) preferred over GUI automation whenever the destination has an API.

## Extension points

- **New capture backend:** implement `CaptureBackend` in `shadow/capture/<platform>.py`.
- **New pattern algorithm:** subclass `PatternDetector` and override `detect()`.
- **New intent backend:** drop in a different class with the same public shape as `IntentExtractor`. The dashboard only knows the `.extract(pattern)` method.
- **New runtime handler:** add a method to `AgentExecutor._handlers` keyed by the action name.
