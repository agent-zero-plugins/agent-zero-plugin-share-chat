# share-chat — E2E behaviour, in BDD

Generated for **`share_chat` v0.1.0** (Interu, Apache-2.0) — a single-file HTML UI extension at
`extensions/webui/chat-top-end/share-chat.html`. No API, no Python hooks, no `@extensible` fork
seams, no config screen. Each `Scenario` is one falsifiable assertion that runs against a live
Agent Zero instance with the plugin installed. The whole behaviour layer runs under
`test.describe.serial` against **one A0 boot**, so backend chat state created via `#newChat`
**persists** across the run — no group may assume a clean backend, and any "no context" precondition
is forced by **page-side global stubbing** (`globalThis.getContext = () => null`), never by relying on
fresh state, because A0's poll handler auto-reselects the first existing backend chat. Groups use the
**`loggedInPage`** fixture (authenticated, onboarding suppressed). `<P>` is a UI-provisioned chat
context; `baseURL` is the nested A0 origin. There is **no** `dump_live` probe and **no** `.devkit.yml
e2e_pod_env` for this plugin — it has zero Python and zero fork seams, so every behaviour is
hard-asserted directly against the live DOM (absence of the probe surface is itself verified, E2E-26).

## Hard rules (binding for this and every e2e/BDD spec in the fleet)

1. **No silent swallow.** Every scenario is a real, falsifiable assertion. Failures are recorded
   and turn the group RED — never caught-and-ignored. Each group emits a `[coverage]` tally.
2. **No fake green.** A scenario is either genuinely asserted or an explicit `@skip` with a tracked
   reason (issue link) — never a bare pass for an untested case.
3. **Self-provisioning fixtures, through the UI.** The suite creates whatever app state it needs
   (e.g. A0 projects) by driving the **real UI**, not backend/"magic" API calls. Skips for
   "needs a fixture" are not allowed once the fixture is buildable.
4. **LLM-less & hermetic.** Runtime/fork-seam behaviours are exercised via a deterministic
   pure-helper probe (`dump_live`), enabled for e2e only via `.devkit.yml e2e_pod_env`. No API key,
   no live MCP pod. A deterministic LLM stub is added only if a plugin truly needs an agent turn.
5. **≤10 grouped specs, one video each** (webm; no GIF conversion).
6. **Best-effort `try/catch` is reserved** for genuinely un-enableable env only (a real agent turn,
   OS clipboard) — anything reachable via a seam MUST hard-assert.
7. **Validated on the local fast loop** (disposable A0) before pushing; CI is the final gate.

---

## Feature: Injection & extension point  *(group 01)*

```gherkin
Background:
  Given a freshly booted Agent Zero with the share_chat plugin installed
  And I am authenticated via loggedInPage with onboarding suppressed
  And I navigate to baseURL + "/"

Scenario: Button injected and visible (E2E-1)
  # traces BEH-1, UI-1
  Given the chat-top-end HTML extension has been discovered and async-loaded
  When the chat top bar hydrates (within the 20s visibility timeout)
  Then exactly one .share-chat-btn is visible
  And its bounding box is approximately 32px square (30..34)

Scenario: Button injected into the correct region (E2E-2)
  # traces BEH-1, EXT-1, UI-1 — closes C-2
  Given I click #newChat to provision a chat through the real UI
  And globalThis.getContext() polls truthy so .project-dropdown-container renders
  When I inspect the DOM
  Then x-extension#chat-top-end .share-chat-btn is visible
  And the x-extension#chat-top-end host is the last element child of #time-date-container
  And, when present, .project-dropdown-container precedes .share-chat-btn (null-guarded, no throw)

Scenario: Wrapped as x-component, not a raw innerHTML dump (E2E-3)
  # traces EXT-1
  When I inspect x-extension#chat-top-end
  Then it contains exactly one x-component
  And its path attribute is absolute (begins "/")
  And it ends with share_chat/extensions/webui/chat-top-end/share-chat.html

@skip(reason="agent-zero-plugin-share-chat#41 — single-plugin nested A0 cannot provision a 2nd chat-top-end extension; concat string-building is covered by E2E-3, only the multi-tenant sibling case is un-provisionable; counted skipped")
Scenario: Coexistence with other chat-top-end extensions (E2E-4)
  # traces EDGE-7 — only one plugin is installed in the nested A0, so a sibling node cannot be provisioned through the UI
  Given a second, independent chat-top-end extension were also installed
  Then the share_chat button would survive the importHtmlExtensions concatenation

# [coverage] 01: 3 asserted, 1 skipped
```

