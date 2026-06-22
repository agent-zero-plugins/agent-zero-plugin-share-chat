# Behaviour & UI Specification — `agent-zero-plugin-share-chat` (reverse-engineered, after-the-fact)

**Plugin:** `share_chat` · **Version:** 0.1.0 · **Author:** Interu · **License:** Apache-2.0
**Source inspected:** `usr/plugins/share_chat/` (plugin.yaml, meta.yaml, default_config.yaml, `__init__.py`, `extensions/webui/chat-top-end/share-chat.html`, `webui/thumbnail.png`, `webui/.gitkeep`), `tests/e2e/behaviour.mjs`.
**Live A0 cross-reference:** `/a0/webui/components/chat/top-section/chat-top.html`, `/a0/webui/js/extensions.js`, `/a0/webui/index.js`, `/a0/webui/components/sidebar/chats/chats-store.js`.
**Document status:** Descriptive (documents shipped behaviour as-built); RFC-2119 keywords describe observed contract, not aspirational requirements.

> **Self-review note (scope correction).** The task brief anticipated `api/`, `hooks.py`, `prompts/`, `skills/`, `extensions/python/` (incl. `_functions` `@extensible` fork seams), and a `config.html` config screen. **None of these exist in this plugin.** This is verified, not an omission: the plugin ships exactly one functional artifact — a single declarative HTML extension — plus manifests. Sections that would document those surfaces are retained below as **explicit negative requirements** (NEG-*) so the absence is traceable and verifiable rather than silently dropped.

---

## 1. Overview

The plugin injects one circular icon button ("share") into the top bar of the chat area. Clicking it composes a deep link to the currently-open conversation (`<origin><path>?ctxid=<current-context-id>`), copies that link to the clipboard, and shows a transient confirmation (icon → check, green tint, title → "Link copied!") that auto-reverts after ~2000 ms. There is no backend, no persisted state, and no configuration.

The deep link is consumed by **upstream A0** (not by this plugin): on load, `chats-store.init()` reads `?ctxid=`, strips it from the URL, and selects that chat. The plugin only **produces** the link; the **consume** half is a pre-existing A0 capability the plugin piggybacks on.

---

## 2. User-facing behaviours

| ID | Behaviour | Trigger | Observable result | Source / verification |
|----|-----------|---------|-------------------|------------------------|
| **BEH-1** | Share button is injected into the chat top bar | Page load; A0 async-loads HTML extensions for the `chat-top-end` point via `/api/load_webui_extensions` (filters `*.html`) and replaces `<x-extension id="chat-top-end">.innerHTML` | A `.share-chat-btn` element appears at the right end of `#time-date-container`, after the project selector | `extensions.js: importHtmlExtensions`; `chat-top.html` host; e2e step 1/1a |
| **BEH-2** | Button shows the "share" icon in its idle state | Default render (`copied === false`) | `<span class="material-symbols-outlined">` renders text `share` at 0.7 opacity | `share-chat.html` `x-text="copied ? 'check':'share'"`; e2e "share" assertion |
| **BEH-3** | Hover affordance | Pointer over button | Background/border lighten, box-shadow appears, icon opacity → 1.0 (CSS `:hover` only; no JS) | `share-chat.html` `<style>` |
| **BEH-4** | Compose deep link for current chat | Click | `url = new URL(location.href)`; `url.search=""` (all existing query params dropped); `url.searchParams.set('ctxid', getContext())`; `link = url.toString()` | `share-chat.html: shareChat()` |
| **BEH-5** | Copy link to clipboard (primary path) | Click in a secure context where `navigator.clipboard` is available | `await navigator.clipboard.writeText(link)`; on success → BEH-7 | `share-chat.html` try-branch |
| **BEH-6** | Copy link to clipboard (fallback path) | Click when `navigator.clipboard.writeText` throws (e.g. non-HTTPS/insecure context, denied permission) | Off-screen `<textarea>` (fixed, opacity 0) created, value set, selected, `document.execCommand('copy')`, element removed; then → BEH-7 | `share-chat.html` catch-branch |
| **BEH-7** | Show "copied" confirmation state | Successful copy via BEH-5 **or** BEH-6 | `copied=true` → button gains `.share-copied` (green-tinted border/bg), icon swaps to `check` colored `#4caf50`, `title` → "Link copied!" | `share-chat.html` `:class`, `x-text`, `:title`; e2e best-effort step 2 |
| **BEH-8** | Auto-reset confirmation | ~2000 ms after BEH-7 | `setTimeout(()=>copied=false, 2000)` reverts icon/class/title to idle (BEH-2) | `share-chat.html` `setTimeout` |
| **BEH-9** | No-op when no chat context is selected | Click while `getContext()` returns falsy | `shareChat()` returns immediately; no clipboard write, no state change, no error | `share-chat.html` `if (!ctxid) return` |
| **BEH-10** | Idle tooltip | Pointer rest on idle button | `title` = "Copy link to this chat" | `share-chat.html` `:title` |
| **BEH-11** | Deep-link consumption (upstream, not plugin code) | Opening a URL carrying `?ctxid=<id>` | A0 `chats-store.init()` reads `ctxid`, removes it from the URL via `history.replaceState`, and calls `selectChat(ctxid)` to open that conversation | `/a0/webui/components/sidebar/chats/chats-store.js` lines 35–43 — **upstream A0**, documented to make the produced link's meaning verifiable |

