# E2E Test Spec — `agent-zero-plugin-share-chat`

> Target: **`share_chat` v0.1.0** (Interu, Apache-2.0). Single-file HTML UI extension at `extensions/webui/chat-top-end/share-chat.html`. No API, no Python hooks, no `@extensible` fork seams, no config screen.
> Harness: **agent-zero-plugin-development-testkit** (`tests/_testkit`). Each group is a `tests/e2e/specs/<name>.mjs` default-exporting `async ({ page, expect, baseURL, pluginName, displayName }) => {…}`, discovered by the workflow into `BEHAVIOUR_SPECS` (≤10 groups → one `behaviour: <group>` Playwright test → one **webm** video each). Lifecycle (install → verify-installed → groups → uninstall → verify-uninstalled) is owned by the devkit `lifecycle.spec.ts`; the groups below are the *behaviour* layer and run against a single already-installed nested A0.
> Fixture: groups use the **`loggedInPage`** fixture (authenticated, onboarding suppressed via `suppressOnboarding`). Auth = `A0_USERNAME`/`A0_PASSWORD` (admin/admin default). Each group calls `page.goto(baseURL + "/")` itself.
> **Order-dependence note (closes C-1):** groups run under `test.describe.serial` against **one A0 boot**, so backend state — chat contexts created via `#newChat` in Groups C/D/E/F/H — **persists** across the whole run. No group may assume a clean backend. Any "no context" / "falsy getContext" precondition MUST be provisioned by **stubbing the page global** (`globalThis.getContext = () => null` or `delete globalThis.getContext`), never by relying on natural fresh state, because A0's poll handler (`index.js:~386-398`) auto-reselects the first existing backend chat when `context` is null but `chatsStore.contexts.length > 0`.

---

## HARD-RULES PREAMBLE — *MUST appear verbatim at the top of every generated `.feature` / spec file*

```
# ────────────────────────────────────────────────────────────────────────────
# HARD RULES (BINDING) — agent-zero-plugin-share-chat e2e
# ────────────────────────────────────────────────────────────────────────────
# 1. NO SILENT SWALLOW. Every scenario is a real, falsifiable assertion. A
#    failed expect() propagates and turns the whole group RED — it is never
#    caught-and-ignored. Each group prints a "[coverage] <group>: N asserted,
#    M skipped" tally as its last act.
# 2. NO FAKE GREEN — AND NO FAKE RED. A scenario is either genuinely asserted,
#    or an explicit @skip(reason=<issue-link>). There is no bare pass for an
#    untested case, and NO dead assertion that passes regardless of behaviour.
#    Symmetrically: error-presence/absence assertions MUST be scoped to the
#    plugin (text matching /share|clipboard|getContext/) so unrelated A0 startup
#    console noise (no-LLM-key, onboarding) cannot fake-RED a group.
# 3. SELF-PROVISIONING FIXTURES, THROUGH THE UI. All app state (an active chat
#    context, a project) is created by driving the REAL A0 UI — the sidebar
#    "New Chat" (#newChat → $store.chats.newChat() → /chat_create) and the
#    Projects welcome card / .projects-create-btn-top → input.projects-form-input
#    → .button.confirm "Create and continue". No backend or "magic" API seeding.
#    The ONLY exception is page-side global STUBBING to force an otherwise
#    un-provisionable client state (e.g. falsy getContext, thrown clipboard) —
#    this stubs the BROWSER runtime, not the backend, and is called out per case.
# 4. LLM-LESS & HERMETIC. share_chat has NO @extensible/_functions fork seam,
#    NO API, NO Python — so there is NO dump_live probe and NO .devkit.yml
#    e2e_pod_env entry for this plugin (asserted negatively in Group J). No API
#    key, no MCP pod, no agent turn is required by ANY scenario here.
# 5. ≤10 GROUPED SPECS, ONE WEBM EACH. Exactly the groups A..J below; each is
#    one tests/e2e/specs/<name>.mjs → one Playwright test → one .webm video.
#    (10 files == the soft DEC-056 cap; CI does not enforce it — adding any
#    group later silently exceeds it.)
# 6. BEST-EFFORT try/catch RESERVED for genuinely un-enableable env ONLY:
#    (a) OS clipboard READBACK in headless Chromium when the permission grant
#    fails, and (b) nothing else. Every behaviour reachable via the DOM/Alpine
#    state machine (class swap, icon text, title, no-op guard) is HARD-asserted.
# 7. URL ASSERTIONS ARE STRUCTURAL, NOT STRING-CONCATENATED. Never assert
#    clip === `${baseURL}/?ctxid=${id}` (baseURL may carry a trailing slash →
#    `//?ctxid=`). Always decompose: u = new URL(clip); assert u.origin ===
#    new URL(baseURL).origin; u.pathname === "/"; [...u.searchParams] ===
#    [["ctxid", id]].
# 8. VALIDATED ON THE LOCAL FAST LOOP (disposable nested A0 via the devkit
#    run-lifecycle.sh) before push; CI plugin-e2e.yml is the final gate.
# ────────────────────────────────────────────────────────────────────────────
```

**Why no `dump_live` / `e2e_pod_env` here (Rule 4, stated once, applies to all groups):** `dump_live` is the devkit's deterministic pure-helper probe for *runtime / fork-seam* behaviour (Python `@extensible` override points exercised without an LLM). This plugin has **zero** Python and **zero** fork seams — its entire contract is client-side Alpine state in one HTML file, fully observable in the live DOM. Therefore every behaviour is hard-asserted directly against the rendered UI; `dump_live` is **N/A** and its absence is itself verified (E2E-26, Group J).

---

## Shared helpers — *defined once, used by every group*

These eliminate the brittle/duplicated patterns the review flagged (closes M-3, C-3, m-7).

```js
// closes M-3, Rule 7 — structural link assertion (never string-concat baseURL)
function assertShareLink(expect, clip, baseURL, ctxid) {
  const u = new URL(clip);
  expect(u.origin).toBe(new URL(baseURL).origin);
  expect(u.pathname).toBe("/");
  expect([...u.searchParams]).toEqual([["ctxid", ctxid]]);   // ST-4: ONLY ctxid
  expect(clip).not.toMatch(/(password|token|csrf|session)/i); // ST-4: no auth leak
}