---

## Feature: Idle render & tooltip  *(group 02)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"

@skip(reason="agent-zero-plugin-share-chat#42 — BEH-3 hover TRANSITION is pure CSS :hover; no JS/state to falsify; visual-only")
Scenario: Hover affordance transition (E2E-5a)
  # traces BEH-3 — opacity 0.7->1 + box-shadow on :hover, pure CSS, nothing to assert
  When I hover the button
  Then its opacity transitions toward 1 with a box-shadow

Scenario: Idle icon opacity is deterministic (E2E-5b)
  # traces BEH-3, UI-2 — no-cost falsifiable add that catches total stylesheet-injection failure; closes G-4
  When the button is idle
  Then .share-chat-btn .material-symbols-outlined has computed opacity "0.7"

Scenario: Idle icon is "share" (E2E-6)
  # traces BEH-2, UI-2
  Given the icon locator is scoped to the button (the class is not page-unique)
  When the button is idle
  Then the icon text is "share"
  And .share-chat-btn does not have class share-copied
  And the icon inline style has no "color:" rule

Scenario: Idle tooltip text (E2E-7)
  # traces BEH-10, UI-1
  When the button is idle
  Then .share-chat-btn title is "Copy link to this chat"

Scenario: A single Alpine scope owns all state (E2E-8)
  # traces UI-3
  When I inspect x-extension#chat-top-end
  Then there is exactly one [x-data] wrapper
  And that wrapper contains the single .share-chat-btn

# [coverage] 02: 4 asserted, 1 skipped
```

---

## Feature: Copy happy path & confirmation  *(group 03)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"
  And I click #newChat to provision a real backend chat context
  And globalThis.getContext() polls truthy (a real backend ctxid)
  And I grant clipboard-read/clipboard-write permissions for baseURL

Scenario: Click composes and copies the deep link (E2E-9)
  # traces BEH-4, BEH-5, EXT-2, ST-4
  Given I capture ctxid = globalThis.getContext()
  When I click .share-chat-btn
  Then the button gains class share-copied (always HARD, pure DOM)
  And, if the clipboard grant succeeded, navigator.clipboard.readText() passes assertShareLink(clip, baseURL, ctxid)
  And the clipped URL has origin === new URL(baseURL).origin, pathname "/", searchParams exactly [["ctxid", ctxid]]
  And the clipped URL matches no /(password|token|csrf|session)/i

@skip(reason="testkit#clipboard-headless — clipboard grant unavailable; the visual confirmation half stays HARD")
Scenario: Clipboard readback when grantPermissions throws (E2E-9-readback)
  # traces BEH-5 — only the OS-clipboard readback degrades (Rule 6); counted skipped per env
  Given grantPermissions threw in an un-enableable headless env
  Then the exact-link readback cannot be asserted

Scenario: Confirmation state on success (E2E-10)
  # traces BEH-7, UI-2
  When I click .share-chat-btn
  Then the icon text is "check"
  And the icon inline style contains "color: #4caf50"
  And the title flips to "Link copied!"

# [coverage] 03: 2 asserted, 1 skipped (clipboard readback env-gated)
```

---

## Feature: Link composition / param-strip variants  *(group 04)*

```gherkin
Background:
  Given the share_chat plugin is installed
  And I grant clipboard-read/clipboard-write permissions for baseURL

Scenario: Existing query params are dropped from the link (E2E-11)
  # traces BEH-4, ST-4 — closes m-3
  Given I navigate to baseURL + "/?foo=1&bar=2&ctxid=stale"
  And chats-store.init() consumes ?ctxid=stale (a bogus id)
  And I therefore force a fresh #newChat so the live ctxid is real, never "stale"
  And I capture ctxid = globalThis.getContext()
  When I click .share-chat-btn and read the clipboard
  Then assertShareLink(clip, baseURL, ctxid) passes
  And foo and bar are gone, only ctxid is present, no fragment leakage

Scenario: Link is origin+path based with no auth/session leakage (E2E-12)
  # traces ST-4 — distinct traceability row, subsumed by assertShareLink
  Given I provision a fresh #newChat and capture ctxid
  When I click .share-chat-btn and read the clipboard
  Then the clipped URL origin === new URL(baseURL).origin
  And the clipped URL matches no /(password|token|csrf|session)/i

# [coverage] 04: 2 asserted, 0 skipped (clipboard-gated)
```