---

## 3. Injected UI components

| ID | Component | Injection point / location | Selector | Renders / does | Source |
|----|-----------|----------------------------|----------|----------------|--------|
| **UI-1** | Share button (root) | `chat-top-end` extension point → inside `<x-extension id="chat-top-end">` in `#time-date-container`, positioned after `project-selector` | `.share-chat-btn` (idle); `.share-chat-btn.share-copied` (confirmed). Note: **no `data-testid`** — selection is by class, consistent with core A0 having no test ids | 32×32 circular button; click → BEH-4..8; `:title` bound to copied state | `share-chat.html`; host `chat-top.html` |
| **UI-2** | Icon glyph | Inside UI-1, wrapped in `.share-chat-icon` | `.share-chat-btn .material-symbols-outlined` | Material Symbol; text `share` ⇄ `check`, color empty ⇄ `#4caf50`, opacity 0.7 ⇄ 1.0 on hover | `share-chat.html` |
| **UI-3** | Alpine local state scope | Wrapper `<div x-data="{copied, shareChat()}">` enclosing UI-1 | (no stable selector) | Holds the only state: `copied:boolean`; owns `shareChat()` | `share-chat.html` |

**UI selector note (self-review C-2):** the e2e test asserts `x-extension#chat-top-end .share-chat-btn` to prove correct injection region; downstream consumers SHOULD use `.share-chat-btn` (idle) / `.share-copied` (confirmed) / the bound `title` text rather than positional selectors, since the component carries no `data-testid` and A0 core does not either.

---

## 4. Configuration screen

| ID | Statement |
|----|-----------|
| **CFG-1** | The plugin has **no configuration screen and no controls.** `webui/` contains only `thumbnail.png` (Store tile image) and `.gitkeep`; there is **no `config.html`**. `default_config.yaml` explicitly declares no options. `plugin.yaml` sets `per_project_config: false`, `per_agent_config: false`. Therefore A0 computes `has_config_screen = false`; the Plugin Store row exposes only the enable/disable toggle (and the thumbnail), and the config-panel open path (`openConfig → loadProjects → _hasProject`) is never reachable for this plugin. |
| **CFG-2** | `always_enabled: false` — the plugin is opt-in; the button (UI-1) appears only after a user enables `share_chat` in the Plugin Store. |

---

## 5. Backend / API surface & A0 extension points

| ID | Statement | Upstream vs fork |
|----|-----------|------------------|
| **API-1** | The plugin ships **no API handler, no Python hooks, no tools.** `__init__.py` is a docstring only; there is no `api/`, `hooks.py`, `prompts/`, `skills/`, or `extensions/python/`. `meta.yaml: env: []` (no operator-injected env vars / secrets). | n/a |
| **EXT-1** | **HTML extension point `chat-top-end`** — the plugin's sole integration. The file path `extensions/webui/chat-top-end/share-chat.html` maps to the `<x-extension id="chat-top-end">` declared in **upstream** `chat-top.html`. A0's `importHtmlExtensions()` discovers it via `/api/load_webui_extensions` (filter `*.html`), wraps it as an `<x-component>`, caches it (`frontend_extensions_html(extensions)(plugins)`), and injects it. | **Upstream-native** A0 seam — **not** an `@extensible` fork seam |
| **EXT-2** | **`globalThis.getContext()`** — returns A0's current `context` (the active chat/context id). The plugin reads it via optional chaining (`globalThis.getContext?.()`) to build the deep link. | **Upstream-native** global (`/a0/webui/index.js:599`) |
| **EXT-3** | **`?ctxid=` deep-link convention** — the link the plugin produces is consumed by upstream `chats-store.init()`. The plugin depends on this contract but contributes no code to it. | **Upstream-native** A0 behaviour |
| **NEG-1** | **No `@extensible` / `_functions` fork seam dependency.** The plugin uses only upstream-native injection (`x-extension`) and the upstream `getContext` global. It does **not** require the A0 fork's `@extensible` decorator points or `_functions` Python override hooks. This matters operationally: `share_chat` runs on **stock upstream A0**, not only on the fork. | Confirms upstream-only |

---

## 6. State & persistence

