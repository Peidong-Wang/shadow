# Roadmap

## v0.1 — Today (✅ shipped)

- Per-OS capture (macOS, Windows, Linux, generic fallback).
- Local SQLite storage with session segmentation.
- N-gram pattern detection.
- Claude intent extraction with a structured `AgentSpec` output.
- Zero-dep web dashboard.
- Dry-run executor.

## v0.2 — The "actually useful" milestone

- [ ] Edit-distance clustering so near-duplicate patterns merge into one.
- [ ] Browser extension for Chromium + Firefox yielding rich DOM-level events.
- [ ] AT-SPI2 on Linux for full accessibility-tree capture under GNOME/KDE.
- [ ] Playwright-based live executor for browser-centric agents.
- [ ] Per-pattern "confidence score" combining frequency, recency, and consistency.
- [ ] Dashboard UX: searchable event log, pattern filters, pin/archive.

## v0.3 — The "stays running" milestone

- [ ] Scheduler (cron + event-triggered) with a run history log.
- [ ] API-first adapters for Gmail, Slack, Linear, Notion (prefer APIs over GUI automation).
- [ ] Tauri-based desktop app shell so the project is installable as a real app, not `python -m`.
- [ ] Signed installers for macOS, Windows, Linux.
- [ ] First-run walkthrough and privacy onboarding.

## v0.4 — Local intelligence

- [ ] Local-only intent extraction (small model) so Claude is optional.
- [ ] On-device NER to redact sensitive values before any outbound call.
- [ ] Per-app privacy policies users can edit declaratively.

## v1.0 — Ready for real users

- [ ] Extensive sample agent library (file triage, meeting-note routing, recurring SaaS chores).
- [ ] A curated OSS marketplace of shareable, portable agent specs.
- [ ] Enterprise opt-in team-sync layer with SSO and RBAC.

## How to help

Every line item above is an invitation. Good starting points:

- Pick an adapter you'd use yourself and ship it — the first API integrations unlock the most real-world value.
- Port the generic capture fallback to your OS — we'd rather have three imperfect backends than one perfect one.
- Try Shadow on your own workflows and file issues when a pattern you expected to be discovered was missed.
