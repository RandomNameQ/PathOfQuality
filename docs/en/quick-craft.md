# Quick Craft

**English** | [Русский](../ru/quick-craft.md)

## Overview
Summons currency overlays near the cursor and performs a rapid right-click on the source item followed by a left-click back at the cursor — all in a single action without stealing focus.

## Setup
1. In **Tools → Currency**, add entries with the required image, capture bounds, and activation state.
2. In **Tools → Quick Craft**, assign a global hotkey, position overlay templates using the center guide, and save the layout.
3. (Optional) Add your game executable to `assets/allowed_processes.json` to restrict execution to the focused game window.

## Usage
- Press the global hotkey to spawn the overlays near the cursor.
- Click a currency overlay once to run the quick craft interaction immediately.

## Tips
- Overlays remain hidden from Alt-Tab and the taskbar, and they never activate windows.
- Works while the game is focused; if focus gating is disabled, it also works while the app window is active.
