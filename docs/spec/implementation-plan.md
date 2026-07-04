# share-chat — Implementation plan

How the product is built internally (the *product* counterpart to `e2e-steps-spec.md`). Behaviour lives
in `behaviour-spec.md`; the executable contract in `e2e.feature.md`.

## Components

| Component | Path | Responsibility |
|---|---|---|
| Share button (the whole plugin) | `usr/plugins/share_chat/extensions/webui/chat-top-end/share-chat.html` | An Alpine `x-data` island injected at the `chat-top-end` extension point. Renders one button and owns all behaviour + styling. |
| Manifest | `plugin.yaml` / `meta.yaml` | `name: share_chat`, UI-only, `env: []`, no config. |

There are **no** tools, API handlers, hooks, settings, or persisted state — the plugin is a single
front-end extension.

## Internals

- **State (one Alpine scope):** `{ copied: false, shareChat() }`. The `copied` flag drives the confirmation.
- **Link composition (`shareChat`):** read `globalThis.getContext()`; if falsy, return (no-op). Else take
  `window.location.href`, **clear all query params** (`url.search = ''`), set only `ctxid=<context id>`,
  and use the resulting string. This makes the link origin+path based (no auth/session leakage) and
  re-selects the chat when opened.
- **Copy:** `await navigator.clipboard.writeText(link)`; on rejection (non-secure context) fall back to a
  hidden `<textarea>` + `document.execCommand('copy')`. Either path sets `copied = true`.
- **Confirmation:** `copied` toggles the icon `share → check`, adds `.share-copied` (green accent), and
  swaps the title to "Link copied!"; a `setTimeout(..., 2000)` resets it. Rapid clicks: the last click's
  timer governs the reset.

## Configuration & dependencies

None. Upstream-compatible — uses only stock A0 surfaces: the `chat-top-end` webui extension point and the
chat-context model (`globalThis.getContext`). No `@extensible` fork seam; no e2e seam (there is no
agent-driven behaviour — the user clicks the button directly).
