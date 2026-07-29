# Marketplace submission draft — Share Chat

Staged assets for the a0-plugins index PR. **Do not submit while the repo is private** —
the raw screenshot URLs below will 404 until the repo is flipped public.

## `plugins/share_chat/index.yaml`

```yaml
title: Share Chat
description: >-
  One-click sharing for Agent Zero conversations. Adds a share button to the
  chat top bar that copies a deep link to the current chat — paste it anywhere
  and Agent Zero opens straight to that conversation. Entirely client-side:
  no backend, no storage, no tokens. Confirms with a green check and
  auto-resets. Recipients still need access to your instance — the link is a
  pointer, not a bypass.
github: https://github.com/agent-zero-plugins/agent-zero-plugin-share-chat
tags:
  - workflow
  - tools
  - integration
screenshots:
  - https://raw.githubusercontent.com/agent-zero-plugins/agent-zero-plugin-share-chat/main/docs/screenshot-idle.png
  - https://raw.githubusercontent.com/agent-zero-plugins/agent-zero-plugin-share-chat/main/docs/screenshot-copied.png
```

- Description length: ~430 chars (< 500 ✓)
- Tags: 3 (≤ 5 ✓), from TAGS.md
- Title: 10 chars (≤ 50 ✓)

## Thumbnail

Copy `usr/plugins/share_chat/webui/thumbnail.png` (256×256 square, ~3.3 KB < 20 KB ✓)
to `plugins/share_chat/thumbnail.png` in the index PR.

## Pre-submission checklist (flip-time)

- [ ] Repo public (screenshot URLs resolve)
- [ ] `plugin.yaml` at expected path with `name: share_chat` (matches index folder, `^[a-z0-9_]+$` ✓)
- [ ] `LICENSE` present at repo root (full Apache-2.0 ✓)
- [ ] `plugin-e2e` green on the submitted commit
- [ ] One plugin per PR; only `index.yaml` + `thumbnail.png` in the index folder