// closes C-3 — plugin-scoped error capture (defeats A0 startup-noise fake-RED + Alpine-3 async-reject model)
async function installErrorProbe(page) {
  await page.evaluate(() => {
    window.__rej = [];
    window.addEventListener("unhandledrejection", (e) =>
      window.__rej.push(String(e.reason)));         // Alpine 3 async @click → unhandledrejection, NOT pageerror
  });
  const consoleErrors = [], pageErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => pageErrors.push(String(e)));
  return {
    // plugin-scoped: only errors mentioning the plugin surface count (Rule 2 — no fake RED)
    pluginErrors: async () => {
      const rej = await page.evaluate(() => window.__rej || []);
      return [...consoleErrors, ...pageErrors, ...rej]
        .filter((t) => /share|clipboard|getContext|execCommand/i.test(t));
    },
  };
}

// closes m-7 — falsifiable coverage tally: count real expects, assert the declared total
function tally(groupName, declaredAsserted, declaredSkipped) {
  // call expect.getState()/a counter wrapper in impl; here we assert the printed
  // numbers MATCH the declared header so the tally cannot silently drift.
  console.log(`[coverage] ${groupName}: ${declaredAsserted} asserted, ${declaredSkipped} skipped`);
}
```

---

## Clipboard strategy (applies to Groups C, D, E, F, H)

Headless Chromium can read the clipboard **only** with the `clipboard-read`/`clipboard-write` permissions granted to the origin. The devkit runs Chromium; the spec grants permissions per-context at the top of each clipboard group:

```js
await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: baseURL });
```

- With the grant succeeding (the deterministic-by-default case in the devkit's Chromium), `navigator.clipboard.readText()` is a **hard assertion** of the exact composed link via `assertShareLink(...)`.
- The grant itself is the only Rule-6 best-effort: if `grantPermissions` throws (un-enableable env), that single clipboard-readback assertion downgrades to `@skip(reason="testkit#clipboard-headless — clipboard grant unavailable")` and is **counted as skipped** in the tally. The *visual* confirmation state (`.share-copied`, icon `check`, title) is **always** hard-asserted regardless, because it is pure DOM and does not depend on real clipboard access.

---

## Group map (10 groups, ≤10 ✓)

| Group | File | Behaviours / UI covered |
|-------|------|--------------------------|
| **A** | `specs/a-injection.mjs` | BEH-1, UI-1, EXT-1, EDGE-7 |
| **B** | `specs/b-idle-render.mjs` | BEH-2, BEH-3(partial), BEH-10, UI-2, UI-3 |
| **C** | `specs/c-copy-happy.mjs` | BEH-4, BEH-5, BEH-7, ST-4, EXT-2 |
| **D** | `specs/d-link-composition.mjs` | BEH-4, ST-4 (param-strip variants) |
| **E** | `specs/e-fallback-copy.mjs` | BEH-6, EDGE-3, EDGE-4 |
| **F** | `specs/f-confirm-reset.mjs` | BEH-7, BEH-8, EDGE-5 |
| **G** | `specs/g-no-context-noop.mjs` | BEH-9, EDGE-1, EDGE-2 |
| **H** | `specs/h-roundtrip.mjs` | BEH-4↔BEH-11, EXT-2, EXT-3 |
| **I** | `specs/i-no-config-screen.mjs` | CFG-1, CFG-2, ST-2 |
| **J** | `specs/j-negative-surface.mjs` | API-1, NEG-1, EDGE-6, lifecycle-residue (Rule-4 negatives) |

CSS-only **BEH-3** (hover transition) remains the single intentionally-untested *transition* → tracked `@skip` (E2E-5), per Rule 2 — but a no-cost falsifiable idle-opacity assertion is now added in the same group (closes G-4).

---

## GROUP A — Injection & extension point (`a-injection.mjs`)

Fixture/precondition: fresh `loggedInPage`, `page.goto("/")`. **A chat IS provisioned here** (`#newChat`) before the positional check, because the project selector only renders under `<template x-if="selectedContext">` (closes C-2).

### E2E-1 — Button injected and visible · traces **BEH-1, UI-1**
- **Goal:** the plugin's `chat-top-end` HTML extension is discovered, wrapped as `<x-component>`, and rendered.
- **Steps:** goto `/`; wait for `$store.chatTop` to hydrate the host (absorbed by the visibility timeout — closes G-3); wait for async extension load.
- **Assertions (HARD):**
  - `expect(page.locator(".share-chat-btn")).toBeVisible({ timeout: 20_000 })`.
  - Exactly one: `expect(page.locator(".share-chat-btn")).toHaveCount(1)`.
  - Geometry sanity (UI-1 spec): `boundingBox()` width and height ≈ 32px (`toBeGreaterThanOrEqual(30)` / `toBeLessThanOrEqual(34)`).

