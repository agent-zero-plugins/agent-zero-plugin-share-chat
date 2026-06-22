# QA / E2E Review — `agent-zero-plugin-share-chat` e2e test spec

**Reviewer scope:** spec vs. actual plugin source (`/tmp/fan-share-chat`) + live A0 (`/a0/webui`, `/a0/src/.../agent-zero-plugin-development-testkit`). Every selector, seam, and harness claim below was checked against real code, not memory.

**Bottom line up front:** The spec is unusually rigorous and the *coverage* is excellent — it closes both gaps the behaviour spec flagged (I-1/EDGE-4 false-positive, I-2 round-trip). But several assertions are **wrong against the real DOM/runtime** (3 Critical), and there is a structural **order-dependence flaw** baked into the harness model the spec did not account for. These must be fixed before the spec is implementable as written.

---

## CRITICAL

### C-1 — Group G precondition is not deterministic; it is order-dependent on prior groups (robustness + verifiability)
The spec asserts (E2E-17) that on a fresh `loggedInPage` with no chat created, `getContext()` is `null`. That is true *only on a truly clean backend*. But the harness runs all groups under **`test.describe.serial` with the plugin installed as persistent backend state across one A0 boot** (`lifecycle.spec.ts:99-101`: "install is backend state, so it persists across each test's fresh page"). Groups C/D/E/F/H all call `#newChat`, which does `/chat_create` — those contexts **persist on the backend** for the rest of the run.

Then on Group G's fresh page, A0's poll/state handler (`/a0/webui/index.js:~386-398`) runs: when `context` is null **but `chatsStore.contexts.length > 0`**, it calls `setContext(firstChatId)` and auto-selects the first existing chat. So `getContext()` will be a real ctxid, **`expect(...).toBeNull()` fails**, and the entire no-op premise collapses.

The spec half-anticipates this ("If a session restored a chat, deselect via `globalThis.deselectChat()`") but `deselectChat()` only clears `context`/sessionStorage — the **next poll re-selects the first backend chat again**, re-racing the assertion.

**Fix:** Do not rely on natural falsy state. Provision it deterministically and defeat the auto-reselect: after `deselectChat()`, **stub the global before the click** — `await page.evaluate(() => { globalThis.getContext = () => null; })` (or `delete globalThis.getContext` as E2E-19 already does) — and gate the no-op assertions on that stub, not on backend state. Alternatively, make Group G the *first* spec alphabetically (`a-...`? no — file order is `specs/*.mjs` sorted) so it runs before any `#newChat`; but serial backend persistence still leaks across the suite, so stubbing is the only robust fix.

### C-2 — E2E-2 positional assertion uses a selector that isn't rendered when no chat is active (correctness)
E2E-2 asserts the share button is DOM-after the project selector via `compareDocumentPosition(.project-dropdown-container, .share-chat-btn)`. Verified: `.project-dropdown-container` exists (`/a0/webui/components/projects/project-selector.html:11`) — **but it lives inside `<template x-if="selectedContext">`** and only renders when a context with a project is selected. Group A's fixture explicitly says **"No chat needed"**, so on that page `selectedContext` is null, `.project-dropdown-container` is **absent**, and `compareDocumentPosition` throws on a null node (or the locator resolves to 0 elements → the evaluate errors).

**Fix:** Either (a) provision a chat in Group A before the positional check, or (b) drop the dependency on the project-selector node and assert position relative to a *stable always-present* sibling — e.g. `#time-date` or the `chat-top-end` host itself: assert `.share-chat-btn` is inside `x-extension#chat-top-end` (already done in E2E-1a) and that the host is the **last** child of `#time-date-container` (which is static in `chat-top.html`). The "after project selector" contract is better proven structurally from `chat-top.html` source, not at runtime.