---

## Feature: Fallback copy path  *(group 05)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"
  And I click #newChat to provision a real backend chat context

Scenario: writeText rejection triggers the execCommand fallback (E2E-13)
  # traces BEH-6, EDGE-3 — closes M-2; deterministic page seam (Rule 3 exception)
  Given navigator.clipboard.writeText is stubbed to reject ("forced-insecure")
  And document.execCommand("copy") is stubbed to capture document.activeElement's textarea value
  When I capture ctxid and click .share-chat-btn
  Then the captured fallback value passes assertShareLink(copied, baseURL, ctxid)
  And the transient textarea is removed afterward (textarea.share-chat-temp, body > textarea count 0)
  And confirmation is still reached (share-copied present, icon "check")

Scenario: Fallback execCommand THROWS — no false-positive, real textarea leak (E2E-14a)
  # traces EDGE-4 (I-1) — closes C-3, M-1
  Given an installErrorProbe captures plugin-scoped unhandledrejection/console/pageerror
  And navigator.clipboard.writeText rejects and document.execCommand throws "execCommand blocked"
  When I click .share-chat-btn
  Then .share-chat-btn does NOT gain class share-copied and the icon stays "share"
  And the leaked transient textarea is present (count 1) — the real defect, cross-linked to #43
  And probe.pluginErrors() length is >= 1 (the async catch-rethrow surfaces as unhandledrejection, not pageerror)

Scenario: Fallback execCommand RETURNS FALSE — silent false-positive confirmation (E2E-14b)
  # traces EDGE-4 (I-1) — the honest false-positive bug
  Given navigator.clipboard.writeText rejects and document.execCommand returns false
  When I click .share-chat-btn
  Then copied=true is shown anyway (share-copied present, icon "check") despite nothing being copied
  And, if the clipboard grant is available, a pre-seeded "SENTINEL-E14" is unchanged — proving the confirmation is decoupled from real copy

@skip(reason="testkit#clipboard-headless — readback unavailable; the false-positive VISUAL confirmation half stays HARD-asserted")
Scenario: Clipboard-truly-empty proof for the return-false path (E2E-14b-readback)
  # traces EDGE-4 — only the OS-clipboard readback half degrades per env (Rule 6)
  Given grantPermissions threw in an un-enableable headless env
  Then the sentinel-unchanged readback cannot be asserted

# [coverage] 05: 4 asserted, 1 skipped (clipboard readback env-gated)
```

---

## Feature: Confirmation auto-reset & rapid clicks  *(group 06)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"
  And I click #newChat to provision a real backend chat context
  And I grant clipboard-read/clipboard-write permissions for baseURL

Scenario: Confirmation auto-resets at ~2000 ms (E2E-15)
  # traces BEH-8 — closes M-6
  When I click .share-chat-btn
  Then immediately the button has class share-copied and the icon is "check"
  And at +300 ms share-copied is STILL present (coarse lower bound, did not reset early)
  And the confirmation reverts within a 3000 ms upper bound (primary BEH-8 assertion)
  And after revert the icon is "share" and the title is "Copy link to this chat"

Scenario: Rapid repeated clicks — the last click governs the reset (E2E-16)
  # traces EDGE-5 — closes M-6 (widened margins)
  When I click .share-chat-btn, wait ~1200 ms, then click .share-chat-btn again
  Then after the 2nd click share-copied is present
  And at 2nd-click + 800 ms (well under 2000) share-copied is STILL present — the fresh timer governs, the first click's near-expiry timer did not reset early
  And the state eventually reverts within 2500 ms — no stuck state

# [coverage] 06: 2 asserted, 0 skipped
```

---

## Feature: No-context no-op  *(group 07)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"
  # the falsy-context precondition is FORCED by page-side stubbing, never assumed from a fresh backend (serial persistence + poll auto-reselect would otherwise reselect a leftover chat) — closes C-1

