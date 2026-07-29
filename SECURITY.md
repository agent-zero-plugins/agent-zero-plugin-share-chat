# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Instead use
[GitHub private vulnerability reporting](https://github.com/agent-zero-plugins/agent-zero-plugin-share-chat/security/advisories/new)
on this repository, or contact the maintainers at `hello@interu.ai`. We aim to acknowledge
reports within 7 days.

## Threat model — what a "share link" actually is

This plugin composes a URL of the form:

```
<your-a0-origin>/?ctxid=<chat-context-id>
```

and copies it to the clipboard. Being honest about the security properties:

### What the link does NOT do

- **It is not a capability/bearer token.** The `ctxid` grants no access by itself. A recipient
  must (a) have network reachability to your Agent Zero instance and (b) pass its
  authentication (login / auth proxy). Unauthenticated visitors land on the login screen.
- **It is not a public share page.** There is no anonymous read-only render, no proxy, no
  third-party service. The plugin has zero backend and stores nothing.
- **Nothing leaves your machine on click.** Link composition and the clipboard write are
  entirely client-side (`navigator.clipboard`, with a hidden-textarea `execCommand` fallback).

### What you SHOULD consider before pasting a link somewhere

- **Token entropy / guessability of `ctxid`:** Agent Zero chat context ids are short
  (~8 char) random ids generated client- or server-side. They are identifiers, **not**
  secrets — Agent Zero's security boundary is its authentication layer, not ctxid secrecy.
  Anyone already authenticated to the *same* instance could enumerate or guess chat ids;
  the plugin does not change that pre-existing property.
- **Exposure surface = your instance's exposure.** If your A0 instance is exposed on a LAN or
  the internet without auth, the link points anyone straight at your conversation. That risk
  exists with or without this plugin — the plugin just makes the URL easier to produce.
  Run A0 behind authentication (built-in login, reverse-proxy auth, VPN).
- **The URL itself leaks metadata.** A pasted link reveals your instance origin (hostname/port)
  and one chat id to whoever can read the paste destination (chat logs, issue trackers).
  Treat links like you treat internal URLs.
- **Clipboard is a shared surface.** Anything on the clipboard can be read by other local
  applications with clipboard access. The confirmation state ("Link copied!") auto-reverts
  after ~2s but the clipboard content persists until overwritten.

### Design mitigations in this plugin

- No secrets embedded in links; existing query params are stripped before `ctxid` is set
  (prevents accidentally re-sharing tokens that were in your current URL).
- No-op when no chat is selected (`getContext()` falsy → return).
- No network calls, no storage, no server-side component — the audit surface is a single
  ~150-line declarative HTML file: `usr/plugins/share_chat/extensions/webui/chat-top-end/share-chat.html`.

## Supported versions

Only the latest released version receives security fixes.
