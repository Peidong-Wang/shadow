# Roadmap

## v0.1 — Foundation (✅ shipped)

- [x] Per-OS capture (macOS, Windows, Linux, generic fallback).
- [x] Local SQLite storage with session segmentation.
- [x] N-gram pattern detection.
- [x] Claude intent extraction with a structured `AgentSpec` output.
- [x] Zero-dep web dashboard.
- [x] Dry-run executor.

## v0.2 — The "actually useful" milestone (✅ shipped)

- [x] Edit-distance clustering so near-duplicate patterns merge into one.
- [x] Per-pattern "confidence score" combining frequency, recency, and consistency.
- [x] Dashboard UX: searchable event log, pattern filters, pin/archive, tabbed views.
- [ ] Browser extension for Chromium + Firefox yielding rich DOM-level events.
- [ ] AT-SPI2 on Linux for full accessibility-tree capture under GNOME/KDE.
- [ ] Playwright-based live executor for browser-centric agents.

## v0.3 — The "stays running" milestone (✅ shipped)

- [x] Scheduler (cron + event-triggered) with a run history log.
- [x] API-first adapters for Gmail, Slack, Linear, Notion (prefer APIs over GUI automation).
- [x] Tauri-based desktop app shell so the project is installable as a real app, not `python -m`.
- [ ] Signed installers for macOS, Windows, Linux.
- [ ] First-run walkthrough and privacy onboarding.

## v0.4 — Local intelligence (✅ shipped)

- [x] Multi-provider intent extraction: Claude, OpenAI, OpenClaw, Ollama, local transformers.
- [x] On-device NER to redact sensitive values before any outbound call.
- [x] Per-app privacy policies users can edit declaratively.

## v1.0 — Ready for real users (✅ shipped)

- [x] Sample agent library with 6 templates (file-triage, meeting-note-router, daily-standup-prep, email-followup, tab-cleanup, expense-logger).
- [x] Curated agent marketplace for discovering, installing, and sharing templates.
- [x] Tauri desktop app with native installers.

## v1.1+ — Community & Enterprise (in planning)

- [ ] Browser extension for richer web capture (DOM targets + URLs).
- [ ] Community plugin system for custom adapters and agents.
- [ ] Advanced scheduler UI with more trigger types and template management.
- [ ] Improved agent library with more templates submitted by community.
- [ ] Team collaboration features (shared agents, audit logs, team sync).
- [ ] Enterprise features: SSO integration, RBAC, centralized audit logs.
- [ ] Signed and notarized installers for all platforms.
- [ ] Prompt templates and customization UI for agent behavior tuning.

## How to help

Every line item above is an invitation. Good starting points:

- **Adapters:** Pick a SaaS platform you'd use and build an adapter for it.
- **Agents:** Design new sample templates or contribute your own to the marketplace.
- **Capture:** Port the generic capture fallback or improve existing per-OS backends.
- **UX:** Help shape the dashboard, onboarding, or privacy settings UI.
- **Docs:** Expand architecture docs, write tutorials, or share your use cases.

File an issue or open a discussion on GitHub to discuss your ideas. The roadmap is community-driven.