Scenario: Falsy context precondition is deterministically stubbed (E2E-17)
  # traces EDGE-1 — closes C-1
  Given I call globalThis.deselectChat?.() best-effort
  And I stub globalThis.getContext = () => null so the stub OWNS the precondition
  Then globalThis.getContext() is null regardless of backend contexts.length

Scenario: Click is a silent no-op when there is no context (E2E-18)
  # traces BEH-9, EDGE-1 — closes C-1, C-3
  Given the getContext = () => null stub is in place
  And clipboard is granted and pre-seeded with "SENTINEL-G"
  And an installErrorProbe is active (plugin-scoped)
  When I click .share-chat-btn
  Then .share-chat-btn does NOT gain class share-copied, the icon stays "share", the title stays "Copy link to this chat"
  And, if the grant is available, the clipboard still reads "SENTINEL-G" (no write)
  And probe.pluginErrors() equals [] — A0 startup noise is filtered out by the plugin scope, so it cannot fake-RED this

@skip(reason="testkit#clipboard-headless — clipboard readback unavailable; the no-class/no-icon-change half stays HARD")
Scenario: No-clipboard-write proof when grant unavailable (E2E-18-readback)
  # traces BEH-9 — only the OS-clipboard half degrades per env (Rule 6)
  Given grantPermissions threw in an un-enableable headless env
  Then the SENTINEL-G unchanged readback cannot be asserted

Scenario: Undefined getContext is treated as a no-op (E2E-19)
  # traces EDGE-2 — closes C-3
  Given I delete globalThis.getContext to simulate a load-order race / API removal
  And an installErrorProbe is active (plugin-scoped)
  When I click .share-chat-btn
  Then optional chaining yields undefined and the click is a no-op (share-copied absent)
  And probe.pluginErrors() equals []

# [coverage] 07: 3 asserted, 1 skipped (clipboard readback env-gated)
```

---

## Feature: Deep-link round trip (produce ↔ consume)  *(group 08)*

```gherkin
Background:
  Given the share_chat plugin is installed and I navigate to baseURL + "/"
  And I grant clipboard-read/clipboard-write permissions for baseURL
  # the only group exercising the upstream consume half (BEH-11); the highest-value gap (I-2)

Scenario: Produce — copy a link for a known chat (E2E-20)
  # traces BEH-4, EXT-2 — closes M-3
  Given I create two chats via #newChat and record ctxids c1 and c2 (c2 active)
  When I click .share-chat-btn with c2 active and read the clipboard
  Then assertShareLink(clip, baseURL, c2) passes

