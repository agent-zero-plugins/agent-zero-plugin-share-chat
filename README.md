# Share Chat Plugin for Agent Zero

Adds a **share button** to the top-right of the chat area that copies a deep link to the current conversation to the clipboard.

## Features

- Single icon button in the chat top bar (uses the `chat-top-end` extension point)
- Generates a deep link with `?ctxid=<chat-id>` parameter
- Copies to clipboard with one click
- Visual feedback: icon changes to a checkmark for 2 seconds after copying
- Works in both HTTPS and non-HTTPS contexts (clipboard API with fallback)

## Installation

Copy the `share_chat/` directory to your Agent Zero plugins folder:

```
/a0/usr/plugins/share_chat/
```

Enable the plugin via the Agent Zero settings UI, or create a `.toggle-1` file:

```bash
touch /a0/usr/plugins/share_chat/.toggle-1
```

## How it works

When you click the share button, the plugin:

1. Reads the current chat's context ID via `getContext()`
2. Builds a URL: `<origin>?ctxid=<context-id>`
3. Copies it to the clipboard
4. Shows a brief checkmark confirmation

Anyone with access to the Agent Zero instance can open the link to navigate directly to that chat.

## License

Apache-2.0