| ID | Statement |
|----|-----------|
| **ST-1** | The only state is the Alpine-local `copied:boolean` (UI-3), scoped to the component instance. |
| **ST-2** | **Nothing is persisted.** No localStorage, no sessionStorage, no server write, no cookie. `copied` is volatile and resets on auto-timeout (BEH-8) or page reload. |
| **ST-3** | The clipboard is the only external sink, and only transiently (it holds the composed URL string after a copy). |
| **ST-4** | The composed link encodes **only** `ctxid`; **all other query parameters of the current URL are discarded** (`url.search=""` before setting `ctxid`). A shared link therefore carries no auth, filters, or prior params — by design. |

---

## 7. Edge cases & config-dependent behaviour

| ID | Case | Behaviour | Source |
|----|------|-----------|--------|
| **EDGE-1** | No active context (`getContext()` falsy) | BEH-9 — silent no-op; no copy, no visual change | `if (!ctxid) return` |
| **EDGE-2** | `globalThis.getContext` undefined (load-order race / API change) | `?.()` yields `undefined` → treated as EDGE-1 (no-op); no thrown error | optional chaining |
| **EDGE-3** | Insecure context / `navigator.clipboard` unavailable or throws | BEH-6 `execCommand('copy')` fallback runs; still reaches BEH-7 | try/catch |
| **EDGE-4** | `execCommand('copy')` itself fails (deprecated/blocked) | **Not handled** — fallback is not wrapped in its own try/catch, so `copied=true` is set unconditionally after the fallback block: the confirmation (BEH-7) can show even if the copy silently failed. *(Known limitation, flagged in self-review I-1.)* | catch-branch has no inner guard |
| **EDGE-5** | Rapid repeated clicks | Each click resets `copied=true` and schedules a fresh 2000 ms timer; timers are not cancelled, so the **last** click governs reset timing (acceptable; no leak of consequence). | `setTimeout` not cleared |
| **EDGE-6** | Plugin disabled / not installed | UI-1 never injected (CFG-2); `chat-top-end` host renders empty. No residual state. | enable-gating |
| **EDGE-7** | Multiple `chat-top-end` HTML extensions present | A0 concatenates all into the host's innerHTML; share button coexists with others (order = A0 discovery order). | `importHtmlExtensions` combinedHTML |
| **EDGE-8** | Headless/CI clipboard | e2e treats the copied-state toggle as **best-effort/informational**; the deterministic gate is "button injected into `chat-top-end` + idle icon = `share`". | `behaviour.mjs` |

---

## 8. Traceability matrix (behaviour → UI → source → test)

| Behaviour | UI | A0 dependency | Test coverage |
|-----------|----|---------------|----------------|
| BEH-1 | UI-1 | EXT-1 | e2e step 1, 1a (deterministic) |
| BEH-2 | UI-2 | — | e2e "share" assertion (deterministic) |
| BEH-3 | UI-1/UI-2 | — | none (CSS-only; visual) |
| BEH-4 | UI-3 | EXT-2 | indirect via BEH-7 |
| BEH-5/6/7 | UI-1/UI-2/UI-3 | — | e2e step 2 (best-effort) |
| BEH-8 | UI-1/UI-2 | — | none (transient timing) |
| BEH-9 (EDGE-1/2) | UI-3 | EXT-2 | none — **coverage gap (self-review I-2)** |
| BEH-11 | — | EXT-3 | none (upstream behaviour) |

---

## 9. Self-review findings (IEEE-29148 quality gates applied to this spec)

- **Completeness — C-1 (closed):** added NEG-1 and API-1 to make the *absence* of api/hooks/python-seams/config-screen explicit and traceable rather than implied.
- **Completeness — C-2 (closed):** added the selector/no-`data-testid` note (Section 3) since the brief flagged selector strategy as load-bearing.
- **Unambiguity — U-1 (closed):** BEH-4 now states verbatim that **all existing query params are dropped** (`url.search=""`), removing the ambiguity of "clean existing params."
- **Consistency — X-1 (closed):** "copy succeeded" vs "confirmation shown" are deliberately decoupled and reconciled in EDGE-4 — the spec no longer implies confirmation ⇒ copy success.
- **Verifiable — V-1 (closed):** each BEH cites a source line and, where present, the e2e assertion; transient/CSS-only behaviours are explicitly marked unverified-by-test rather than over-claimed.
- **Traceable — T-1 (closed):** Section 8 matrix links every BEH → UI → A0 dependency → test, surfacing two real gaps below.
- **Implementation findings surfaced (not spec defects):**
  - **I-1 / EDGE-4:** fallback copy path has no inner error handling → false-positive confirmation possible.
  - **I-2:** BEH-9 (no-context no-op) and BEH-11 (deep-link round-trip) are untested. A round-trip e2e (click → read clipboard → reload with the link → assert correct chat selected) would close the highest-value gap.
  - **I-3:** dropping all query params (ST-4) is intentional but undocumented in README (README is an unexpanded `§§include` stub at HEAD — documentation gap, not behaviour defect).