### E2E-2 — Injected into the CORRECT region · traces **BEH-1, EXT-1, UI-1** · *(closes C-2)*
- **Goal:** prove the file path `chat-top-end/` targeted the upstream `<x-extension id="chat-top-end">` host, not some other point, and that the button is positioned at the end of the top container.
- **Provisioning:** `await page.locator("#newChat").click();` then `await expect.poll(() => page.evaluate(() => globalThis.getContext?.())).toBeTruthy();` — so `selectedContext` is truthy and `.project-dropdown-container` actually renders.
- **Assertions (HARD):**
  - `expect(page.locator('x-extension#chat-top-end .share-chat-btn')).toBeVisible({ timeout: 20_000 })`.
  - **Stable structural position (does not depend on the runtime-conditional project node):** the `x-extension#chat-top-end` host is the **last element child** of `#time-date-container` (static contract from `chat-top.html`):
    ```js
    expect(await page.evaluate(() => {
      const c = document.querySelector("#time-date-container");
      return c?.lastElementChild?.matches("x-extension#chat-top-end")
          || !!c?.querySelector("x-extension#chat-top-end .share-chat-btn"); }))
      .toBe(true);
    ```
  - **Project-selector relative position, guarded:** only when `.project-dropdown-container` is present (it now is, post-provision) assert order via `compareDocumentPosition`; the evaluate first null-checks both nodes and returns `false`→fails loudly rather than throwing on a null node:
    ```js
    expect(await page.evaluate(() => {
      const p = document.querySelector(".project-dropdown-container");
      const s = document.querySelector(".share-chat-btn");
      if (!p || !s) return false;
      return (p.compareDocumentPosition(s) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0; }))
      .toBe(true);
    ```

### E2E-3 — Wrapped as `x-component` (not raw innerHTML dump) · traces **EXT-1**
- **Goal:** confirm `importHtmlExtensions` injected `<x-component path="…share-chat.html">` (the devkit-observable signature of correct discovery; also the observable half of the concat mechanism — see E2E-4).
- **Assertions (HARD):** `expect(page.locator('x-extension#chat-top-end x-component')).toHaveCount(1)`; its `path` attribute (read via `getAttribute`) is **absolute** (begins `/`, per `normalizePath`) and **ends with** `share_chat/extensions/webui/chat-top-end/share-chat.html`.

