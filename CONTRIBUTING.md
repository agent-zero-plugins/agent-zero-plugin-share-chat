# Contributing to Share Chat

Thanks for helping improve the plugin! This repo follows the
[agent-zero-plugins devkit v2](https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit)
conventions — most of the tooling below ships from the `tests/_testkit` submodule.

## Getting set up

```bash
git clone --recursive https://github.com/agent-zero-plugins/agent-zero-plugin-share-chat.git
cd agent-zero-plugin-share-chat
pip install pytest pyyaml
```

If you cloned without `--recursive`, run `git submodule update --init --recursive`.

## Repo layout

| Path | What |
|---|---|
| `usr/plugins/share_chat/` | The plugin itself (manifests + one HTML extension) |
| `docs/spec/` | Behaviour contract (BEH-N), implementation plan, e2e spec docs |
| `tests/component/` | L1 shape suite (testkit assertions, fast, no A0 boot) |
| `tests/e2e/features/` + `tests/e2e/steps/` | Behaviour-first BDD (Gherkin + Playwright steps) |
| `tests/_testkit/` | Devkit submodule — runner, gates, shared steps. Do not edit here; PR the devkit repo. |

## Workflow

1. **Branch** from `main`.
2. **Change behaviour? Update the contract.** Any user-visible change must update
   `docs/spec/behaviour-spec.md` (add/modify a `BEH-N`) and the matching scenario in
   `tests/e2e/features/` — the traceability gate enforces this.
3. **Keep Gherkin pure.** Feature files describe behaviour in domain language — no selectors,
   DOM ids, store names, or API calls (the feature-purity gate rejects them). Implementation
   detail lives in `tests/e2e/steps/`.
4. **Run the gates locally before pushing:**

   ```bash
   pytest tests/component -v   # L1 shape suite
   make verify                 # Tier-1 static BDD gates
   make bdd-e2e                # full local e2e (boots a disposable nested A0)
   ```

5. **Open a PR.** CI runs `plugin-e2e` (lint → seam-off red-proof → BDD e2e). Green CI +
   review is required; the publish gate refuses to ship a commit whose `plugin-e2e` was red.

## Rules of the road

- **No fake green.** Never wrap an assertion in `try/catch` to pass, never add a bare `@skip`
  — skips need a tracked issue link.
- **Version bumps:** keep `usr/plugins/share_chat/plugin.yaml` and `meta.yaml` versions in
  sync.
- **License:** contributions are accepted under [Apache-2.0](LICENSE).
- **No secrets** — this plugin has no credentials and it must stay that way. CI and the
  static validator scan for committed secrets.

## Reporting bugs / requesting features

Use the issue templates. For security problems see [SECURITY.md](SECURITY.md) — do not open
a public issue.