### C-3 — `pageerror` assertions (E2E-14, E2E-18, E2E-19) are not falsifiable against Alpine 3 (verifiability)
The spec hard-asserts "a console error / unhandled rejection was observed" (E2E-14) and "captured `pageerror` array is empty" (E2E-18/19). A0 runs **Alpine 3.14.x** (`/a0/webui/index.html:43`). Alpine 3 evaluates `@click` expressions inside its own `try/catch` and routes failures to **`console.error`/`console.warn`**, and for async handlers the returned promise is **not awaited** — a rejection becomes an `unhandledrejection`, **not** a `window.onerror` `pageerror`. Playwright's `page.on("pageerror")` captures uncaught exceptions and (depending on version) unhandled rejections inconsistently. So:
- E2E-14's "assert a pageerror was observed when execCommand throws" may **never fire** → false RED or, worse, a swallowed assertion.
- E2E-18/19's "`expect(errors).toEqual([])`" can be **polluted by unrelated A0 console noise** (the onboarding/no-LLM-key path logs errors), causing false RED unrelated to the plugin.

**Fix:** Replace `pageerror` reliance with deterministic listeners: register `page.on("console", ...)` filtered to `type==='error'` **and** `page.on("pageerror", ...)` **and** an injected `window.addEventListener('unhandledrejection', e => window.__rej.push(e.reason))`. For E2E-14, assert against `window.__rej` (the real signal for an async catch-rethrow), not `pageerror`. For E2E-18/19, scope the "no error" assertion to errors whose text **mentions the plugin** (e.g. matches `/share|clipboard|getContext/`), not a blanket empty array — otherwise A0's own startup errors fake-RED the test (violates "no fake green" symmetrically — a false RED is as bad).

---

## MAJOR

### M-1 — E2E-14 mis-models the execCommand-throw path; the textarea leaks and there is NO cleanup (correctness vs. real code)
The spec says when `execCommand` *throws*, "the `setTimeout`/state lines after `document.execCommand` never run." Correct. But it omits the real consequence verified in source (lines 25-34): the textarea is **appended at line 29 before** `execCommand` at line 31, and `removeChild` is at line 32 — **after** the throwing call. So a throw leaves a **leaked off-screen `<textarea>` in the DOM**. E2E-13's sibling assertion `expect(page.locator("textarea")).toHaveCount(0)` would therefore be **violated in the throw sub-case**, and E2E-14 should *assert* the leak as the real bug, not just "no false-positive confirmation."

**Fix:** In E2E-14 (throw sub-case) add a HARD assertion `expect(page.locator("textarea")).toHaveCount(1)` (leaked) to document the actual defect, and cross-link it to the I-1 issue. This is a *stronger, more honest* falsification than the current "no `.share-copied`" alone.