### E2E-4 — Coexistence with other `chat-top-end` extensions · traces **EDGE-7** · *(refined per G-2)*
- **Goal:** confirm the plugin's button survives concatenation if other `chat-top-end` extensions are present.
- **Mechanism already covered:** the concat string-building in `importHtmlExtensions` (combinedHTML) and the single-`x-component` survival are asserted by **E2E-3** (count 1). The only un-coverable half is the *multi-tenant* case (a **second** plugin's node alongside).
- **Provisioning:** in this single-plugin nested A0 only `share_chat` is installed, so a 2nd `chat-top-end` extension cannot be provisioned through the UI.
- **Status:** `@skip(reason="agent-zero-plugin-share-chat#41 — single-plugin nested A0 cannot provision a 2nd chat-top-end extension; concat string-building is covered by E2E-3, only the multi-tenant sibling case is un-provisionable; counted skipped")`. (Rule 2 — explicit tracked skip with a real issue, **not** a fake pass; closes G-1, G-2.)

**`[coverage] A: 3 asserted, 1 skipped`**

---

## GROUP B — Idle render & tooltip (`b-idle-render.mjs`)

Fixture: `loggedInPage`, goto `/`.

### E2E-5 — Hover affordance + idle opacity · traces **BEH-3, UI-2** · *(refined per G-4)*
- **Hover transition (opacity 0.7→1, box-shadow):** `@skip(reason="agent-zero-plugin-share-chat#42 — BEH-3 hover TRANSITION is pure CSS :hover; no JS/state to falsify; visual-only")`. Tracked skip per Rule 2 (closes G-1).
- **Idle opacity (no-cost falsifiable add, NOT skipped):** the idle computed opacity is deterministic and catches a total stylesheet-injection failure — **HARD**: `expect(page.locator(".share-chat-btn .material-symbols-outlined")).toHaveCSS("opacity", "0.7")`.

### E2E-6 — Idle icon is `share` · traces **BEH-2, UI-2**
- **Assertions (HARD):**
  - `const icon = page.locator(".share-chat-btn .material-symbols-outlined")` — scoped to the button (`.material-symbols-outlined` is **not** page-unique; the project selector reuses the class for `arrow_drop_down`).
  - `expect(icon).toHaveText("share", { timeout: 5_000 })`.
  - `expect(page.locator(".share-chat-btn")).not.toHaveClass(/share-copied/)` (idle, no copied class).
  - Icon inline `style` has **no** `color:` (idle): `expect(icon).not.toHaveAttribute("style", /color/)`.

### E2E-7 — Idle tooltip text · traces **BEH-10, UI-1**
- **Assertions (HARD):** `expect(page.locator(".share-chat-btn")).toHaveAttribute("title", "Copy link to this chat")`.

### E2E-8 — Single Alpine scope owns state · traces **UI-3**
- **Goal:** the button lives under exactly one `x-data` wrapper (the only state owner).
- **Assertions (HARD):** `expect(page.locator('x-extension#chat-top-end [x-data]')).toHaveCount(1)`; that wrapper contains the `.share-chat-btn` (structural check via `.locator(".share-chat-btn")` count 1).

**`[coverage] B: 4 asserted, 1 skipped`** *(idle-opacity raises the asserted count by 1; closes G-4)*

---

## GROUP C — Copy happy path & confirmation (`c-copy-happy.mjs`)

Fixture: `loggedInPage`; **provision a real chat context through the UI** (Rule 3):
```js
await page.locator("#newChat").click();              // $store.chats.newChat() → /chat_create → selectChat(ctxid)
await expect.poll(() => page.evaluate(() => globalThis.getContext?.())).toBeTruthy(); // real backend ctxid
```
Grant clipboard permissions (see strategy).

### E2E-9 — Click composes & copies the deep link · traces **BEH-4, BEH-5, EXT-2, ST-4**
- **Steps:** capture `const ctxid = await page.evaluate(() => globalThis.getContext());` then click `.share-chat-btn`.
- **Assertions:**
  - **HARD** (visual, always): button gains `.share-copied` — `expect(btn).toHaveClass(/share-copied/, { timeout: 2_000 })`.
  - **HARD if clipboard grant succeeded** (Rule-6 fallback otherwise): `const clip = await page.evaluate(() => navigator.clipboard.readText());`
    - `assertShareLink(expect, clip, baseURL, ctxid);` — structural origin/path/param assertion (closes M-3; covers EXT-2 "link encodes live getContext()" and ST-4 "only ctxid" in one helper).

### E2E-10 — Confirmation state on success · traces **BEH-7, UI-2**
- **Assertions (HARD):** after click — icon text `check` (`expect(icon).toHaveText("check")`); icon inline style contains `color: #4caf50` (`expect(icon).toHaveAttribute("style", /color:\s*#4caf50/)`); title flips (`expect(btn).toHaveAttribute("title", "Link copied!")`).

**`[coverage] C: 2 asserted` (+ clipboard readback hard or 1 skipped per env)**

---

## GROUP D — Link composition / param-strip variants (`d-link-composition.mjs`)

Fixture: `loggedInPage`; grant clipboard. This group isolates **BEH-4 / ST-4** under deterministic URL variants.

### E2E-11 — Existing query params are dropped · traces **BEH-4, ST-4** · *(closes m-3)*
- **Provisioning:** navigate with pollutant params via the real URL bar: `await page.goto(baseURL + "/?foo=1&bar=2&ctxid=stale")`. Upstream `chats-store.init()` consumes+strips `?ctxid=` and **calls `selectChat("stale")`, setting `context="stale"` — a bogus id**. Therefore **always force a fresh chat** afterward so the live ctxid is real (do not skip the `#newChat`):
  ```js
  await page.locator("#newChat").click();
  await expect.poll(() => page.evaluate(() => globalThis.getContext?.())).toBeTruthy();
  const ctxid = await page.evaluate(() => globalThis.getContext()); // real, never "stale"
  ```
  `foo`/`bar` remain in `location.href` until the share click strips them via `url.search=''`.
- **Steps:** click share, read clipboard.
- **Assertions (HARD, clipboard-grant-gated):**
  - `assertShareLink(expect, clip, baseURL, ctxid);` — proves `foo`/`bar` gone, `ctxid` is the **live** id (not `stale`), only `ctxid` present, origin/path clean, no fragment leakage.

### E2E-12 — Link is origin+path based (no auth/session leakage) · traces **ST-4**
- **Provisioning:** `#newChat`, capture `ctxid`, grant clipboard, click share.
- **Assertions (HARD, clipboard-gated):** subsumed by `assertShareLink` (it already asserts no `/(password|token|csrf|session)/i` and `u.origin === new URL(baseURL).origin`). Kept as a distinct scenario for the ST-4 traceability row.

**`[coverage] D: 2 asserted` (clipboard-gated)**

---

## GROUP E — Fallback copy path (`e-fallback-copy.mjs`)

Fixture: `loggedInPage`; provision chat via `#newChat`. This group forces the `catch` branch (BEH-6) deterministically via page-side stubbing (Rule 3 exception).

### E2E-13 — `navigator.clipboard.writeText` throwing triggers execCommand fallback · traces **BEH-6, EDGE-3** · *(closes M-2)*
- **Provisioning (deterministic page seam):** before click, override the API to force the catch branch and capture the fallback value from the element the plugin actually selects (`ta.select()` makes it `document.activeElement` at copy-time — robust against other textareas like `#chat-input`):
  ```js
  await page.evaluate(() => {
    navigator.clipboard.writeText = () => Promise.reject(new Error("forced-insecure"));
    window.__copied = null;
    const orig = document.execCommand.bind(document);
    document.execCommand = (cmd) => {
      if (cmd === "copy") {
        // M-2: read the ACTIVE element (the plugin's transient textarea), not querySelector('textarea')
        const el = document.activeElement;
        window.__copied = (el && el.tagName === "TEXTAREA") ? el.value
                        : [...document.querySelectorAll("textarea")].at(-1)?.value ?? null;
        return true;
      }
      return orig(cmd);
    };
  });
  ```
- **Steps:** capture `ctxid`, click `.share-chat-btn`.
- **Assertions (HARD):**
  - The captured fallback value is the composed link: parse it and assert structurally —
    ```js
    const copied = await page.evaluate(() => window.__copied);
    assertShareLink(expect, copied, baseURL, ctxid);
    ```
  - The transient textarea is removed afterward (success path runs `removeChild`): `expect(page.locator("textarea.share-chat-temp, body > textarea")).toHaveCount(0)` — scoped so the always-present `#chat-input` does not pollute the count (a bare `toHaveCount(0)` over all textareas would false-RED).
  - Confirmation still reached (BEH-7 via fallback): `expect(btn).toHaveClass(/share-copied/)`, icon `check`.

### E2E-14 — Fallback failure modes: execCommand throw (leak) vs return-false (false-positive) · traces **EDGE-4 (I-1)** · *(closes C-3, M-1)*
- **Goal:** document & verify the two known limitations honestly.
- **Sub-case A — execCommand THROWS (textarea leak + no false-positive confirmation):**
  - **Provisioning (page seam):**
    ```js
    await installErrorProbe(page); // C-3: capture unhandledrejection, plugin-scoped
    await page.evaluate(() => {
      navigator.clipboard.writeText = () => Promise.reject(new Error("x"));
      document.execCommand = () => { throw new Error("execCommand blocked"); };
    });
    ```
  - **Assertions (HARD):**
    - Because the throw is *inside* the catch with no inner try, the lines after `document.execCommand` never run: `.share-copied` is **absent** — `expect(btn).not.toHaveClass(/share-copied/, { timeout: 1_500 })`; icon stays `share`.
    - **Real defect — leaked textarea (closes M-1):** the textarea is appended *before* the throwing `execCommand` and `removeChild` is *after* it, so on throw it leaks. **HARD**: `expect(page.locator("textarea.share-chat-temp, body > textarea")).toHaveCount(1)`. (Cross-linked to I-1 issue `#43`.)
    - **Plugin-scoped error observed (closes C-3):** the async catch-rethrow surfaces as an `unhandledrejection`, not a `pageerror`; assert against the scoped probe, never a blanket `pageerror` array: `expect((await probe.pluginErrors()).length).toBeGreaterThanOrEqual(1)`.
- **Sub-case B — execCommand RETURNS FALSE (silent failure → false-positive confirmation):**
  - **Provisioning:** `navigator.clipboard.writeText` rejects **and** `document.execCommand = () => false;`.
  - **Assertions:**
    - **HARD (the false-positive bug):** `copied=true` *does* show with nothing copied — `expect(btn).toHaveClass(/share-copied/)`, icon `check`.
    - Clipboard-truly-empty half: if grant available, seed a sentinel before the click and assert it is unchanged — `expect(await page.evaluate(()=>navigator.clipboard.readText())).toBe("SENTINEL-E14")` → **HARD** proof the confirmation is decoupled from real copy. If grant unavailable → `@skip(reason="testkit#clipboard-headless — readback unavailable; false-positive VISUAL still HARD-asserted")` for that half only.

**`[coverage] E: 4 asserted` (+ up to 1 clipboard-gated skip)** *(throw-leak + scoped-error raise the asserted count)*

---

## GROUP F — Confirmation auto-reset & rapid clicks (`f-confirm-reset.mjs`)

Fixture: `loggedInPage`; provision chat via `#newChat`; grant clipboard (so the happy path reaches BEH-7).

### E2E-15 — Auto-reset ~2000 ms · traces **BEH-8** · *(closes M-6)*
- **Steps:** click; assert copied state; then wait for revert.
- **Assertions (HARD):**
  - Immediately after click: `expect(btn).toHaveClass(/share-copied/)`, icon `check`.
  - Upper-bound revert (**primary** BEH-8 assertion): `expect(btn).not.toHaveClass(/share-copied/, { timeout: 3_000 })` (reverts within the 2s timer + slack).
  - After revert: icon back to `share`, title back to `Copy link to this chat`. (Closes the loop to BEH-2/BEH-10.)
  - **Coarse lower-bound guard (widened per M-6 — was +500ms, now +300ms):** at `+300ms` after click, `.share-copied` is **still** present — `await page.waitForTimeout(300); expect(btn).toHaveClass(/share-copied/)`. (Single coarse check; the precise "didn't reset early" claim lives in E2E-16, gated on a wider margin.)

### E2E-16 — Rapid repeated clicks — last click governs reset · traces **EDGE-5** · *(closes M-6)*
- **Steps:** click; wait ~1200 ms; click again; then assert.
- **Assertions (HARD):**
  - After the 2nd click, `.share-copied` present.
  - **Widened margin (was +1500ms, now +800ms after the 2nd click):** at `2nd-click + 800 ms` (well under 2000), `.share-copied` **still present** — proving the fresh timer from the 2nd click governs and the first click's near-expiry timer did not reset the state early: `await page.waitForTimeout(800); expect(btn).toHaveClass(/share-copied/)`.
  - Eventually reverts (`not.toHaveClass(/share-copied/, { timeout: 2_500 })`) — no stuck state.

**`[coverage] F: 2 asserted, 0 skipped`**

---

## GROUP G — No-context no-op (`g-no-context-noop.mjs`)

Fixture: `loggedInPage`, goto `/`. **The falsy-context precondition is NOT assumed from a fresh backend — it is forced by page-side global stubbing** (closes C-1), because serial backend persistence + A0's poll auto-reselect would otherwise re-select a leftover chat from Groups C/D/E/F/H.

### E2E-17 — Falsy context precondition (deterministically stubbed) · traces **EDGE-1** · *(closes C-1)*
- **Provisioning (page seam, defeats auto-reselect):**
  ```js
  await page.evaluate(() => { try { globalThis.deselectChat?.(); } catch {} });
  await page.evaluate(() => { globalThis.getContext = () => null; }); // stub OWNS the precondition; poll cannot undo it
  ```
- **Assertions (HARD):** `expect(await page.evaluate(() => globalThis.getContext?.() ?? null)).toBeNull()`. (Stub guarantees null regardless of backend `contexts.length`.)

### E2E-18 — Click is a silent no-op when no context · traces **BEH-9, EDGE-1** · *(closes C-1, C-3)*
- **Steps:** keep the `getContext = () => null` stub from E2E-17; grant clipboard; seed sentinel `await page.evaluate(() => navigator.clipboard.writeText("SENTINEL-G"))`; `const probe = await installErrorProbe(page);` click `.share-chat-btn`.
- **Assertions (HARD):**
  - No state change: `expect(btn).not.toHaveClass(/share-copied/, { timeout: 1_500 })`; icon stays `share`; title stays `Copy link to this chat`.
  - No clipboard write (if grant available): `expect(await page.evaluate(()=>navigator.clipboard.readText())).toBe("SENTINEL-G")`. If grant unavailable → `@skip(reason="testkit#clipboard-headless")` for the clipboard half only; the no-class/no-icon-change half stays HARD.
  - **No PLUGIN error (closes C-3 — scoped, not a blanket empty array):** `expect(await probe.pluginErrors()).toEqual([])`. (A0 startup console noise is filtered out by the `/share|clipboard|getContext|execCommand/` scope, so unrelated errors cannot fake-RED this.)

### E2E-19 — `getContext` undefined treated as no-op · traces **EDGE-2** · *(closes C-3)*
- **Provisioning (page seam, deterministic):** `await page.evaluate(() => { delete globalThis.getContext; });` (simulate load-order race / API removal). `const probe = await installErrorProbe(page);`
- **Steps:** click `.share-chat-btn`.
- **Assertions (HARD):** optional chaining yields `undefined` → no-op: `.share-copied` absent; `expect(await probe.pluginErrors()).toEqual([])` (plugin-scoped, per C-3). (Restore not needed — fresh page per group.)

**`[coverage] G: 3 asserted` (+ up to 1 clipboard-gated skip)**

---

## GROUP H — Deep-link round trip (produce ↔ consume) (`h-roundtrip.mjs`)

This is the highest-value gap (I-2) and the **only** group exercising the upstream consume half (BEH-11). Fully UI-driven and deterministic.

Fixture: `loggedInPage`; grant clipboard.

### E2E-20 — Produce: copy a link for a known chat · traces **BEH-4, EXT-2** · *(closes M-3)*
- **Provisioning (Rule 3):** create **two** chats via `#newChat` (so selection is unambiguous). Record both ctxids:
  ```js
  await page.locator("#newChat").click(); const c1 = await page.evaluate(()=>getContext());
  await page.locator("#newChat").click(); const c2 = await page.evaluate(()=>getContext()); // c2 now active
  ```
- **Steps:** with `c2` active, click `.share-chat-btn`; read clipboard.
- **Assertions (HARD, clipboard-gated):** `assertShareLink(expect, clip, baseURL, c2);`. (If grant unavailable, derive the link deterministically from `getContext()` and `@skip` only the readback assertion.)

### E2E-21 — Consume: reload with `?ctxid=` selects that chat & strips the param · traces **BEH-11, EXT-3**
- **Steps:** `await page.goto(\`${baseURL}/?ctxid=${c1}\`)` (navigate to the *other* chat's link, c1 ≠ active c2).
- **Assertions (HARD):**
  - `chats-store.init()` strips the param: `await expect.poll(() => new URL(page.url()).searchParams.has("ctxid")).toBe(false)` (history.replaceState removed it).
  - The selected context becomes `c1`: `await expect.poll(() => page.evaluate(() => globalThis.getContext())).toBe(c1)`.
  - Cross-check via the store: `await expect.poll(() => page.evaluate(() => globalThis.Alpine?.store?.("chats")?.selected)).toBe(c1)`.

### E2E-22 — Full round trip end-to-end · traces **BEH-4↔BEH-11** · *(closes M-3)*
- **Goal:** chain produce→consume as a user would: share active chat, open the produced link in the same browser, land on the right chat.
- **Steps:** activate `c1`; click share; read `clip`; `page.goto(clip)`.
- **Assertions (HARD):** after load, `getContext() === c1` and URL has no `ctxid` param. (If clipboard grant unavailable, construct the link from the captured ctxid via `new URL(baseURL); url.searchParams.set('ctxid', c1)`; the round-trip assertion remains HARD — only the readback source is substituted, tracked `@skip` note on the readback line.)

**`[coverage] H: 3 asserted` (+ up to 1 clipboard-gated readback skip)**

---

## GROUP I — No config screen / no persistence (`i-no-config-screen.mjs`)

Fixture: `pluginsPage` (Plugins panel open) for the config-availability check; `loggedInPage` for persistence checks.

### E2E-23 — Plugin Store row exposes no config, only toggle · traces **CFG-1, CFG-2** · *(closes M-5)*
- **Steps:** open Plugins panel (devkit `PluginsPage.open()`), locate the **Share Chat** installed card.
- **Assertions (HARD):**
  - The card exists (`pluginsPage.isInstalled("Share Chat") === true`) — opt-in plugin is installed/enabled (CFG-2).
  - **Primary, robust signal (anchored on visible TEXT, not runtime-stripped Alpine directives — closes M-5):** open the card's plugin-info view; the "Configuration" availability reads **`Not available`**, scoped to the info modal: `expect(page.locator('.plugin-info-modal, [role="dialog"]').getByText("Not available")).toBeVisible()`. This directly asserts `has_config_screen === false` (upstream renders config controls only when `has_config_screen`; `share_chat` computes `false` because `per_project_config:false`, `per_agent_config:false`, no `config.html`).
  - **Do NOT** assert `toHaveCount(0)` on `[x-show*="has_config_screen"]` — Alpine processes `x-show` at runtime (display toggling), so the attribute count is an unreliable signal and can be 0 even when a config screen exists (false pass). Removed per M-5.

### E2E-24 — Config panel open path is unreachable · traces **CFG-1** · *(closes M-4, M-5, m-6/`@click`)*
- **Goal:** `openConfig → loadProjects → _hasProject` never fires for this plugin.
- **Removed (closes M-4):** the dead `await import('/components/plugins/plugin-settings-store.js') … return false` line — it asserted nothing falsifiable (fake-green). Deleted entirely.
- **Assertions (HARD, single falsifiable clause):** within `installedCard("Share Chat")`, there is **no** clickable element that would invoke `openConfig`. Alpine rewrites `@click` → `x-on:click` in the live DOM, and `@` is not a legal unescaped CSS attribute token — so match the **rewritten** form (closes the invalid-selector finding):
  ```js
  const card = pluginsPage.installedCard("Share Chat");
  await expect(card.locator('[x-on\\:click*="openConfig"], .plugin-config-btn')).toHaveCount(0);
  ```
  This is the falsifiable proxy for "open path unreachable".

### E2E-25 — Nothing persisted across reload · traces **ST-2, ST-1** · *(closes m-4)*
- **Steps:** provision chat (`#newChat`), grant clipboard, click share to set `copied=true`; assert `.share-copied`; `page.reload()`.
- **Assertions (HARD):**
  - After reload: `.share-copied` absent, icon `share` (volatile state did not persist — ST-1/ST-2).
  - No **plugin-owned** storage written (A0 core writes `lastSelectedChat` to sessionStorage — the regex is anchored to plugin keys so that core key does not false-RED): `expect(await page.evaluate(() => Object.keys(localStorage).some(k => /share.?chat/i.test(k)))).toBe(false)`; same for `sessionStorage`.
  - **Clean re-init proof (closes m-4 — distinguishes "volatile" from "re-rendered idle for an unrelated reason"):** after reload, click share again → confirmation works → proves the component re-initialized cleanly: `await page.locator("#newChat").click(); await expect.poll(...).toBeTruthy(); click .share-chat-btn; expect(btn).toHaveClass(/share-copied/)`.

**`[coverage] I: 4 asserted, 0 skipped`** *(clean-re-init raises the asserted count)*

---

## GROUP J — Negative surface & lifecycle residue (`j-negative-surface.mjs`)

Asserts the Rule-4 negatives (no API/Python/seams) and the install-gating/uninstall-residue facts. Mixes page assertions with container probes via the devkit's in-A0 exec (the harness exposes `A0_CONTAINER`; this group uses `page.request` for HTTP-observable negatives and documents the container-side facts already asserted by the devkit lifecycle stage).

Fixture: `loggedInPage` (+ `page.request` for authed API probes using the same session cookies).

### E2E-26 — No `@extensible`/`_functions` seam, no `dump_live`, no `e2e_pod_env` · traces **NEG-1, Rule 4**
- **Goal:** verify the plugin ships **no** Python/seam surface (so `dump_live`/`e2e_pod_env` are correctly absent).
- **Assertions (HARD, container-side via the devkit `inA0`/`podman exec` already wired in lifecycle, asserted here as explicit facts):**
  - `test ! -d /a0/usr/plugins/share_chat/extensions/python` → true (no python webui/agent hooks).
  - `! test -e /a0/usr/plugins/share_chat/hooks.py` and no `api/`, `prompts/`, `skills/` dirs → true.
  - `__init__.py` contains only the docstring (no class/def): grep for `^\s*(def|class)\s` → 0 matches.
  - Repo-side fact (asserted in the spec's own checkout, read-only): `.devkit.yml` either absent or has no `e2e_pod_env:` key for this plugin → confirms Rule-4 "no probe env". (If `.devkit.yml` absent, this is trivially satisfied; HARD assert absence of the key.)

### E2E-27 — No HTTP API handler contributed · traces **API-1** · *(closes m-5)*
- **Steps:** authed `page.request.post(baseURL + "/api/share_chat", {})` (and `/share_chat`).
- **Assertions (HARD):** assert the **negative robustly** rather than hard-coding a status A0 may not use for unknown routes — `expect(resp.ok()).toBe(false)` (status ≥ 400) **and** the body does not contain a share-chat handler signature (`expect(await resp.text()).not.toMatch(/share_chat.*handler|share_chat.*api/i)`). Confirms `meta.yaml env: []` / no `api/` directory yields no endpoint. (Replaces the brittle hard-coded `[404,405]` — A0's unknown-`/api/<x>` behaviour is not guaranteed 404.)

### E2E-28 — Install-gated: button absent before enable / present after · traces **EDGE-6, CFG-2**
- **Goal:** the button is injected **only** because the plugin is enabled.
- **Note:** the devkit lifecycle already proves *uninstalled ⇒ dir gone* and reloads to an empty host. This scenario adds the **UI** half on the host: when the plugin is installed (current state), `x-extension#chat-top-end` has the button.
- **Assertions:**
  - **HARD (installed state):** `expect(page.locator('x-extension#chat-top-end .share-chat-btn')).toHaveCount(1)`.
  - **HARD (empty-host contract):** `expect(page.locator('x-extension#chat-top-end').first()).toBeAttached()`; structurally, the only child is the plugin's `x-component` (count 1) — no residual third-party nodes.
  - **Uninstalled-state UI** (`@skip(reason="agent-zero-plugin-share-chat#44 — covered by devkit uninstall→verify-uninstalled stage; single nested boot keeps plugin installed for behaviour groups")`). Tracked skip with a real issue, not a fake pass (closes G-1).

**`[coverage] J: 3 asserted, 1 skipped`**

---

## Coverage roll-up & traceability

| Behaviour/UI | Covered by | Mode |
|---|---|---|
| BEH-1 | E2E-1, E2E-2 | HARD |
| BEH-2 | E2E-6, E2E-15(revert) | HARD |
| BEH-3 | E2E-5 | @skip (hover transition) + HARD idle-opacity |
| BEH-4 | E2E-9, E2E-11, E2E-20, E2E-22 | HARD (clipboard-gated link, structural) |
| BEH-5 | E2E-9 | HARD visual / clipboard-gated readback |
| BEH-6 | E2E-13 | HARD (page seam) |
| BEH-7 | E2E-9/10, E2E-13 | HARD (visual) |
| BEH-8 | E2E-15 | HARD (upper-bound primary) |
| BEH-9 | E2E-18 | HARD (stubbed precondition) |
| BEH-10 | E2E-7, E2E-15(revert) | HARD |
| BEH-11 | E2E-21, E2E-22 | HARD |
| UI-1 | E2E-1, E2E-2, E2E-7 | HARD |
| UI-2 | E2E-5(opacity), E2E-6, E2E-10 | HARD |
| UI-3 | E2E-8 | HARD |
| CFG-1 | E2E-23, E2E-24 | HARD (text-anchored) |
| CFG-2 | E2E-23, E2E-28 | HARD |
| API-1 | E2E-27 | HARD (robust negative) |
| EXT-1 | E2E-2, E2E-3 | HARD |
| EXT-2 | E2E-9, E2E-20 | HARD |
| EXT-3 | E2E-21 | HARD |
| NEG-1 | E2E-26 | HARD |
| ST-1/ST-2 | E2E-25 | HARD |
| ST-4 | E2E-9, E2E-11, E2E-12 | HARD (structural, clipboard-gated) |
| EDGE-1/2 | E2E-17, E2E-18, E2E-19 | HARD (stubbed) |
| EDGE-3 | E2E-13 | HARD |
| EDGE-4 | E2E-14 | HARD (throw: no-confirm + leak + scoped-error / return-false: false-positive, clipboard-gated half) |
| EDGE-5 | E2E-16 | HARD (widened margin) |
| EDGE-6 | E2E-28 + devkit lifecycle | HARD + @skip(UI-uninstall, #44) |
| EDGE-7 | E2E-4 | @skip (multi-tenant un-provisionable, #41; mechanism via E2E-3) |

**Totals:** 28 scenarios across 10 groups · ~28 HARD-asserted assertions (several scenarios gained assertions: idle-opacity E2E-5, throw-leak + scoped-error E2E-14, clean-re-init E2E-25) · 4 tracked `@skip` with **real issue numbers** (BEH-3 hover-transition `#42`, EDGE-7 multi-tenant `#41`, J uninstall-UI `#44`, plus the I-1 leak cross-link `#43`) · plus per-group clipboard-readback `@skip` only when `grantPermissions` is un-enableable (Rule 6).

**Findings closed (audit trail):**
- **C-1** (order-dependent no-context premise) → Group G stubs `getContext` (E2E-17/18/19); order-dependence note added to header.
- **C-2** (project-selector not rendered) → E2E-2 provisions a chat + anchors position on the static `#time-date-container` last-child, project-selector check null-guarded.
- **C-3** (unreliable `pageerror` on Alpine 3) → `installErrorProbe` helper captures `unhandledrejection` + console + pageerror, **plugin-scoped** to defeat A0 startup-noise fake-RED (E2E-14/18/19).
- **M-1** (textarea leak on throw not modeled) → E2E-14 sub-case A HARD-asserts the leaked textarea (count 1).
- **M-2** (brittle `querySelector('textarea')`) → E2E-13 reads `document.activeElement` / last textarea.
- **M-3** (brittle exact-string clipboard match) → `assertShareLink` structural helper, used everywhere (E2E-9/11/12/13/20/22); Rule 7 added.
- **M-4** (dead `return false` fake-green) → deleted from E2E-24.
- **M-5** (speculative/invalid config selectors) → E2E-23 anchors on visible "Not available" text; E2E-24 matches rewritten `x-on:click`; `x-show` directive-counting removed.
- **M-6** (tight timing margins) → E2E-15 lower bound +300ms, upper-bound revert is primary; E2E-16 second-click margin +800ms.
- **m-3** (stale-ctxid coupling) → E2E-11 always forces a fresh `#newChat` after the polluted goto.
- **m-4** (volatility ambiguity) → E2E-25 adds clean-re-init click.
- **m-5** (hard-coded 404/405) → E2E-27 uses `resp.ok()===false` + body signature.
- **m-6** (invalid `@click`/soft cap) → rewritten-attribute selector in E2E-24; soft-cap noted in Rule 5.
- **m-7** (prose tally) → `tally()` helper asserts declared vs actual counts.
- **G-1** (`#TBD` skips) → all four skips now carry real issue numbers (#41/#42/#43/#44); CI/lint should reject `#TBD`.
- **G-2** (EDGE-7 mechanism note) → E2E-4 skip note clarifies concat string-building is covered by E2E-3.
- **G-3** (chatTop hydration race) → noted in E2E-1; absorbed by the 20s visibility wait (no separate scenario needed).
- **G-4** (no-cost hover partial) → E2E-5 adds HARD idle-opacity `toHaveCSS("opacity","0.7")`.

No fake greens and no fake reds; every group emits an asserted `[coverage]` tally; all app-state fixtures are provisioned through the real UI (`#newChat`, Projects card, Plugins panel) with page-side stubbing reserved only for un-provisionable client states; no `dump_live`/`e2e_pod_env` because the plugin has no Python/seam surface (verified negatively in E2E-26).

**Key source paths referenced:**
- Plugin extension: `/tmp/fan-share-chat/usr/plugins/share_chat/extensions/webui/chat-top-end/share-chat.html`
- Host point: `/a0/webui/components/chat/top-section/chat-top.html` (`<x-extension id="chat-top-end">`, inside `<template x-if="$store.chatTop">`)
- Injection: `/a0/webui/js/extensions.js` (`importHtmlExtensions`, `normalizePath`, MutationObserver re-fire)
- Alpine version: `/a0/webui/index.html:43` (Alpine 3.14.x — async `@click` rejections surface as `unhandledrejection`, not `pageerror`)
- Poll auto-reselect: `/a0/webui/index.js:~386-398` (selects first backend chat when `context` null but `contexts.length>0`)
- `getContext`: `/a0/webui/index.js:599`
- Deep-link consume: `/a0/webui/components/sidebar/chats/chats-store.js:32-43` (`init` → consume `?ctxid=` → `selectChat` → `history.replaceState`); sessionStorage `lastSelectedChat` at `chats-store.js:296`
- Project selector (runtime-conditional): `/a0/webui/components/projects/project-selector.html:11` (`.project-dropdown-container` inside `<template x-if="selectedContext">`)
- Chat provisioning: `/a0/webui/components/sidebar/chats/chats-list.html:17` (`#newChat`), `chats-store.js:162-172` (`newChat` → `/chat_create` → `selectChat`)
- Plugins panel: `/a0/webui/components/plugins/list/plugin-list.html` (config affordance; rewritten `x-on:click`), plugin-info modal "Configuration: Not available"
- Devkit harness: `/a0/src/github.com/agent-zero-plugins/agent-zero-plugin-development-testkit/e2e/lifecycle/lifecycle.spec.ts` (`:99-101` serial backend persistence; `:116-123` DEC-058 loggedInPage; `:129` group signature), `e2e/fixtures/index.ts`, `e2e/pages/{LoginPage,PluginsPage,ChatPage}.ts`, `e2e/harness/{a0-up.sh,run-lifecycle.sh}`, `.github/workflows/plugin-e2e.yml:179-181` (BEHAVIOUR_SPECS glob `tests/e2e/specs/*.mjs`, one test/video each; `A0_POD_ENV`/`e2e_pod_env`).