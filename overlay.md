# Overlay

## What it is

`TabOverlayWindow` is a top-level window shown above all app/game windows.

- Size: 70% of screen width and 70% of screen height.
- Position: centered on screen.
- Transparency: 5% transparent (`alpha = 0.95`).
- Window chrome: hidden (`overrideredirect=True`) - no native header/title bar with close/minimize/maximize buttons.
- Lifecycle: created once during app initialization, then shown/hidden by button or hotkey.

## Layout

- Left side: menu.
- Right side: content area with vertical scrolling.
- Bottom-left: static `ADD +` button.

Menu/content behavior:

- Program button example: `MAP` (built-in program item).
- User link items: created by clicking `ADD +`.
- Selecting a user link opens image content for that link.
- Empty user link content shows centered `LOAD IMAGES` button.

## Menu rules

### Static controls

- `ADD +` is static: cannot be moved and cannot be renamed.

### Program items

- Current built-in program item: `MAP`.
- Program items do not show image gallery.
- Program items run program logic; current implementation is placeholder/stub for `MAP`.

### User link items (created via `ADD +`)

- Can be reordered with drag-and-drop in the menu.
- Can be renamed via context menu (right click on the menu item).
- Can be duplicated via context menu.
- Can be deleted via context menu.

Context menu commands for user link menu items:

- `Rename`
- `Duplicate`
- `Delete`

## Content rules for user links

- If link has no images: show `LOAD IMAGES` button.
- If link has images:
  - show all images in order (vertical list),
  - still show `LOAD IMAGES` button under the list (for adding more images).

Image interactions:

- Mouse wheel up/down on image: zoom in/out.
- Hold left mouse button and drag on image: pan (move view).

Image context menu (right click on image):

- `Up` - move image one position higher.
- `Down` - move image one position lower.
- `Delete` - remove image from current link.

## Routes (event flow)

These are internal UI event routes (not HTTP routes):

- `TAB_OVERLAY_OPEN`
  - Source: Settings tab `Open Overlay` button OR top-level `Overlay` tab `Open Overlay` button.
  - Path: `SettingsTab`/`OverlayTab` -> `BuffHUD._events` -> `Application.run()` -> `Application._toggle_tab_overlay()`.
- `TAB_OVERLAY_HOTKEY_CHANGED`
  - Source: Settings tab or top-level `Overlay` tab hotkey set/clear buttons.
  - Path: `SettingsTab`/`OverlayTab` -> `BuffHUD._events` -> `Application.run()` -> `Application._sync_overlay_hotkey()` -> `save_settings(...)`.

Overlay-local interaction routes (inside `TabOverlayWindow`, no `Application` event bus):

- `MENU_ADD_LINK`
  - Trigger: click `ADD +`.
  - Path: `ADD + button` -> `TabOverlayWindow._add_user_item()` -> menu item appended -> select new item -> content render.
- `MENU_SELECT_ITEM`
  - Trigger: left click on menu item.
  - Path: `menu button command` -> `TabOverlayWindow._select_item()` -> `TabOverlayWindow._render_content()`.
- `MENU_USER_ITEM_CONTEXT`
  - Trigger: right click on user menu item.
  - Path: `Button-3` -> `TabOverlayWindow._show_item_context_menu()` -> `Rename|Duplicate|Delete` handlers.
- `MENU_USER_ITEM_DND`
  - Trigger: drag user menu item with left mouse button.
  - Path: `ButtonPress-1/B1-Motion/ButtonRelease-1` -> drag state -> `TabOverlayWindow._apply_user_order()`.
- `LINK_LOAD_IMAGES`
  - Trigger: click `LOAD IMAGES` in user link content.
  - Path: `load button` -> `TabOverlayWindow._load_images_for_item()` -> file dialog -> append image entries -> re-render.
- `IMAGE_ZOOM`
  - Trigger: mouse wheel on image canvas.
  - Path: `MouseWheel` -> `TabOverlayWindow._on_image_wheel()` -> `TabOverlayWindow._draw_image()`.
- `IMAGE_PAN`
  - Trigger: hold left mouse + move on image canvas.
  - Path: `ButtonPress-1/B1-Motion` -> `TabOverlayWindow._start_pan()`/`TabOverlayWindow._on_pan()` -> `TabOverlayWindow._draw_image()`.
- `IMAGE_CONTEXT`
  - Trigger: right click on image canvas.
  - Path: `Button-3` -> `TabOverlayWindow._show_image_context_menu()` -> `Up|Down|Delete` -> move/delete handlers -> re-render.
- `PROGRAM_MAP_ACTION`
  - Trigger: click `Run MAP placeholder` in MAP content.
  - Path: `program action button` -> local placeholder callback (stub).

Hotkey route:

- Overlay hotkey token is read from `settings["hotkeys"]["overlay_open"]`.
- Runtime path: `Application._process_hotkeys()` -> `Application._handle_overlay_hotkey(token)` -> `Application._toggle_tab_overlay()`.

## Connections

### UI layer

- `src/ui/tabs/settings_tab.py`
  - Includes overlay controls in Settings.
- `src/ui/tabs/overlay_tab.py`
  - Dedicated top-level `Overlay` tab.
  - Contains `Open Overlay` button and hotkey controls (`Set hotkey`, `Clear hotkey`).
- `src/ui/hud.py`
  - Wires settings tab commands.
  - Wires overlay tab commands.
  - Pushes `TAB_OVERLAY_OPEN` and `TAB_OVERLAY_HOTKEY_CHANGED` events.
  - Exposes getter/setter for current overlay hotkey and syncs display in both tabs.

### Core layer

- `src/core/application.py`
  - Creates `TabOverlayWindow` in `initialize(...)`.
  - Handles overlay events in `run()`.
  - Syncs/persists hotkey to settings.
  - Handles overlay hotkey in hotkey processing and fallback polling.

### Overlay window

- `src/ui/tab_overlay_window.py`
  - Owns the top-level overlay UI.
  - Builds two-pane layout (left menu + right content).
  - Manages menu item CRUD/reordering for user links.
  - Manages image loading/list/zoom/pan/reorder/delete per link.
  - Executes program-item placeholder behavior (`MAP`).
  - API:
    - `show()`
    - `hide()`
    - `toggle()`
    - `close()`

## Config keys

Default key added in settings defaults:

```json
{
  "hotkeys": {
    "overlay_open": ["F8"]
  }
}
```

Current project settings file includes the same key: `settings.json`.