### M-2 — E2E-13's `document.execCommand` override is brittle and may not capture the value (correctness/robustness)
E2E-13 overrides `document.execCommand` to read `document.querySelector('textarea')?.value`. Two problems: (1) if **any** other textarea exists on the page (chat input is a textarea-like; A0's `#chat-input` — verify, but the risk is real), `querySelector('textarea')` grabs the wrong one. (2) The override reads at copy-time, which is fine, but it doesn't scope to the plugin's transient element.

**Fix:** Scope the readback to the element the plugin actually selects: capture from `document.activeElement` (the plugin calls `ta.select()` immediately before `execCommand`, so the active element *is* the plugin textarea) or to the *last* textarea (`[...document.querySelectorAll('textarea')].at(-1)?.value`). Prefer `document.activeElement.value`.

### M-3 — Clipboard readback exact-match is fragile on trailing-slash/origin normalization (robustness)
Multiple groups assert `clip === \`${baseURL}/?ctxid=${ctxid}\``. The plugin builds the link via `new URL(window.location.href); url.search=''; url.searchParams.set('ctxid', ctxid)`. The resulting `toString()` preserves whatever **path** `location.href` had. If `baseURL` is `http://host:port` (no trailing slash) but the page is at `/` , the composed link is `http://host:port/?ctxid=...` — matches. But if the harness navigates to `baseURL` *without* a trailing slash and the server doesn't redirect, `location.pathname` could be `""`→ normalized to `/` by `URL`, generally fine. The real fragility: **`baseURL` may itself carry a trailing slash** (`A0_BASE_URL` env), making the template literal produce `http://host:port//?ctxid=`.

**Fix:** Don't string-concatenate. Assert structurally: `const u = new URL(clip); expect(u.origin).toBe(new URL(baseURL).origin); expect(u.pathname).toBe('/'); expect([...u.searchParams]).toEqual([['ctxid', ctxid]])`. This is exactly the param-key assertion already used in E2E-9/D — apply it everywhere instead of the brittle exact-string form.

### M-4 — E2E-24 contains a no-op placeholder evaluate that asserts nothing real (no-fake-green violation)
E2E-24's first assertion is `expect(await page.evaluate(async () => { const s = await import('/components/plugins/plugin-settings-store.js'); /* ... */ return false; }))` — it **imports a module and unconditionally `return false`**, then (implicitly) compares to... nothing falsifiable. This is a **fake-green**: it will pass regardless of plugin behaviour, directly violating Hard Rule 2. The spec even hedges ("pragmatically, assert there is no clickable element..."), meaning the real assertion is the *second* clause, and the first is dead.

**Fix:** Delete the `import(...) return false` line entirely. Keep only the falsifiable clause: scope to `installedCard("Share Chat")` and assert `card.locator('[\\@click*="openConfig"], .plugin-config-btn').toHaveCount(0)`. (Note: `@click` is not a valid CSS attribute selector token unescaped — see m-6.)

### M-5 — E2E-23 / E2E-24 selectors are speculative and partly invalid (correctness)
- `card.locator('[x-show*="has_config_screen"]')` — `x-show` attributes are **removed/processed by Alpine at runtime** (Alpine hides the element via `style display:none`, and the `x-show` attribute itself may be stripped depending on build). Asserting `toHaveCount(0)` on an Alpine directive attribute is unreliable; it may be 0 even when a config screen *exists* (false pass).
- `[\@click*="openConfig"]` — `@` is not a legal start for an unescaped CSS attribute name; Playwright will throw a selector parse error. Alpine rewrites `@click` to `x-on:click` in the live DOM anyway, so the attribute to match (if any) is `[x-on\\:click*="openConfig"]`.

**Fix:** Verify the actual rendered config affordance in `/a0/webui/components/plugins/list/plugin-list.html` (and the plugin-info modal) before asserting. The most robust positive signal the spec already identified is the plugin-info "Configuration: **Not available**" text — anchor E2E-23/24 on that visible text (scoped to the info modal) and drop the directive-attribute counting.

### M-6 — Group F lower-bound timing assertions are inherently flaky (robustness)
E2E-15 asserts at `+500ms` `.share-copied` is still present, and E2E-16 builds a multi-window timing argument (`+1200ms`, `+1500ms < 2000ms`). The plugin's timer is a bare `setTimeout(...,2000)` started at copy-time. CI under load (nested rootless podman + headless Chromium) can stall the event loop; the 1500ms-still-present window has only ~500ms of slack against a 2000ms timer — a GC pause or video-capture hitch flips it RED. The `EDGE-5` "last click governs" proof is valuable but the chosen margins are too tight.

**Fix:** Widen margins: assert "still present" at `+300ms` (not 500) and the second-click-still-present at `+800ms` (not 1500), keeping the upper-bound revert at `timeout:3000`. Better: gate the *lower bound* on a single coarse check (`+300ms present`) and rely on the **upper-bound revert** as the primary EDGE-8 assertion; the precise "didn't reset early" claim is better verified by reading the Alpine state, not wall-clock racing.

---

## MINOR

### m-1 — `toHaveText("share")` is correct but verify no icon-font ligature whitespace
Verified the icon `<span class="material-symbols-outlined" x-text="...">` sets `textContent` directly via Alpine `x-text`, so `toHaveText("share")` (exact) is right. Note `.material-symbols-outlined` is **not page-unique** (the project selector uses `arrow_drop_down` in the same class). The spec correctly scopes via `.share-chat-btn .material-symbols-outlined` — keep that scoping rigorously in every group (E2E-6/10/15 do). Good.

### m-2 — E2E-3 `x-component path` assertion: confirm the path value (correctness)
Verified `importHtmlExtensions` injects `<x-component path="${normalizePath(path)}">` (`extensions.js:179`) and `normalizePath` prepends `/`. So the `path` attribute is an **absolute** path beginning `/`. The spec's "ends with `share_chat/extensions/webui/chat-top-end/share-chat.html`" is safe (endsWith), but confirm the backend returns `usr/plugins/share_chat/...` not a deduped form. The assertion is fine as `endsWith`.

### m-3 — E2E-11 "stale ctxid stripped by init" coupling is subtle but correct
Verified `chats-store.init()` (`chats-store.js:32-43`) consumes `?ctxid=` first and `history.replaceState`s it out, leaving `foo`/`bar`. So after `goto(baseURL+"/?foo=1&bar=2&ctxid=stale")`, `location.href` retains `foo`/`bar` only — the plugin then drops them via `url.search=''`. Logic is sound. But add a guard: `init()` *also* calls `selectChat("stale")`, which sets `context="stale"` (a bogus id). The subsequent `#newChat` (spec says "if needed") may be skipped, leaving `getContext()==="stale"` and the test asserting against a non-existent context. **Fix:** Always force a fresh `#newChat` after the polluted goto so the live ctxid is real, then capture it.

### m-4 — E2E-25 "nothing persisted" is correct for the plugin but note sessionStorage interaction
Verified: the plugin writes **no** storage. But A0 core writes `lastSelectedChat` to **sessionStorage** on every `selectChat` (`chats-store.js:296`). After `page.reload()`, the chat is re-selected by `init()`. The spec's assertion (regex `/share.?chat/i` over storage keys → false) is correct because the A0 key is `lastSelectedChat`, not share-chat-named. Assertion stands. Just ensure the regex is anchored to plugin-owned keys (it is). Good — but consider also asserting `.share-copied` absence is due to volatility, not because the button re-rendered idle for an unrelated reason (e.g. add: after reload, click again → copied works → proves the component re-initialized cleanly).

### m-5 — E2E-27 status assertion `[404,405]` may miss A0's actual unknown-route behaviour
The spec asserts `/api/share_chat` POST returns 404/405. Verify A0's API router default for unknown `/api/<x>` — some A0 builds return **200 with an error body** or **500**, not 404, for unmatched dynamic handlers. **Fix:** Before hard-coding `[404,405]`, probe a known-nonexistent endpoint in live A0 once and match the *observed* unknown-route status; or assert the **negative** more robustly: `expect(resp.ok()).toBe(false)` plus body does not contain a share-chat handler signature.

### m-6 — Spec-count / glob naming: confirmed 10 files map to 10 videos, but there is no enforcement
Verified the workflow globs `tests/e2e/specs/*.mjs` and emits one test/video each (`plugin-e2e.yml:179-181`), and lifecycle passes `{page, expect, baseURL, pluginName, displayName}` (`lifecycle.spec.ts:129`) — the spec's signature claim is **correct**. The "≤10 groups → one webm each" is a *documented convention (DEC-056)*, **not enforced** by CI. 10 files is exactly at the limit; adding any spec later silently exceeds it. Minor: note this is a soft cap.

### m-7 — Coverage tally lines are prose, not asserted (verifiability of the meta-rule)
Hard Rule 1 mandates each group print `[coverage] <group>: N asserted, M skipped`. The spec lists these as expected outputs but defines no mechanism that **fails the group if the tally is wrong** (e.g. asserted count mismatches actual). As written they're `console.log` decoration — they satisfy the letter of the rule but can drift from reality. **Fix (optional):** increment a counter on each `expect` wrapper and assert the final tally equals the declared N; otherwise the tally is informational only.

---

## GAPS (coverage)

### G-1 — `@skip` reasons reference non-existent issues (`#TBD`) — violates Hard Rule 2's spirit
Rule 2 requires `@skip(reason=<issue-link>)`. Four skips (E2E-4, E2E-5, E2E-28 uninstall, the E2E-24 proxy) use `agent-zero-plugin-share-chat#TBD`. A `#TBD` is **not a link** and will never be triaged → these become permanent silent holes. **Fix:** File the four tracking issues before merge and substitute real numbers; CI/lint should reject `#TBD`.

### G-2 — EDGE-7 (multi-extension concat) skipped as "un-provisionable" — defensible, but a cheaper assertion exists
The spec skips E2E-4 because a single-plugin nested A0 can't host a 2nd `chat-top-end` extension via the UI. Correct (UI-only fixture rule). **But** the concat *mechanism* is observable without a 2nd plugin: `importHtmlExtensions` builds `combinedHTML` and the plugin's button must survive as **one** `x-component` among siblings. You already assert `x-component` count 1 (E2E-3). The truly-uncoverable half is "coexists with *another* plugin's node" — acceptable skip. Keep, but downgrade the skip note to clarify the mechanism (concat string-building) *is* covered by E2E-3, only the multi-tenant case isn't.

### G-3 — No assertion that the button does NOT appear on non-chat routes / before `$store.chatTop` hydrates (timing)
The host is inside `<template x-if="$store.chatTop">` (`chat-top.html`). The button only injects after `chatTop` store hydrates. Every group's `toBeVisible({timeout:20_000})` implicitly waits for this, so it's covered for the positive case — but there's no guard against a **race where the MutationObserver injects before Alpine renders the host** (the observer in `extensions.js:201-221` re-fires on the `x-extension` node insertion). Low risk; the 20s visibility wait absorbs it. No fix required — noting for completeness.

### G-4 — BEH-3 hover correctly skipped, but a no-cost partial assertion is available
E2E-5 skips hover as "pure CSS, nothing to falsify." True for opacity/box-shadow. However the **idle opacity 0.7** is a deterministic computed style: `expect(icon).toHaveCSS("opacity", "0.7")` is falsifiable and would catch a regression that drops the stylesheet entirely (a real failure mode if the `<style>` block fails to inject). **Fix (optional, raises value):** convert E2E-5 from full-skip to a single computed-style assertion on idle opacity; keep the hover-transition itself skipped.

---

## What the spec got right (credit where due)
- **Fire-and-forget discipline:** the spec correctly never `await`s `openModal`/`openConfig`; it relies on the devkit's `loggedInPage` (not `pluginsPage`) for behaviour groups, exactly matching `lifecycle.spec.ts:116-123`'s DEC-058 guidance. No awaited-promise-hang risk introduced.
- **UI-only fixtures:** all app state via `#newChat` and the Plugins panel — verified `#newChat` → `$store.chats.newChat()` → `/chat_create` → `selectChat` (`chats-list.html:17`, `chats-store.js:162-172`). No backend seeding. Compliant.
- **LLM-less / no dump_live:** correct — the plugin genuinely has zero Python (`__init__.py` is a docstring; no `api/`, `hooks.py`, `extensions/python/`), `meta.yaml env: []`, no `.devkit.yml`. E2E-26's negative container assertions are valid and the dump_live N/A justification holds.
- **Round-trip (Group H):** the highest-value addition; `chats-store.init()` consume path and `Alpine.store("chats").selected` cross-check are both real and accessible (`AlpineStore.js:28`).
- **Signature & glob:** `({page,expect,baseURL,pluginName,displayName})` and `specs/*.mjs`→1 video each are both verified correct.

---

## VERDICT

**REQUEST CHANGES (not approvable as-is).** The coverage design is best-in-class and the hard-rules framing is sound, but the spec ships **three Critical correctness defects that will fail or fake-pass against the real runtime** (C-1 order-dependent no-context premise; C-2 project-selector-not-rendered positional assertion; C-3 unreliable `pageerror` model on Alpine 3), one **fake-green** (M-4 dead `return false` evaluate), and **invalid/speculative selectors** (M-5/m-6 `@click`/`x-show` matching). None are conceptual — they're fixable in a focused editorial pass:

1. Stub `getContext`/scope error-listeners to defeat order-dependence and console-noise (C-1, C-3).
2. Re-anchor positional and config assertions on static/visible signals, not runtime-stripped directives (C-2, M-5).
3. Delete the no-op evaluate; replace exact-string clipboard matches with structural `URL` assertions (M-4, M-3).
4. Model the execCommand-throw textarea leak as the real defect; harden timing margins; file the `#TBD` issues (M-1, M-6, G-1).

After those, this becomes a genuinely strong, falsifiable, hermetic suite. The skips are honest (modulo `#TBD`), no silent swallows exist in the asserted paths, and the UI-only/LLM-less hard rules are met.
```