Scenario: Consume — reload with ?ctxid= selects that chat and strips the param (E2E-21)
  # traces BEH-11, EXT-3
  When I navigate to baseURL + "/?ctxid=" + c1 (the other chat's link)
  Then chats-store.init() strips the param (searchParams.has("ctxid") becomes false)
  And the selected context becomes c1 (globalThis.getContext() polls to c1)
  And Alpine.store("chats").selected polls to c1

Scenario: Full round trip end-to-end (E2E-22)
  # traces BEH-4 <-> BEH-11 — closes M-3
  Given I activate c1 and click .share-chat-btn and read clip
  When I navigate the same browser to clip
  Then after load globalThis.getContext() === c1
  And the URL has no ctxid param

@skip(reason="testkit#clipboard-headless — readback unavailable; round-trip stays HARD by constructing the link from the captured ctxid, only the readback SOURCE is substituted")
Scenario: Round trip when clipboard grant unavailable (E2E-22-readback)
  # traces BEH-4 <-> BEH-11 — only the readback source degrades per env (Rule 6)
  Given grantPermissions threw in an un-enableable headless env
  Then the produced-link is derived from getContext() instead of clipboard readText

# [coverage] 08: 3 asserted, 1 skipped (clipboard readback env-gated)
```

---

## Feature: No config screen / no persistence  *(group 09)*

```gherkin
Background:
  Given the share_chat plugin is installed
  # config-availability checks use the pluginsPage fixture; persistence checks use loggedInPage

Scenario: Plugin Store row exposes no config, only a toggle (E2E-23)
  # traces CFG-1, CFG-2 — closes M-5
  Given I open the Plugins panel and locate the installed "Share Chat" card
  Then pluginsPage.isInstalled("Share Chat") is true (opt-in plugin enabled)
  And opening the card's plugin-info view shows "Configuration: Not available" (scoped to the info modal) — directly asserting has_config_screen === false
  # do NOT count [x-show*="has_config_screen"] — Alpine processes x-show at runtime, so the attribute count is an unreliable signal

Scenario: The config-open path is unreachable (E2E-24)
  # traces CFG-1 — closes M-4, M-5
  Given the dead "return false" plugin-settings-store probe has been deleted (it asserted nothing)
  When I inspect the installed "Share Chat" card
  Then it has no clickable element invoking openConfig
  And matching the Alpine-rewritten form, card.locator('[x-on\\:click*="openConfig"], .plugin-config-btn') has count 0

Scenario: Nothing is persisted across a reload (E2E-25)
  # traces ST-2, ST-1 — closes m-4
  Given I provision a chat via #newChat, grant clipboard, and click share to set copied=true
  When I reload the page
  Then .share-chat-btn no longer has class share-copied and the icon is "share" (volatile state did not persist)
  And no plugin-owned localStorage/sessionStorage key matches /share.?chat/i (core's lastSelectedChat is excluded by the plugin-anchored regex)
  And clicking share again on a fresh #newChat re-confirms — proving the component re-initialized cleanly

# [coverage] 09: 4 asserted, 0 skipped
```

---

## Feature: Negative surface & lifecycle residue  *(group 10)*

```gherkin
Background:
  Given the share_chat plugin is installed and I am authenticated (loggedInPage + page.request)
  # asserts the Rule-4 negatives (no API/Python/seams) and install-gating facts

Scenario: No @extensible/_functions seam, no dump_live, no e2e_pod_env (E2E-26)
  # traces NEG-1, Rule 4 — container-side facts via the devkit in-A0 exec, asserted explicitly here
  Then /a0/usr/plugins/share_chat/extensions/python does not exist
  And there is no hooks.py and no api/, prompts/, skills/ directories
  And __init__.py contains only a docstring — grep "^\s*(def|class)\s" yields 0 matches
  And .devkit.yml is absent OR has no e2e_pod_env key for this plugin (Rule-4 "no probe env")

Scenario: No HTTP API handler is contributed (E2E-27)
  # traces API-1 — closes m-5
  When I POST (authed) to baseURL + "/api/share_chat" and baseURL + "/share_chat"
  Then resp.ok() is false (status >= 400) — robust negative, not a hard-coded 404/405
  And the body does not match /share_chat.*handler|share_chat.*api/i — confirming meta.yaml env:[] yields no endpoint

Scenario: Install-gated — button present because the plugin is enabled (E2E-28)
  # traces EDGE-6, CFG-2
  When I inspect the host with the plugin installed (current state)
  Then x-extension#chat-top-end .share-chat-btn has count 1
  And x-extension#chat-top-end is attached and its only child is the plugin's x-component (count 1) — no residual third-party nodes

@skip(reason="agent-zero-plugin-share-chat#44 — uninstalled-state UI is covered by the devkit uninstall->verify-uninstalled stage; the single nested boot keeps the plugin installed for behaviour groups")
Scenario: Button absent in the uninstalled state (E2E-28-uninstall)
  # traces EDGE-6 — the uninstall UI half is owned by the devkit lifecycle.spec.ts, not this behaviour layer
  Given the plugin were uninstalled
  Then x-extension#chat-top-end would render with no .share-chat-btn

# [coverage] 10: 3 asserted, 1 skipped
```

---

## Tracked skips (explicitly not-covered, not silently passed)

```gherkin
@multi-tenant     E2E-4   coexistence w/ a 2nd chat-top-end extension -> #41 (un-provisionable in single-plugin nested A0; mechanism via E2E-3)
@css-only         E2E-5a  hover TRANSITION (opacity/box-shadow)        -> #42 (pure CSS :hover; idle-opacity E2E-5b is HARD)
@i-1-defect       E2E-14a leaked-textarea cross-link                   -> #43 (asserted HARD here; tracked as a real plugin defect)
@devkit-lifecycle E2E-28-uninstall  uninstalled-state UI              -> #44 (owned by uninstall->verify-uninstalled stage)
@env-gated        E2E-9/14b/18/22 clipboard READBACK halves           -> testkit#clipboard-headless (Rule 6; only when grantPermissions is un-enableable; visual/DOM halves stay HARD)
```
