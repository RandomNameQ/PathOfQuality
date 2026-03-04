"""
Main application logic and event loop.
"""

import os
import threading
import sys
import json
import subprocess
import cv2
import time
from typing import Dict, List, Optional, Set, Tuple
from src.capture.mss_capture import MSSCapture
from src.capture.base_capture import Region
from src.detector.template_matcher import TemplateMatcher
from src.detector.library_matcher import LibraryMatcher
from src.ui.hud import BuffHUD
from src.ui.icon_mirrors import IconMirrorsOverlay
from src.ui.overlay import OverlayHighlighter
from src.ui.tab_overlay_window import TabOverlayWindow
from src.ui.currency_overlay import CurrencyOverlay
from src.ui.roi_selector import select_roi
from src.ui.tray import TrayIcon
from src.utils.settings import (
    load_settings,
    load_works_config,
    save_settings,
    resource_path,
)
from src.i18n.locale import t, get_lang
from src.currency.library import load_currencies
from src.quickcraft.library import (
    load_global_source_settle_delay_s,
    load_positions as load_quickcraft_positions,
    save_positions as save_quickcraft_positions,
    load_global_hotkey,
)

ALLOWED_PROCESSES_FILE = resource_path(os.path.join("assets", "allowed_processes.json"))
WORKS_CONFIG_FILE = "works.json"
DEFAULT_QUICKCRAFT_SOURCE_SETTLE_DELAY_S = 0.1

# Windows API for checking active process and mouse simulation
if sys.platform.startswith("win"):
    import ctypes
    from ctypes import wintypes
    import win32api
    import win32con
    import win32clipboard
    from src.quickcraft.hotkeys import HotkeyListener, normalize_hotkey_name
    from src.qol.mouse_listener import MouseListener
    from src.qol.wasd_controller import WasdController

    try:
        from src.qol.quick_mouse_listener import QuickMouseListener
    except Exception:
        QuickMouseListener = None  # type: ignore

    # Define ULONG_PTR type with fallback for environments where wintypes lacks it
    try:
        ULONG_PTR = wintypes.ULONG_PTR  # type: ignore[attr-defined]
    except AttributeError:
        # Determine pointer size to choose correct underlying type
        ULONG_PTR = (
            ctypes.c_ulonglong
            if ctypes.sizeof(ctypes.c_void_p) == 8
            else ctypes.c_ulong
        )

    # Define SendInput structures
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class INPUT(ctypes.Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        _anonymous_ = ("_input",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("_input", _INPUT),
        ]

    # Constants for SendInput
    INPUT_MOUSE = 0
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MOVE = 0x0001

    # Load SendInput function
    SendInput = ctypes.windll.user32.SendInput
    SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    SendInput.restype = wintypes.UINT
else:
    HotkeyListener = None  # type: ignore
    WasdController = None  # type: ignore

    def normalize_hotkey_name(name: str) -> str:  # type: ignore
        return ""


def get_foreground_process_name() -> Optional[str]:
    """Get the name of the process that owns the foreground window."""
    if not sys.platform.startswith("win"):
        return None

    try:
        # Get foreground window handle
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return None

        # Get process ID from window handle
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

        # Open process to get executable name
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, process_id.value
        )

        if not h_process:
            return None

        try:
            # Get executable path
            exe_path = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                h_process, 0, exe_path, ctypes.byref(size)
            ):
                # Extract filename from path
                full_path = exe_path.value
                return os.path.basename(full_path)
        finally:
            ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception:
        pass

    return None


class Application:
    """Main application controller."""

    def __init__(self, settings_path: str = "settings.json"):
        """
        Initialize application.

        Args:
            settings_path: Path to settings file
        """
        self.settings_path = settings_path
        self.settings = load_settings(settings_path)
        # Allowed processes are defined strictly in JSON (no implicit additions)
        self.allowed_processes: Set[str] = self._load_allowed_processes()
        self._focus_required = bool(self.settings.get("require_game_focus", True))
        self._works_config = load_works_config(WORKS_CONFIG_FILE)
        raw_bypass = self._works_config.get("bypass_when_focus_required", {})
        self._works_bypass: Dict[str, bool] = {}
        if isinstance(raw_bypass, dict):
            for key, value in raw_bypass.items():
                self._works_bypass[str(key)] = bool(value)
        try:
            grace_ms = float(self._works_config.get("dock_interaction_grace_ms", 350))
        except Exception:
            grace_ms = 350.0
        self._dock_interaction_grace_s = max(0.0, grace_ms / 1000.0)
        self._self_process_names: Set[str] = self._get_self_process_names()
        self._last_allowed_focus_ts: float = 0.0

        # Initialize components
        self.capture: MSSCapture = None
        self.matcher: TemplateMatcher = None
        self.lib_matcher: LibraryMatcher = None
        self.hud: BuffHUD = None
        self.overlay: OverlayHighlighter = None
        self.mirrors: IconMirrorsOverlay = None
        self.currency_overlay: CurrencyOverlay = None
        self.tab_overlay: Optional[TabOverlayWindow] = None
        self.tray: TrayIcon = None

        # State
        self.roi: Region = None
        self.last_found: List[str] = []
        self.overlay_enabled_last = False
        self.positioning_enabled_last = False
        self._scan_user_requested = False
        self._copy_user_requested = False
        self._currency_positioning_requested = False
        self._currency_positioning_enabled = False
        self._quickcraft_positions: Dict[str, Dict[str, object]] = (
            load_quickcraft_positions()
        )
        self._quickcraft_hotkey_map: Dict[str, str] = {}
        self._quickcraft_global_hotkey: str = ""
        self._quickcraft_source_settle_delay_s: float = (
            self._load_quickcraft_source_settle_delay_s(migrate_legacy=True)
        )
        self._quickcraft_runtime_active: Optional[str] = None
        self._quickcraft_runtime_active_ids: Set[str] = set()
        self._currencies_cache: List[Dict] = []
        self._hotkeys = (
            HotkeyListener()
            if sys.platform.startswith("win") and HotkeyListener is not None
            else None
        )
        self._mouse: Optional[MouseListener] = (
            MouseListener() if sys.platform.startswith("win") else None
        )
        self._mouse_clicks = (
            QuickMouseListener()
            if sys.platform.startswith("win")
            and "QuickMouseListener" in globals()
            and QuickMouseListener is not None
            else None
        )
        self._focus_state_last: Optional[bool] = None
        self._last_allowed_hwnd = None

        self._wasd_toggle_lock = threading.Lock()
        self._wasd_toggle_requests = 0
        self._triple_ctrl_click_enabled = bool(
            self.settings.get("triple_ctrl_click_enabled", False)
        )
        self._triple_ctrl_click_active = False
        self._wasd_cfg = self.settings.get("wasd", {})
        if not self._wasd_cfg:
            self._wasd_cfg = {"enabled": bool(self.settings.get("wasd_enabled", False))}
        self._wasd_enabled = bool(self._wasd_cfg.get("enabled", False))
        self._wasd_top = int(self._wasd_cfg.get("top_offset", 0))
        self._wasd_bot = int(self._wasd_cfg.get("bot_offset", 0))
        self._wasd_left = int(self._wasd_cfg.get("left_offset", 0))
        self._wasd_right = int(self._wasd_cfg.get("right_offset", 0))
        self._wasd_center_offset_x = int(
            self._wasd_cfg.get("center_offset_x", self._wasd_right - self._wasd_left)
        )
        self._wasd_center_offset_y = int(
            self._wasd_cfg.get("center_offset_y", self._wasd_bot - self._wasd_top)
        )
        self._wasd_move_offset_pixels = max(
            0,
            int(self._wasd_cfg.get("move_offset_pixels", 100)),
        )
        self._wasd_enable_skill_cursor = bool(
            self._wasd_cfg.get("enable_skill_cursor", False)
        )
        self._wasd_distance_skill = max(0, int(self._wasd_cfg.get("distance_skill", 0)))
        self._wasd_skill_cursor_delay_s = max(
            0.0,
            float(self._wasd_cfg.get("skill_cursor_delay_s", 0.0)),
        )
        self._wasd_input_delay_s = max(
            0.0,
            float(self._wasd_cfg.get("input_delay_s", 0.0)),
        )
        self._wasd_movement_keys, self._wasd_toggle_hotkey = (
            self._get_wasd_hotkey_config(self.settings.get("hotkeys", {}))
        )
        self._wasd_movement_hint = self._format_wasd_movement_hint(
            self._wasd_movement_keys
        )
        self._wasd_toggle_hint = self._format_hotkey_tokens(self._wasd_toggle_hotkey)
        self._overlay_open_sequence, self._overlay_open_interval_s = (
            self._get_overlay_open_trigger_config(self.settings.get("hotkeys", {}))
        )
        self._overlay_open_hotkey = (
            self._overlay_open_sequence[0] if self._overlay_open_sequence else ""
        )
        self._overlay_sequence_progress = 0
        self._overlay_sequence_last_time = 0.0
        hotkeys_cfg = self.settings.setdefault("hotkeys", {})
        hotkeys_cfg["wasd"] = dict(self._wasd_movement_keys)
        hotkeys_cfg["tool_wasd_toggle"] = list(self._wasd_toggle_hotkey)
        hotkeys_cfg["overlay_open"] = (
            [self._overlay_open_hotkey] if self._overlay_open_hotkey else []
        )
        hotkeys_cfg["overlay_open_sequence"] = list(self._overlay_open_sequence)
        hotkeys_cfg["overlay_open_interval_s"] = float(self._overlay_open_interval_s)
        self._wasd_controller = (
            WasdController(
                is_target_active=self._is_wasd_target_active,
                offset_pixels=self._wasd_move_offset_pixels,
                enable_skill_cursor=self._wasd_enable_skill_cursor,
                distance_skill_percent=self._wasd_distance_skill,
                skill_cursor_delay_s=self._wasd_skill_cursor_delay_s,
                input_delay_s=self._wasd_input_delay_s,
                on_toggle=self._handle_wasd_toggle,
                movement_keys=self._wasd_movement_keys,
                toggle_hotkey=self._wasd_toggle_hotkey,
            )
            if sys.platform.startswith("win") and WasdController is not None
            else None
        )
        self._ctrl_press_count: int = 0
        self._last_ctrl_press_time: float = 0.0
        self._ctrl_prev_held: bool = False
        self._last_ctrl_hotkey_time: float = 0.0
        self._register_quickcraft_hotkeys()
        # Fallback polling state for when LL hooks are unavailable
        self._key_down_state: Dict[str, bool] = {}
        self._key_last_emit: Dict[str, float] = {}
        self._anchor_at_hotkey: Optional[tuple[int, int]] = None
        self._last_click_time: float = 0.0
        self._pending_click_currency_id: Optional[str] = None
        self._last_clipboard_map_name: str = ""
        # Mega QoL settings
        mq = self.settings.get("mega_qol", {}) or {}
        self._mega_qol_enabled: bool = bool(mq.get("wheel_down_enabled", False))
        self._mega_qol_seq_str: str = str(mq.get("wheel_down_sequence", "1,2,3,4"))
        try:
            self._mega_qol_delay_ms: int = int(mq.get("wheel_down_delay_ms", 50))
        except Exception:
            self._mega_qol_delay_ms = 50
        # Wheel burst suppression: emit once per scroll burst, rearm after 50ms of silence
        self._mega_qol_suppress: bool = False
        self._mega_qol_last_wheel: float = 0.0
        fd = self.settings.get("fast_destroy", {}) or {}
        self._fast_destroy_enabled: bool = bool(fd.get("enabled", False))
        self._fast_destroy_warning_overlay: bool = bool(fd.get("warning_overlay", True))
        self._fast_destroy_activation_hotkey: List[str] = self._parse_sequence_tokens(
            fd.get("activation_hotkey", ["ALT", "ALT"])
        )
        if not self._fast_destroy_activation_hotkey:
            self._fast_destroy_activation_hotkey = ["ALT", "ALT"]
        self._fast_destroy_deactivation_hotkey: List[str] = self._parse_sequence_tokens(
            fd.get("deactivation_hotkey", ["ALT"])
        )
        if not self._fast_destroy_deactivation_hotkey:
            self._fast_destroy_deactivation_hotkey = ["ALT"]
        self._fast_destroy_activation_hint = self._format_hotkey_tokens(
            self._fast_destroy_activation_hotkey
        )
        self._fast_destroy_deactivation_hint = self._format_hotkey_tokens(
            self._fast_destroy_deactivation_hotkey
        )
        self._fast_destroy_activation_interval_s: float = max(
            0.01,
            float(fd.get("activation_interval_s", 0.3)),
        )
        self._fast_destroy_chat_open_delay_s: float = max(
            0.0,
            float(fd.get("chat_open_delay_s", 0.01)),
        )
        self._fast_destroy_command_input_delay_s: float = max(
            0.0,
            float(fd.get("command_input_delay_s", 0.01)),
        )
        self._fast_destroy_command_submit_delay_s: float = max(
            0.0,
            float(fd.get("command_submit_delay_s", 0.01)),
        )
        self._fast_destroy_mode_active: bool = False
        self._fast_destroy_last_alt_press_time: float = 0.0
        self._fast_destroy_prev_lmb: bool = False
        self._fast_destroy_overlay_win = None
        self._fast_destroy_overlay_label = None
        self.settings.setdefault("fast_destroy", {})
        self.settings["fast_destroy"].update(
            {
                "enabled": self._fast_destroy_enabled,
                "warning_overlay": self._fast_destroy_warning_overlay,
                "activation_hotkey": list(self._fast_destroy_activation_hotkey),
                "deactivation_hotkey": list(self._fast_destroy_deactivation_hotkey),
                "activation_interval_s": float(
                    self._fast_destroy_activation_interval_s
                ),
                "chat_open_delay_s": float(self._fast_destroy_chat_open_delay_s),
                "command_input_delay_s": float(
                    self._fast_destroy_command_input_delay_s
                ),
                "command_submit_delay_s": float(
                    self._fast_destroy_command_submit_delay_s
                ),
            }
        )
        # Focus-loss debounce for runtime overlays
        self._focus_loss_started: float = 0.0

    def _is_feature_allowed(
        self, feature_key: str, game_in_focus: Optional[bool] = None
    ) -> bool:
        """Return True when a feature may run under focus policy + works.json."""
        if not self._focus_required:
            return True
        if game_in_focus is None:
            game_in_focus = self._is_allowed_process_active()
        if game_in_focus:
            return True
        return bool(self._works_bypass.get(feature_key, False))

    def _has_effective_focus(
        self, feature_key: str = "scan", game_in_focus: Optional[bool] = None
    ) -> bool:
        return self._is_feature_allowed(feature_key, game_in_focus)

    def _is_wasd_target_active(self) -> bool:
        game_in_focus = self._is_allowed_process_active()
        if not self._is_feature_allowed("wasd_controller", game_in_focus):
            return False
        if not game_in_focus:
            return True
        if sys.platform.startswith("win"):
            try:
                foreground_hwnd = ctypes.windll.user32.GetForegroundWindow()
                if (
                    foreground_hwnd
                    and self._last_allowed_hwnd
                    and int(foreground_hwnd) == int(self._last_allowed_hwnd)
                ):
                    return True
            except Exception:
                pass
        return game_in_focus

    def _handle_wasd_toggle(self) -> None:
        with self._wasd_toggle_lock:
            self._wasd_toggle_requests += 1

    def _consume_wasd_toggle_requests(self) -> int:
        with self._wasd_toggle_lock:
            count = int(self._wasd_toggle_requests)
            self._wasd_toggle_requests = 0
        return count

    def _do_wasd_toggle(self, game_in_focus: Optional[bool] = None) -> None:
        if not self._is_feature_allowed("wasd_controller", game_in_focus):
            return
        self._wasd_enabled = not self._wasd_enabled
        self.hud.set_wasd_enabled(self._wasd_enabled)
        self._wasd_cfg["enabled"] = self._wasd_enabled
        self.settings["wasd"] = self._wasd_cfg
        save_settings(self.settings_path, self.settings)
        if self._wasd_controller is not None:
            self._wasd_controller.set_enabled(self._wasd_enabled)
            self._start_wasd_controller()

    def _normalize_hotkey_token(self, token: object) -> str:
        token_text = str(token or "").strip().replace("-", "_")
        normalized = normalize_hotkey_name(token_text)
        if normalized:
            return normalized
        return token_text.upper()

    def _get_wasd_hotkey_config(
        self, hotkeys_cfg: dict
    ) -> Tuple[Dict[str, str], List[str]]:
        defaults = {
            "up": "W",
            "left": "A",
            "down": "S",
            "right": "D",
        }
        movement_raw = (
            hotkeys_cfg.get("wasd", {}) if isinstance(hotkeys_cfg, dict) else {}
        )
        movement: Dict[str, str] = {}
        for direction, fallback in defaults.items():
            candidate = fallback
            if isinstance(movement_raw, dict):
                candidate = movement_raw.get(direction, fallback)
            normalized = self._normalize_hotkey_token(candidate)
            if not normalized:
                normalized = fallback
            movement[direction] = normalized

        toggle_raw = (
            hotkeys_cfg.get("tool_wasd_toggle", ["GRAVE"])
            if isinstance(hotkeys_cfg, dict)
            else ["GRAVE"]
        )
        if isinstance(toggle_raw, str):
            toggle_items = [
                part.strip()
                for part in toggle_raw.replace("+", " ").replace(",", " ").split()
                if part.strip()
            ]
        elif isinstance(toggle_raw, list):
            toggle_items = [
                str(item).strip() for item in toggle_raw if str(item).strip()
            ]
        else:
            toggle_items = []

        toggle: List[str] = []
        for token in toggle_items:
            normalized = self._normalize_hotkey_token(token)
            if normalized:
                toggle.append(normalized)
        if not toggle:
            toggle = ["GRAVE"]

        return movement, toggle

    def _format_hotkey_tokens(self, tokens: List[str]) -> str:
        names = {
            "SHIFT": "Shift",
            "CTRL": "Ctrl",
            "CONTROL": "Ctrl",
            "ALT": "Alt",
            "GRAVE": "~",
            "TILDE": "~",
            "OEM_3": "~",
        }
        parts = []
        for token in tokens:
            key = str(token or "").strip().upper()
            if not key:
                continue
            parts.append(names.get(key, key))
        return "+".join(parts) if parts else "~"

    def _format_wasd_movement_hint(self, movement: Dict[str, str]) -> str:
        up = movement.get("up", "W")
        left = movement.get("left", "A")
        down = movement.get("down", "S")
        right = movement.get("right", "D")
        return f"{up}/{left}/{down}/{right}"

    def _get_single_hotkey_token(self, raw_value: object, fallback: str = "") -> str:
        if isinstance(raw_value, str):
            items = [raw_value]
        elif isinstance(raw_value, list):
            items = [str(item) for item in raw_value]
        else:
            items = []

        for item in items:
            normalized = self._normalize_hotkey_token(item)
            if normalized:
                return normalized

        return self._normalize_hotkey_token(fallback)

    def _sync_overlay_hotkey(self) -> None:
        token = self._normalize_hotkey_token(self.hud.get_overlay_hotkey())
        self._overlay_open_sequence = [token] if token else []
        self._overlay_open_hotkey = token
        self._overlay_sequence_progress = 0
        self._overlay_sequence_last_time = 0.0
        self.hud.set_overlay_hotkey(token)
        hotkeys_cfg = self.settings.setdefault("hotkeys", {})
        hotkeys_cfg["overlay_open"] = [token] if token else []
        hotkeys_cfg["overlay_open_sequence"] = list(self._overlay_open_sequence)
        hotkeys_cfg["overlay_open_interval_s"] = float(self._overlay_open_interval_s)
        save_settings(self.settings_path, self.settings)

    def _toggle_tab_overlay(self, game_in_focus: Optional[bool] = None) -> None:
        if self.tab_overlay is None:
            return
        if not self._is_feature_allowed("tab_overlay", game_in_focus):
            try:
                self.tab_overlay.hide()
            except Exception:
                pass
            return
        self.tab_overlay.toggle()

    def _get_overlay_open_trigger_config(
        self, hotkeys_cfg: dict
    ) -> Tuple[List[str], float]:
        fallback_sequence = ["SHIFT", "SHIFT"]
        fallback_interval_s = 0.1

        if not isinstance(hotkeys_cfg, dict):
            return fallback_sequence, fallback_interval_s

        raw_sequence = hotkeys_cfg.get("overlay_open_sequence")
        sequence: List[str] = []
        if isinstance(raw_sequence, list):
            for token in raw_sequence:
                normalized = self._normalize_hotkey_token(token)
                if normalized:
                    sequence.append(normalized)
        elif isinstance(raw_sequence, str):
            for part in raw_sequence.replace("+", " ").replace(",", " ").split():
                normalized = self._normalize_hotkey_token(part)
                if normalized:
                    sequence.append(normalized)

        if not sequence:
            single = self._get_single_hotkey_token(
                hotkeys_cfg.get("overlay_open", fallback_sequence),
                fallback=fallback_sequence[0],
            )
            if single:
                sequence = [single]
            else:
                sequence = list(fallback_sequence)

        try:
            interval_s = float(
                hotkeys_cfg.get("overlay_open_interval_s", fallback_interval_s)
            )
        except Exception:
            interval_s = fallback_interval_s
        interval_s = max(0.01, interval_s)

        return sequence, interval_s

    def _handle_overlay_hotkey(
        self, token: str, game_in_focus: Optional[bool] = None
    ) -> bool:
        sequence = self._overlay_open_sequence
        if not sequence:
            return False

        now = time.time()
        if self._overlay_sequence_progress > 0:
            if (now - self._overlay_sequence_last_time) > self._overlay_open_interval_s:
                self._overlay_sequence_progress = 0

        expected = sequence[self._overlay_sequence_progress]
        if token == expected:
            self._overlay_sequence_progress += 1
            self._overlay_sequence_last_time = now
            if self._overlay_sequence_progress >= len(sequence):
                self._overlay_sequence_progress = 0
                self._overlay_sequence_last_time = 0.0
                self._toggle_tab_overlay(game_in_focus)
                return True
            return False

        if token == sequence[0]:
            self._overlay_sequence_progress = 1
            self._overlay_sequence_last_time = now
            return False

        self._overlay_sequence_progress = 0
        self._overlay_sequence_last_time = 0.0
        return False

    def _open_settings_location(self) -> None:
        folder = os.path.dirname(os.path.abspath(self.settings_path))
        if not folder:
            folder = os.getcwd()
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            print(f"[Config] Failed to open settings folder: {exc}")

    def _show_notification(self, text: str, bg_color: str) -> None:
        if hasattr(self, "_notif_win") and self._notif_win:
            self._notif_win.destroy()
            if hasattr(self, "_notif_timer") and self._notif_timer:
                self.root.after_cancel(self._notif_timer)

        import tkinter as tk

        self._notif_win = tk.Toplevel(self.root)
        self._notif_win.overrideredirect(True)
        self._notif_win.attributes("-topmost", True)
        self._notif_win.geometry("+20+20")
        self._notif_win.configure(bg=bg_color)
        lbl = tk.Label(
            self._notif_win,
            text=text,
            bg=bg_color,
            fg="black",
            font=("Arial", 16, "bold"),
            padx=10,
            pady=5,
        )
        lbl.pack()

        def hide():
            if self._notif_win:
                self._notif_win.destroy()
                self._notif_win = None

        self._notif_timer = self.root.after(1500, hide)

    def _apply_wasd_config(self, cfg: dict) -> None:
        self._wasd_enabled = bool(cfg.get("enabled", False))
        self._wasd_top = int(cfg.get("top_offset", 0))
        self._wasd_bot = int(cfg.get("bot_offset", 0))
        self._wasd_left = int(cfg.get("left_offset", 0))
        self._wasd_right = int(cfg.get("right_offset", 0))
        self._wasd_center_offset_x = int(
            cfg.get("center_offset_x", self._wasd_right - self._wasd_left)
        )
        self._wasd_center_offset_y = int(
            cfg.get("center_offset_y", self._wasd_bot - self._wasd_top)
        )
        self._wasd_move_offset_pixels = max(
            0,
            int(cfg.get("move_offset_pixels", 100)),
        )
        self._wasd_enable_skill_cursor = bool(cfg.get("enable_skill_cursor", False))
        self._wasd_distance_skill = max(0, int(cfg.get("distance_skill", 0)))
        self._wasd_skill_cursor_delay_s = max(
            0.0,
            float(cfg.get("skill_cursor_delay_s", 0.0)),
        )
        self._wasd_input_delay_s = max(0.0, float(cfg.get("input_delay_s", 0.0)))

        if self._wasd_controller:
            self._wasd_controller.set_enabled(self._wasd_enabled)
            self._wasd_controller.set_center_offset(
                self._wasd_center_offset_x,
                self._wasd_center_offset_y,
            )
            self._wasd_controller.set_move_offset_pixels(self._wasd_move_offset_pixels)
            self._wasd_controller.set_skill_cursor_config(
                self._wasd_enable_skill_cursor,
                self._wasd_distance_skill,
                self._wasd_skill_cursor_delay_s,
                self._wasd_input_delay_s,
            )
            self._start_wasd_controller()

    def _start_wasd_controller(self) -> None:
        if self._wasd_controller is None:
            return
        try:
            self._wasd_controller.start()
        except Exception as exc:
            print(f"[WASD] Failed to start controller: {exc}")

    def _stop_wasd_controller(self) -> None:
        if self._wasd_controller is None:
            return
        try:
            self._wasd_controller.stop()
        except Exception as exc:
            print(f"[WASD] Failed to stop controller: {exc}")

    def initialize(self, roi: Region) -> None:
        """
        Initialize application components.

        Args:
            roi: Initial ROI region
        """
        self.roi = roi

        # Initialize capture
        self.capture = MSSCapture()

        # Initialize matchers
        raw_templates_dir = self.settings.get("templates_dir", "assets/templates")
        templates_dir = resource_path(raw_templates_dir)
        threshold = float(self.settings.get("threshold", 0.9))

        self.matcher = TemplateMatcher(templates_dir=templates_dir, threshold=threshold)
        self.lib_matcher = LibraryMatcher(threshold=threshold)

        print(f"Загружено шаблонов: {len(self.matcher.templates)} из '{templates_dir}'")
        if len(self.matcher.templates) > 0:
            print(
                "Список шаблонов:",
                ", ".join([t[0] for t in self.matcher.get_template_infos()]),
            )
        else:
            print(
                f"Шаблоны не найдены в каталоге '{templates_dir}'. Добавьте .png/.jpg, вырезанные ровно по иконке."
            )

        # Initialize UI
        ui_cfg = self.settings.get("ui", {})
        dock_cfg = ui_cfg.get("dock_position") or {}
        dock_position = None
        try:
            left = dock_cfg.get("left")
            top = dock_cfg.get("top")
            if left is not None and top is not None:
                dock_position = (int(left), int(top))
        except Exception:
            dock_position = None

        self.hud = BuffHUD(
            templates=self.matcher.get_template_infos(),
            keep_on_top=bool(ui_cfg.get("keep_on_top", False)),
            alpha=float(ui_cfg.get("alpha", 1.0)),
            grab_anywhere=bool(ui_cfg.get("grab_anywhere", True)),
            focus_required=self._focus_required,
            dock_position=dock_position,
            triple_ctrl_click_enabled=self._triple_ctrl_click_enabled,
            mega_qol_enabled=self._mega_qol_enabled,
            mega_qol_sequence=self._mega_qol_seq_str,
            mega_qol_delay_ms=self._mega_qol_delay_ms,
            fast_destroy_enabled=self._fast_destroy_enabled,
            fast_destroy_warning_overlay=self._fast_destroy_warning_overlay,
            fast_destroy_activation_hint=self._fast_destroy_activation_hint,
            fast_destroy_deactivation_hint=self._fast_destroy_deactivation_hint,
            wasd_enabled=self._wasd_enabled,
            wasd_center_offset_x=self._wasd_center_offset_x,
            wasd_center_offset_y=self._wasd_center_offset_y,
            wasd_move_offset_pixels=self._wasd_move_offset_pixels,
            wasd_enable_skill_cursor=self._wasd_enable_skill_cursor,
            wasd_distance_skill=self._wasd_distance_skill,
            wasd_skill_cursor_delay_s=self._wasd_skill_cursor_delay_s,
            wasd_input_delay_s=self._wasd_input_delay_s,
            wasd_movement_hint=self._wasd_movement_hint,
            wasd_toggle_hint=self._wasd_toggle_hint,
            overlay_hotkey=self._overlay_open_hotkey,
            use_map_layout_overlay=bool(
                self.settings.get("overlay", {}).get("use_map_layout_overlay", True)
            ),
        )

        self.hud.set_roi_info(roi.left, roi.top, roi.width, roi.height)
        self.hud.set_dock_visibility_grace(self._dock_interaction_grace_s)

        # Initialize overlays
        self.overlay = OverlayHighlighter(self.hud.get_root())
        self.tab_overlay = TabOverlayWindow(
            self.hud.get_root(),
            settings=self.settings,
            save_settings_callback=lambda: save_settings(
                self.settings_path,
                self.settings,
            ),
        )
        self.mirrors = IconMirrorsOverlay(self.hud.get_root())
        self.mirrors.set_copy_enabled(self.hud.get_copy_area_enabled())
        self.currency_overlay = CurrencyOverlay(self.hud.get_root())
        self.hud.set_currency_positioning(False)
        self._currencies_cache = load_currencies()

        # Initialize tray
        self.tray = TrayIcon()
        self.tray.start()

        # Initialize focus-dependent state
        self._scan_user_requested = self.hud.get_scanning_enabled()
        self._copy_user_requested = self.hud.get_copy_area_enabled()
        self._apply_wasd_config(self.hud.get_wasd_config())
        self._focus_state_last = None
        self._last_allowed_hwnd = None
        try:
            game_in_focus = self._is_allowed_process_active()
            self.hud.set_wasd_indicator_visibility(game_in_focus)
            self.hud.set_dock_game_focused(game_in_focus)
        except Exception:
            pass
        self.hud.set_status_message("")

    def _load_allowed_processes(self) -> Set[str]:
        """Load allowed process names from configuration file."""
        processes: Set[str] = set()

        try:
            with open(ALLOWED_PROCESSES_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                items = data.get("processes", [])
            else:
                items = data
            for item in items or []:
                name = str(item).strip().lower()
                if name:
                    processes.add(name)
        except Exception:
            processes = set()
        return processes

    def _restore_allowed_focus(self) -> None:
        """Attempt to return focus to the last allowed window."""
        if not sys.platform.startswith("win"):
            return
        hwnd = getattr(self, "_last_allowed_hwnd", None)
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _get_self_process_names(self) -> Set[str]:
        """Return possible executable names for the current process."""
        names: Set[str] = set()

        for candidate in (sys.executable, sys.argv[0]):
            try:
                if not candidate:
                    continue
                name = os.path.basename(candidate).strip().lower()
                if name:
                    names.add(name)
                    if name.endswith("python.exe"):
                        names.add("pythonw.exe")
                    elif name.endswith("pythonw.exe"):
                        names.add("python.exe")
            except Exception:
                continue

        if not names:
            names.add("python.exe")
            names.add("pythonw.exe")

        return names

    def run(self) -> None:
        """Run main application loop."""
        scan_interval_ms = int(self.settings.get("scan_interval_ms", 50))

        print(
            f"ROI: left={self.roi.left}, top={self.roi.top}, width={self.roi.width}, height={self.roi.height}"
        )
        print(f"Порог совпадения: {self.matcher.threshold}")
        print(f"Интервал опроса: {scan_interval_ms} мс")

        try:
            while True:
                event = self.hud.read(timeout=scan_interval_ms)
                game_in_focus = self._is_allowed_process_active()
                if not game_in_focus:
                    try:
                        game_in_focus = self.hud.is_dock_interaction_recent(
                            self._dock_interaction_grace_s
                        )
                    except Exception:
                        game_in_focus = False

                toggle_requests = self._consume_wasd_toggle_requests()
                if toggle_requests % 2 == 1:
                    try:
                        self._do_wasd_toggle(game_in_focus)
                    except Exception as exc:
                        print(f"[WASD] Toggle failed: {exc}")

                if event == "EXIT" or self.tray.is_exit_requested():
                    break

                refresh_copy = False
                skip_frame_processing = False

                if event == "LIBRARY_UPDATED":
                    try:
                        self.lib_matcher.refresh()
                    except Exception:
                        pass
                    skip_frame_processing = True

                elif event == "COPY_UPDATED":
                    refresh_copy = True
                    skip_frame_processing = True

                elif event == "CURRENCY_UPDATED":
                    self._currencies_cache = load_currencies()
                    active_ids = {
                        str(entry.get("id"))
                        for entry in self._currencies_cache
                        if entry.get("id")
                    }
                    self._trim_quickcraft_positions(active_ids)
                    self._register_quickcraft_hotkeys()
                    if (
                        self._quickcraft_runtime_active
                        and self._quickcraft_runtime_active
                        not in self._quickcraft_positions
                    ):
                        self._hide_quickcraft_overlay()
                    if self._currency_positioning_enabled:
                        self._enable_currency_positioning()
                    if self._quickcraft_runtime_active:
                        self._show_quickcraft_overlay(
                            self._quickcraft_runtime_active, force=True
                        )
                    skip_frame_processing = True

                elif event == "QUICKCRAFT_UPDATED":
                    self._reload_quickcraft_data()
                    skip_frame_processing = True

                elif event == "SELECT_ROI":
                    self._handle_roi_selection()
                    skip_frame_processing = True

                elif event == "SCAN_ON":
                    self._scan_user_requested = True

                elif event == "SCAN_OFF":
                    self._scan_user_requested = False

                elif event == "COPY_AREA_TOGGLE":
                    self._copy_user_requested = self.hud.get_copy_area_enabled()
                    refresh_copy = True

                elif event == "FOCUS_POLICY_CHANGED":
                    self._focus_required = self.hud.get_focus_required()
                    self.settings["require_game_focus"] = self._focus_required
                    save_settings(self.settings_path, self.settings)
                    refresh_copy = True

                elif event == "LANG_CHANGED":
                    self.settings["language"] = get_lang()
                    save_settings(self.settings_path, self.settings)

                elif event == "DOCK_MOVED":
                    self._update_dock_position_settings()

                elif event == "DOCK_INTERACTION":
                    # Do not change OS window focus on dock interaction
                    skip_frame_processing = True

                elif event == "TRIPLE_CTRL_CLICK_CHANGED":
                    self._triple_ctrl_click_enabled = (
                        self.hud.get_triple_ctrl_click_enabled()
                    )
                    self.settings["triple_ctrl_click_enabled"] = (
                        self._triple_ctrl_click_enabled
                    )
                    save_settings(self.settings_path, self.settings)
                    # If feature disabled while active, stop emulation
                    if (
                        not self._triple_ctrl_click_enabled
                        and self._triple_ctrl_click_active
                    ):
                        self._stop_mouse_simulation()

                elif event == "MEGA_QOL_CHANGED":
                    cfg = self.hud.get_mega_qol_config()
                    self._mega_qol_enabled = bool(cfg.get("enabled"))
                    self._mega_qol_seq_str = str(cfg.get("sequence") or "")
                    try:
                        self._mega_qol_delay_ms = int(cfg.get("delay_ms") or 50)
                    except Exception:
                        self._mega_qol_delay_ms = 50
                    self.settings.setdefault("mega_qol", {})
                    self.settings["mega_qol"].update(
                        {
                            "wheel_down_enabled": self._mega_qol_enabled,
                            "wheel_down_sequence": self._mega_qol_seq_str,
                            "wheel_down_delay_ms": int(self._mega_qol_delay_ms),
                        }
                    )
                    # Sync double-ctrl emulation from Mega QoL tab
                    self._triple_ctrl_click_enabled = (
                        self.hud.get_triple_ctrl_click_enabled()
                    )
                    self.settings["triple_ctrl_click_enabled"] = (
                        self._triple_ctrl_click_enabled
                    )
                    if (
                        not self._triple_ctrl_click_enabled
                        and self._triple_ctrl_click_active
                    ):
                        self._stop_mouse_simulation()
                    save_settings(self.settings_path, self.settings)

                elif event == "WASD_CHANGED":
                    self._wasd_cfg = self.hud.get_wasd_config()
                    self._apply_wasd_config(self._wasd_cfg)
                    self.settings["wasd"] = self._wasd_cfg
                    save_settings(self.settings_path, self.settings)

                elif event == "FAST_DESTROY_CHANGED":
                    cfg = self.hud.get_fast_destroy_config()
                    self._fast_destroy_enabled = bool(cfg.get("enabled", False))
                    self._fast_destroy_warning_overlay = bool(
                        cfg.get("warning_overlay", True)
                    )
                    self.settings.setdefault("fast_destroy", {})
                    self.settings["fast_destroy"].update(
                        {
                            "enabled": self._fast_destroy_enabled,
                            "warning_overlay": self._fast_destroy_warning_overlay,
                            "activation_interval_s": float(
                                self._fast_destroy_activation_interval_s
                            ),
                            "chat_open_delay_s": float(
                                self._fast_destroy_chat_open_delay_s
                            ),
                            "command_input_delay_s": float(
                                self._fast_destroy_command_input_delay_s
                            ),
                            "command_submit_delay_s": float(
                                self._fast_destroy_command_submit_delay_s
                            ),
                        }
                    )
                    if (
                        not self._fast_destroy_enabled
                        and self._fast_destroy_mode_active
                    ):
                        self._set_fast_destroy_mode(False)
                    elif self._fast_destroy_mode_active:
                        self._update_fast_destroy_overlay()
                    save_settings(self.settings_path, self.settings)

                elif event == "WASD_OPEN_CONFIG":
                    self._open_settings_location()
                    skip_frame_processing = True

                elif event == "TAB_OVERLAY_OPEN":
                    self._toggle_tab_overlay(game_in_focus)
                    skip_frame_processing = True

                elif event == "TAB_OVERLAY_HOTKEY_CHANGED":
                    self._sync_overlay_hotkey()
                    skip_frame_processing = True

                elif event == "MAP_LAYOUT_OVERLAY_CHANGED":
                    overlay_cfg = self.settings.setdefault("overlay", {})
                    if isinstance(overlay_cfg, dict):
                        overlay_cfg["use_map_layout_overlay"] = bool(
                            self.hud.get_map_layout_overlay_enabled()
                        )
                        save_settings(self.settings_path, self.settings)
                    skip_frame_processing = True

                elif event == "CURRENCY_POSITIONING_ON":
                    self._currency_positioning_requested = True
                    if self._is_feature_allowed("currency_positioning", game_in_focus):
                        self._enable_currency_positioning()
                    else:
                        self._currency_positioning_requested = False
                        self._disable_currency_positioning(save_changes=False)
                    skip_frame_processing = True

                elif event == "CURRENCY_POSITIONING_OFF":
                    self._currency_positioning_requested = False
                    self._disable_currency_positioning(save_changes=True)
                    skip_frame_processing = True

                if self.tray.is_exit_requested():
                    break

                self._apply_focus_policy(game_in_focus)

                if refresh_copy:
                    self._refresh_copy_overlays()

                self._update_currency_overlay(game_in_focus)
                self._process_hotkeys(game_in_focus)

                self._process_mega_qol_wheel(game_in_focus)

                self._handle_positioning_toggle(game_in_focus)

                if skip_frame_processing:
                    continue

                self._handle_overlay_toggle(game_in_focus)

                # Handle triple ctrl click functionality
                if self._triple_ctrl_click_enabled:
                    self._handle_triple_ctrl_click(game_in_focus)

                if (
                    self._is_feature_allowed("scan", game_in_focus)
                    and self._scan_user_requested
                ):
                    self._scan_frame()
                else:
                    self._clear_results()

        finally:
            self._cleanup()

    def _handle_overlay_toggle(self, game_in_focus: Optional[bool] = None) -> None:
        """Handle overlay enable/disable."""
        if not self._is_feature_allowed("overlay_highlighter", game_in_focus):
            if self.overlay_enabled_last:
                try:
                    self.overlay.hide()
                except Exception:
                    pass
                self.overlay_enabled_last = False
            return

        overlay_enabled_curr = self.hud.get_overlay_enabled()
        if overlay_enabled_curr != self.overlay_enabled_last:
            if overlay_enabled_curr:
                self.overlay.show(
                    (self.roi.left, self.roi.top, self.roi.width, self.roi.height)
                )
            else:
                self.overlay.hide()
            self.overlay_enabled_last = overlay_enabled_curr

    def _handle_positioning_toggle(self, game_in_focus: Optional[bool] = None) -> None:
        """Handle positioning mode toggle."""
        positioning_allowed = self._is_feature_allowed(
            "currency_positioning", game_in_focus
        )
        positioning_enabled_curr = (
            self.hud.get_positioning_enabled() and positioning_allowed
        )
        if positioning_enabled_curr != self.positioning_enabled_last:
            try:
                if positioning_enabled_curr:
                    print("[UI] Включён режим позиционирования активных иконок")
                    self.mirrors.enable_positioning_mode()
                else:
                    print("[UI] Выключен режим позиционирования, сохраняю координаты")
                    self.mirrors.disable_positioning_mode(save_changes=True)
            except Exception as e:
                print("[UI] Ошибка переключения позиционирования:", e)
            self.positioning_enabled_last = positioning_enabled_curr

    def _handle_roi_selection(self) -> None:
        """Handle ROI selection."""
        selected = select_roi(self.hud.get_root())
        if selected is not None:
            left, top, width, height = selected
            self.roi = Region(left=left, top=top, width=width, height=height)

            # Save to settings
            self.settings.setdefault("roi", {})
            self.settings["roi"]["mode"] = "absolute"
            self.settings["roi"]["left"] = left
            self.settings["roi"]["top"] = top
            self.settings["roi"]["width"] = width
            self.settings["roi"]["height"] = height
            save_settings(self.settings_path, self.settings)

            self.hud.set_roi_info(left, top, width, height)

            if self.overlay_enabled_last:
                self.overlay.update((left, top, width, height))

    def _scan_frame(self) -> None:
        """Scan current frame for buffs."""
        frame_bgr = self.capture.grab(self.roi)
        if frame_bgr is None:
            self.hud.update([])
            return

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        found = self.matcher.match(gray)
        lib_results = self.lib_matcher.match(gray)

        self.hud.update(found)

        try:
            self.mirrors.update(
                lib_results,
                frame_bgr,
                (self.roi.left, self.roi.top, self.roi.width, self.roi.height),
            )
        except Exception:
            pass

        if found != self.last_found:
            print("Найдены шаблоны:", ", ".join(found) if found else "—")
            self.last_found = found

    def _clear_results(self) -> None:
        """Clear scan results when scanning is disabled."""
        if self.last_found:
            print("Найдены шаблоны: —")
            self.last_found = []

        self.hud.update([])

        try:
            self.mirrors.update(
                [], None, (self.roi.left, self.roi.top, self.roi.width, self.roi.height)
            )
        except Exception:
            pass

    def _refresh_copy_overlays(self) -> None:
        """Refresh copy area overlays after configuration changes."""
        try:
            self.mirrors.update(
                [], None, (self.roi.left, self.roi.top, self.roi.width, self.roi.height)
            )
        except Exception:
            pass

    def _update_currency_overlay(
        self, game_in_focus: Optional[bool] = None, block: bool = False
    ) -> None:
        """Refresh quick craft overlay captures when active or positioning."""
        if self.currency_overlay is None:
            return
        runtime_allowed = self._is_feature_allowed(
            "quickcraft_runtime_overlay", game_in_focus
        )
        positioning_allowed = self._is_feature_allowed(
            "currency_positioning", game_in_focus
        )
        if not runtime_allowed and (
            self._quickcraft_runtime_active or self._quickcraft_runtime_active_ids
        ):
            self._hide_quickcraft_overlay()
        if self._currency_positioning_enabled and not positioning_allowed:
            self._disable_currency_positioning(save_changes=False)
        if not runtime_allowed and not positioning_allowed:
            return
        try:
            self.currency_overlay.refresh()
        except Exception as exc:
            print(f"[QuickCraft] Refresh failed: {exc}")

    def _trim_quickcraft_positions(self, valid_ids: Set[str]) -> None:
        if not isinstance(valid_ids, set):
            valid_ids = set(valid_ids)
        trimmed: Dict[str, Dict[str, object]] = {}
        for raw_id, cfg in self._quickcraft_positions.items():
            cid = str(raw_id)
            if cid not in valid_ids:
                continue
            try:
                left = int(cfg.get("left", 0))
                top = int(cfg.get("top", 0))
            except Exception:
                left, top = 0, 0
            hotkey = str(cfg.get("hotkey", "") or "").strip()
            trimmed[cid] = {"left": left, "top": top, "hotkey": hotkey}
        self._quickcraft_positions = trimmed

    def _load_quickcraft_source_settle_delay_s(
        self,
        migrate_legacy: bool = False,
    ) -> float:
        quickcraft_cfg = self.settings.get("quickcraft")
        if not isinstance(quickcraft_cfg, dict):
            quickcraft_cfg = {}
            self.settings["quickcraft"] = quickcraft_cfg

        raw_delay = quickcraft_cfg.get(
            "source_settle_delay_s",
            DEFAULT_QUICKCRAFT_SOURCE_SETTLE_DELAY_S,
        )
        try:
            delay_s = max(0.0, float(raw_delay))
        except Exception:
            delay_s = DEFAULT_QUICKCRAFT_SOURCE_SETTLE_DELAY_S

        if migrate_legacy:
            try:
                legacy_delay_s = load_global_source_settle_delay_s(default=delay_s)
            except Exception:
                legacy_delay_s = delay_s
            if (
                abs(delay_s - DEFAULT_QUICKCRAFT_SOURCE_SETTLE_DELAY_S) < 1e-9
                and abs(legacy_delay_s - delay_s) > 1e-9
            ):
                delay_s = legacy_delay_s
                quickcraft_cfg["source_settle_delay_s"] = float(delay_s)
                save_settings(self.settings_path, self.settings)

        quickcraft_cfg["source_settle_delay_s"] = float(delay_s)
        return float(delay_s)

    def _register_quickcraft_hotkeys(self) -> None:
        # Load per-item hotkeys and global hotkey
        mapping: Dict[str, str] = {}
        for cid, cfg in (self._quickcraft_positions or {}).items():
            try:
                raw = str(cfg.get("hotkey", "") or "").strip()
            except Exception:
                raw = ""
            token = normalize_hotkey_name(raw)
            if not token:
                continue
            mapping[token] = str(cid)
        self._quickcraft_hotkey_map = mapping
        try:
            self._quickcraft_global_hotkey = normalize_hotkey_name(load_global_hotkey())
        except Exception:
            self._quickcraft_global_hotkey = ""
        self._quickcraft_source_settle_delay_s = (
            self._load_quickcraft_source_settle_delay_s()
        )

    def _reload_quickcraft_data(self) -> None:
        self._quickcraft_positions = load_quickcraft_positions()
        if self._currencies_cache:
            active_ids = {
                str(entry.get("id"))
                for entry in self._currencies_cache
                if entry.get("id")
            }
            self._trim_quickcraft_positions(active_ids)
        self._register_quickcraft_hotkeys()
        if self._quickcraft_runtime_active:
            active_id = self._quickcraft_runtime_active
            if active_id not in self._quickcraft_positions:
                self._hide_quickcraft_overlay()
            else:
                self._show_quickcraft_overlay(active_id, force=True)

    def _build_position_map(self) -> Dict[str, Dict[str, int]]:
        mapping: Dict[str, Dict[str, int]] = {}
        # Start from saved quickcraft positions
        for cid, cfg in self._quickcraft_positions.items():
            cid = str(cid)
            try:
                left = int(cfg.get("left", 0))
                top = int(cfg.get("top", 0))
            except Exception:
                left, top = 0, 0
            mapping[cid] = {"left": left, "top": top}

        # Fill missing or zero positions from currency capture defaults
        for item in self._currencies_cache or []:
            cid = str(item.get("id") or "")
            if not cid:
                continue
            cap = item.get("capture") or {}
            cap_left = int(cap.get("left", 0))
            cap_top = int(cap.get("top", 0))
            if cid not in mapping:
                mapping[cid] = {"left": cap_left, "top": cap_top}
            else:
                if mapping[cid].get("left", 0) == 0 and mapping[cid].get("top", 0) == 0:
                    mapping[cid] = {"left": cap_left, "top": cap_top}
        return mapping

    def _build_position_map_from_anchor(
        self, anchor_left: int, anchor_top: int
    ) -> Dict[str, Dict[str, int]]:
        """Build absolute positions from saved OFFSETS relative to an anchor square."""
        mapping: Dict[str, Dict[str, int]] = {}
        for cid, cfg in self._quickcraft_positions.items():
            cid = str(cid)
            try:
                off_left = int(cfg.get("left", 0))
                off_top = int(cfg.get("top", 0))
            except Exception:
                off_left, off_top = 0, 0
            mapping[cid] = {
                "left": int(anchor_left) + off_left,
                "top": int(anchor_top) + off_top,
            }
        return mapping

    def _get_center_anchor(self) -> tuple[int, int]:
        try:
            sw = int(self.hud.get_root().winfo_screenwidth())
            sh = int(self.hud.get_root().winfo_screenheight())
        except Exception:
            sw, sh = 1920, 1080
        size = 60
        return max(0, (sw - size) // 2), max(0, (sh - size) // 2)

    def _get_currency_by_id(self, currency_id: str) -> Optional[Dict]:
        for item in self._currencies_cache:
            if item.get("id") == currency_id:
                return item
        try:
            self._currencies_cache = load_currencies()
        except Exception:
            self._currencies_cache = []
            return None
        for item in self._currencies_cache:
            if item.get("id") == currency_id:
                return item
        return None

    def _show_quickcraft_overlay(
        self,
        currency_id: str,
        force: bool = False,
        game_in_focus: Optional[bool] = None,
    ) -> None:
        if self.currency_overlay is None:
            return
        if not self._is_feature_allowed("quickcraft_runtime_overlay", game_in_focus):
            self._hide_quickcraft_overlay()
            return
        if not force and self._quickcraft_runtime_active == currency_id:
            return

        currency_id = str(currency_id)
        currency = self._get_currency_by_id(currency_id)
        if currency is None:
            return

        position_cfg = self._quickcraft_positions.get(currency_id, {})
        position_map = {
            currency_id: {
                "left": int(position_cfg.get("left", 0)),
                "top": int(position_cfg.get("top", 0)),
            }
        }
        self.currency_overlay.activate_runtime([currency], position_map)
        self._quickcraft_runtime_active = currency_id
        # No per-row UI marker required

    def _hide_quickcraft_overlay(self) -> None:
        if self.currency_overlay is not None:
            self.currency_overlay.deactivate_runtime()
        self._quickcraft_runtime_active = None
        self._quickcraft_runtime_active_ids = set()

    def _handle_quickcraft_hotkey(
        self, token: str, game_in_focus: Optional[bool] = None
    ) -> None:
        if not self._is_feature_allowed("quickcraft_hotkey", game_in_focus):
            return
        # Global hotkey takes precedence
        if self._quickcraft_global_hotkey and token == self._quickcraft_global_hotkey:
            # If user presses global hotkey while positioning, save current template first
            if self._currency_positioning_enabled:
                try:
                    self._disable_currency_positioning(save_changes=True)
                except Exception:
                    pass
            self._toggle_quickcraft_global(game_in_focus)
            return
        currency_id = self._quickcraft_hotkey_map.get(token)
        if not currency_id:
            return
        if self._quickcraft_runtime_active == currency_id:
            self._hide_quickcraft_overlay()
        else:
            self._show_quickcraft_overlay(
                currency_id,
                force=True,
                game_in_focus=game_in_focus,
            )

    def _toggle_quickcraft_global(self, game_in_focus: Optional[bool] = None) -> None:
        if not self._is_feature_allowed("quickcraft_hotkey", game_in_focus):
            return
        if not self._is_feature_allowed("quickcraft_runtime_overlay", game_in_focus):
            return
        # If anything active -> hide all
        if self._quickcraft_runtime_active_ids:
            self._hide_quickcraft_overlay()
            return

        # Show all active currencies with saved positions
        currencies = [
            c for c in (self._currencies_cache or load_currencies()) if c.get("active")
        ]
        # Build absolute positions using Win32 mouse coordinates as the center square
        try:
            cur_x, cur_y = win32api.GetCursorPos()
        except Exception:
            cur_x = self.roi.left + self.roi.width // 2
            cur_y = self.roi.top + self.roi.height // 2
        anchor_left = int(cur_x) - 30
        anchor_top = int(cur_y) - 30
        position_map = self._build_position_map_from_anchor(anchor_left, anchor_top)
        show_list = []
        ids: Set[str] = set()
        for c in currencies:
            cid = str(c.get("id"))
            if not cid:
                continue
            show_list.append(c)
            ids.add(cid)

        if not show_list:
            return
        try:
            self.currency_overlay.activate_runtime(show_list, position_map)
            self._quickcraft_runtime_active_ids = ids
            self._quickcraft_runtime_active = None
            self._anchor_at_hotkey = (int(cur_x), int(cur_y))
        except Exception as exc:
            print(f"[QuickCraft] Global show failed: {exc}")

    def _read_clipboard_text(self) -> str:
        if not sys.platform.startswith("win"):
            return ""

        try:
            win32clipboard.OpenClipboard()
            raw_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return str(raw_text or "")
        except Exception:
            return ""
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    def _extract_map_name_from_clipboard(self, clipboard_text: str) -> str:
        text = str(clipboard_text or "")
        if not text:
            return ""

        normalized = text.replace("\r\n", "\n")
        if "Item Class: Maps" not in normalized:
            return ""

        lines = [line.strip() for line in normalized.split("\n")]
        rarity = ""
        for line in lines:
            if line.startswith("Rarity:"):
                rarity = line.split(":", 1)[1].strip().lower()
                break

        unidentified = any(line == "Unidentified" for line in lines)
        map_line = ""
        for line in lines:
            if not line or "Map" not in line:
                continue
            if line.startswith("Item Class:"):
                continue
            if ":" in line:
                continue
            if line.startswith("--------"):
                continue
            map_line = line
            break

        if not map_line:
            return ""

        if unidentified:
            return map_line

        if rarity == "magic":
            parts = map_line.split()
            if len(parts) > 1:
                return " ".join(parts[1:])
            return map_line

        if rarity == "normal":
            return map_line

        if rarity in {"rare", "unique"}:
            return map_line

        return map_line

    def _is_map_layout_overlay_enabled(self) -> bool:
        overlay_cfg = self.settings.get("overlay", {})
        if not isinstance(overlay_cfg, dict):
            return True
        return bool(overlay_cfg.get("use_map_layout_overlay", True))

    def _handle_clipboard_map_hotkey(
        self,
        token: str,
        now: Optional[float] = None,
        game_in_focus: Optional[bool] = None,
    ) -> None:
        if token != "C":
            return
        if not self._is_feature_allowed("map_layout_overlay", game_in_focus):
            return
        if not self._is_map_layout_overlay_enabled():
            return
        if now is None:
            now = time.time()

        try:
            ctrl_down = (win32api.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000) != 0
        except Exception:
            ctrl_down = False
        ctrl_recent = (now - self._last_ctrl_hotkey_time) <= 0.35
        if not (ctrl_down or ctrl_recent):
            return

        overlay_was_open = False
        if self.tab_overlay is not None:
            try:
                overlay_was_open = self.tab_overlay.is_clipboard_map_overlay_open()
            except Exception:
                overlay_was_open = False
            if overlay_was_open:
                try:
                    self.tab_overlay.close_clipboard_map_overlay()
                except Exception:
                    pass

        map_name = ""
        max_attempts = 8 if overlay_was_open else 3
        for attempt in range(max_attempts):
            if attempt > 0:
                time.sleep(0.04 * attempt)
            clipboard_text = self._read_clipboard_text()
            candidate = self._extract_map_name_from_clipboard(clipboard_text)
            if not candidate:
                continue
            if (
                overlay_was_open
                and self._last_clipboard_map_name
                and candidate == self._last_clipboard_map_name
                and attempt < (max_attempts - 1)
            ):
                continue
            map_name = candidate
            if map_name:
                break
        if not map_name:
            return
        if self.tab_overlay is None:
            return

        shown = self.tab_overlay.show_map_overlay_for_map_name(map_name)
        if shown:
            self._last_clipboard_map_name = map_name
            print(f"[Map Clipboard] Overlay shown for: {map_name}")
        else:
            print(f"[Map Clipboard] Map not found in map-data.json: {map_name}")

    def _process_hotkeys(self, game_in_focus: Optional[bool] = None) -> None:
        if self._hotkeys is None:
            # Fallback polling when hooks aren't available
            self._poll_hotkeys_fallback(game_in_focus)
        else:
            polled = self._hotkeys.poll()
            if polled:
                now = time.time()
                for token in polled:
                    if token in {"CTRL", "CONTROL"}:
                        self._last_ctrl_hotkey_time = now
                    self._handle_fast_destroy_hotkey(token, now, game_in_focus)
                    self._handle_clipboard_map_hotkey(token, now, game_in_focus)
                    if self._handle_overlay_hotkey(token, game_in_focus):
                        continue
                    self._handle_quickcraft_hotkey(token, game_in_focus)
            else:
                # If hook is installed but no events, also run fallback to support keys Tk may swallow
                self._poll_hotkeys_fallback(game_in_focus)
        # Process click-triggered actions
        self._process_fast_destroy_click_action(game_in_focus)
        self._process_quickcraft_click_action(game_in_focus)

    def _token_to_vk(self, token: str) -> Optional[int]:
        if not token:
            return None
        t = token.upper()
        if t.startswith("F") and t[1:].isdigit():
            n = int(t[1:])
            if 1 <= n <= 24:
                return getattr(win32con, f"VK_F{n}", None)
        if len(t) == 1 and "A" <= t <= "Z":
            return ord(t)
        if len(t) == 1 and "0" <= t <= "9":
            return ord(t)
        mapping = {
            "ESC": win32con.VK_ESCAPE,
            "ENTER": win32con.VK_RETURN,
            "SPACE": win32con.VK_SPACE,
            "TAB": win32con.VK_TAB,
            "UP": win32con.VK_UP,
            "DOWN": win32con.VK_DOWN,
            "LEFT": win32con.VK_LEFT,
            "RIGHT": win32con.VK_RIGHT,
            "HOME": win32con.VK_HOME,
            "END": win32con.VK_END,
            "PAGE_UP": win32con.VK_PRIOR,
            "PAGE_DOWN": win32con.VK_NEXT,
            "INSERT": win32con.VK_INSERT,
            "DELETE": win32con.VK_DELETE,
            "CTRL": win32con.VK_CONTROL,
            "ALT": win32con.VK_MENU,
            "SHIFT": win32con.VK_SHIFT,
        }
        return mapping.get(t)

    def _poll_hotkeys_fallback(self, game_in_focus: Optional[bool] = None) -> None:
        if not sys.platform.startswith("win"):
            return
        now = time.time()
        # poll only keys that are mapped
        tokens = set(self._quickcraft_hotkey_map.keys())
        tokens.update({"C", "CTRL", "ALT"})
        if self._quickcraft_global_hotkey:
            tokens.add(self._quickcraft_global_hotkey)
        tokens.update(self._overlay_open_sequence)
        for token in list(tokens):
            vk = self._token_to_vk(token)
            if vk is None:
                continue
            state = win32api.GetAsyncKeyState(vk)
            down = (state & 0x8000) != 0
            prev = self._key_down_state.get(token, False)
            if down and not prev:
                last = self._key_last_emit.get(token, 0.0)
                min_interval = 0.2
                if token in self._overlay_open_sequence:
                    min_interval = max(
                        0.01, min(0.2, self._overlay_open_interval_s * 0.45)
                    )
                if now - last > min_interval:
                    self._key_last_emit[token] = now
                    if token in {"CTRL", "CONTROL"}:
                        self._last_ctrl_hotkey_time = now
                        self._key_down_state[token] = down
                        continue
                    self._handle_fast_destroy_hotkey(token, now, game_in_focus)
                    self._handle_clipboard_map_hotkey(token, now, game_in_focus)
                    if not self._handle_overlay_hotkey(token, game_in_focus):
                        self._handle_quickcraft_hotkey(token, game_in_focus)
            self._key_down_state[token] = down

    def _handle_fast_destroy_hotkey(
        self,
        token: str,
        now: Optional[float] = None,
        game_in_focus: Optional[bool] = None,
    ) -> None:
        if token != "ALT":
            return
        if not self._fast_destroy_enabled:
            return
        if not self._is_feature_allowed("fast_destroy_hotkey", game_in_focus):
            if self._fast_destroy_mode_active:
                self._set_fast_destroy_mode(False)
            return
        if now is None:
            now = time.time()

        if self._fast_destroy_mode_active:
            self._set_fast_destroy_mode(False)
            return

        if (
            now - self._fast_destroy_last_alt_press_time
        ) <= self._fast_destroy_activation_interval_s:
            self._set_fast_destroy_mode(True)
            self._fast_destroy_last_alt_press_time = 0.0
            return

        self._fast_destroy_last_alt_press_time = now

    def _set_fast_destroy_mode(self, active: bool) -> None:
        self._fast_destroy_mode_active = bool(active)
        self._fast_destroy_prev_lmb = False
        if self._fast_destroy_mode_active:
            self._update_fast_destroy_overlay()
        else:
            self._hide_fast_destroy_overlay()

    def _update_fast_destroy_overlay(self) -> None:
        if not self._fast_destroy_mode_active or not self._fast_destroy_warning_overlay:
            self._hide_fast_destroy_overlay()
            return
        if not self._is_feature_allowed("fast_destroy_warning_overlay"):
            self._hide_fast_destroy_overlay()
            return
        if not sys.platform.startswith("win") or self.hud is None:
            return

        try:
            cur_x, cur_y = win32api.GetCursorPos()
        except Exception:
            return

        import tkinter as tk

        if self._fast_destroy_overlay_win is None:
            try:
                win = tk.Toplevel(self.hud.get_root())
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.configure(bg="#ff0000")
                lbl = tk.Label(
                    win,
                    text="DELETE",
                    bg="#ff0000",
                    fg="black",
                    font=("Arial", 9, "bold"),
                )
                lbl.place(relx=0.5, rely=0.5, anchor="center")
                self._fast_destroy_overlay_win = win
                self._fast_destroy_overlay_label = lbl
            except Exception:
                self._fast_destroy_overlay_win = None
                self._fast_destroy_overlay_label = None
                return

        try:
            x = int(cur_x - 100)
            y = int(cur_y + 50)
            self._fast_destroy_overlay_win.geometry(f"200x50+{x}+{y}")
            self._fast_destroy_overlay_win.lift()
        except Exception:
            pass

    def _hide_fast_destroy_overlay(self) -> None:
        if self._fast_destroy_overlay_win is not None:
            try:
                self._fast_destroy_overlay_win.destroy()
            except Exception:
                pass
        self._fast_destroy_overlay_win = None
        self._fast_destroy_overlay_label = None

    def _process_fast_destroy_click_action(
        self, game_in_focus: Optional[bool] = None
    ) -> None:
        if not sys.platform.startswith("win"):
            return
        if not self._fast_destroy_enabled or not self._fast_destroy_mode_active:
            self._fast_destroy_prev_lmb = False
            return

        self._update_fast_destroy_overlay()

        if not self._is_feature_allowed("fast_destroy_click_action", game_in_focus):
            self._fast_destroy_prev_lmb = False
            return

        try:
            state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON)
        except Exception:
            return
        down = (state & 0x8000) != 0
        if down and not self._fast_destroy_prev_lmb:
            self._execute_fast_destroy_command()
        self._fast_destroy_prev_lmb = down

    def _execute_fast_destroy_command(self) -> None:
        try:
            if self._fast_destroy_chat_open_delay_s > 0:
                time.sleep(self._fast_destroy_chat_open_delay_s)
            self._key_press(win32con.VK_RETURN)

            if self._fast_destroy_command_input_delay_s > 0:
                time.sleep(self._fast_destroy_command_input_delay_s)
            self._paste_text("/destroy")

            if self._fast_destroy_command_submit_delay_s > 0:
                time.sleep(self._fast_destroy_command_submit_delay_s)
            self._key_press(win32con.VK_RETURN)
        except Exception as exc:
            print(f"[FastDestroy] Execute failed: {exc}")

    def _move_cursor(self, x: int, y: int) -> None:
        try:
            ctypes.windll.user32.SetCursorPos(int(x), int(y))
        except Exception:
            pass

    def _click(self, left: bool = True) -> None:
        try:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN if left else MOUSEEVENTF_RIGHTDOWN
            SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.01)
            inp2 = INPUT()
            inp2.type = INPUT_MOUSE
            inp2.mi.dwFlags = MOUSEEVENTF_LEFTUP if left else MOUSEEVENTF_RIGHTUP
            SendInput(1, ctypes.byref(inp2), ctypes.sizeof(INPUT))
        except Exception:
            pass

    def _mouse_button_is_down(self, left: bool) -> Optional[bool]:
        try:
            vk = win32con.VK_LBUTTON if left else win32con.VK_RBUTTON
            return (win32api.GetAsyncKeyState(vk) & 0x8000) != 0
        except Exception:
            return None

    def _wait_cursor_position(
        self,
        x: int,
        y: int,
        timeout_s: float = 0.12,
        tolerance_px: int = 2,
    ) -> bool:
        deadline = time.time() + max(0.0, float(timeout_s))
        target_x = int(x)
        target_y = int(y)
        tol = max(0, int(tolerance_px))
        while time.time() <= deadline:
            try:
                cur_x, cur_y = win32api.GetCursorPos()
            except Exception:
                return True
            if abs(int(cur_x) - target_x) <= tol and abs(int(cur_y) - target_y) <= tol:
                return True
            time.sleep(0.004)
        return False

    def _move_cursor_and_wait(self, x: int, y: int, attempts: int = 3) -> bool:
        tries = max(1, int(attempts))
        for _ in range(tries):
            self._move_cursor(int(x), int(y))
            if self._wait_cursor_position(
                int(x), int(y), timeout_s=0.1, tolerance_px=2
            ):
                return True
            time.sleep(0.008)
        return False

    def _click_confirmed(self, left: bool, attempts: int = 3) -> bool:
        state = self._mouse_button_is_down(left)
        if state is None:
            self._click(left=left)
            return True

        tries = max(1, int(attempts))
        down_flag = MOUSEEVENTF_LEFTDOWN if left else MOUSEEVENTF_RIGHTDOWN
        up_flag = MOUSEEVENTF_LEFTUP if left else MOUSEEVENTF_RIGHTUP
        for _ in range(tries):
            down_sent = False
            up_sent = False
            try:
                down = INPUT()
                down.type = INPUT_MOUSE
                down.mi.dwFlags = down_flag
                down_sent = bool(
                    SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT)) == 1
                )
            except Exception:
                down_sent = False

            down_ok = False
            if down_sent:
                down_deadline = time.time() + 0.08
                while time.time() <= down_deadline:
                    button_state = self._mouse_button_is_down(left)
                    if button_state is None:
                        down_ok = True
                        break
                    if button_state:
                        down_ok = True
                        break
                    time.sleep(0.003)

            time.sleep(0.012)

            try:
                up = INPUT()
                up.type = INPUT_MOUSE
                up.mi.dwFlags = up_flag
                up_sent = bool(
                    SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT)) == 1
                )
            except Exception:
                up_sent = False

            up_ok = False
            if up_sent:
                up_deadline = time.time() + 0.1
                while time.time() <= up_deadline:
                    button_state = self._mouse_button_is_down(left)
                    if button_state is None:
                        up_ok = True
                        break
                    if not button_state:
                        up_ok = True
                        break
                    time.sleep(0.003)

            if down_ok and up_ok:
                return True

            time.sleep(0.012)

        return False

    def _process_quickcraft_click_action(
        self, game_in_focus: Optional[bool] = None
    ) -> None:
        if self._fast_destroy_enabled and self._fast_destroy_mode_active:
            self._pending_click_currency_id = None
            return
        if not self._is_feature_allowed("quickcraft_click_action", game_in_focus):
            self._pending_click_currency_id = None
            return
        # Require either global (multiple) or single runtime overlay active
        if (
            not self._quickcraft_runtime_active_ids
            and not self._quickcraft_runtime_active
        ):
            self._pending_click_currency_id = None
            return
        # Prefer low-level mouse hook for reliable click detection
        try:
            events = self._mouse_clicks.poll() if self._mouse_clicks is not None else []
        except Exception:
            events = []
        now = time.time()
        for ev in events:
            if ev == "LBUTTON_DOWN":
                try:
                    hovered_id = self.currency_overlay.get_hovered_currency_id()
                except Exception:
                    hovered_id = None
                if hovered_id and (now - self._last_click_time) >= 0.2:
                    self._last_click_time = now
                    self._execute_quickcraft_for(str(hovered_id))
                    return
        now = time.time()
        # Read current left button state
        try:
            state = win32api.GetAsyncKeyState(win32con.VK_LBUTTON)
        except Exception:
            return
        down = (state & 0x8000) != 0

        # Fast-path: execute immediately on button press over an overlay
        if down:
            try:
                hovered_id = self.currency_overlay.get_hovered_currency_id()
            except Exception:
                hovered_id = None
            if hovered_id:
                if (now - self._last_click_time) >= 0.25:
                    self._last_click_time = now
                    self._execute_quickcraft_for(str(hovered_id))
                return

        if self._pending_click_currency_id is None:
            # Waiting for a new click: if left is pressed over an overlay, arm the action
            if not down:
                return
            if now - self._last_click_time < 0.25:
                return
            hovered_id = None
            try:
                hovered_id = self.currency_overlay.get_hovered_currency_id()
            except Exception:
                hovered_id = None
            if not hovered_id:
                return
            self._pending_click_currency_id = str(hovered_id)
            return

        # Pending armed: wait until user releases left before executing
        if down:
            return

        hovered_id = self._pending_click_currency_id
        self._pending_click_currency_id = None
        self._last_click_time = now
        self._execute_quickcraft_for(str(hovered_id))

    def _execute_quickcraft_for(self, hovered_id: str) -> None:
        # Determine SOURCE location from the currency's original capture rect (true source)
        cur = self._get_currency_by_id(str(hovered_id)) or {}
        cap = cur.get("capture", {}) if isinstance(cur, dict) else {}
        try:
            src_left = int(cap.get("left", 0))
            src_top = int(cap.get("top", 0))
            w = max(1, int(cap.get("width", 1)))
            h = max(1, int(cap.get("height", 1)))
        except Exception:
            src_left, src_top, w, h = 0, 0, 32, 32
        cx = int(src_left + w // 2)
        cy = int(src_top + h // 2)

        # Original anchor point to return to (hotkey-time position if set)
        if self._anchor_at_hotkey is None:
            try:
                ax, ay = win32api.GetCursorPos()
            except Exception:
                ax = self.roi.left + self.roi.width // 2
                ay = self.roi.top + self.roi.height // 2
        else:
            ax, ay = self._anchor_at_hotkey

        # Execute sequence: move to SOURCE, right click, return, left click
        try:
            time.sleep(0.01)
            if not self._move_cursor_and_wait(cx, cy, attempts=4):
                self._move_cursor(cx, cy)
                time.sleep(0.03)
            else:
                time.sleep(0.02)

            # Extra settle time after reaching source rect before right click
            time.sleep(max(0.0, float(self._quickcraft_source_settle_delay_s)))

            if not self._click_confirmed(left=False, attempts=4):
                print(
                    "[QuickCraft] Right click not confirmed at source; sequence aborted"
                )
                return

            time.sleep(0.02)
            if not self._move_cursor_and_wait(ax, ay, attempts=3):
                self._move_cursor(ax, ay)
            time.sleep(0.02)
            self._click(left=True)
        except Exception:
            pass

    def _enable_currency_positioning(self) -> None:
        if self.currency_overlay is None:
            return

        intermediate = {}
        if self._currency_positioning_enabled:
            intermediate = self.currency_overlay.disable_positioning(save_changes=False)
        else:
            self._quickcraft_positions = load_quickcraft_positions()

        if intermediate:
            for cid, pos in intermediate.items():
                cid_key = str(cid)
                cfg = self._quickcraft_positions.get(cid_key, {})
                cfg["left"] = int(pos.get("left", 0))
                cfg["top"] = int(pos.get("top", 0))
                cfg["hotkey"] = str(cfg.get("hotkey", "") or "").strip()
                self._quickcraft_positions[cid_key] = cfg

        currencies = load_currencies()
        self._currencies_cache = currencies
        active_ids = {str(entry.get("id")) for entry in currencies if entry.get("id")}
        self._trim_quickcraft_positions(active_ids)

        try:
            # Place windows around center guide using saved OFFSETS
            anchor_left, anchor_top = self._get_center_anchor()
            position_map = self._build_position_map_from_anchor(anchor_left, anchor_top)
            self.currency_overlay.enable_positioning(currencies, position_map)
            self._currency_positioning_enabled = True
            self.hud.set_currency_positioning(True)
        except Exception as exc:
            print(f"[QuickCraft] Failed to enable positioning: {exc}")
            self._currency_positioning_enabled = False
        self._register_quickcraft_hotkeys()

    def _disable_currency_positioning(self, save_changes: bool = True) -> None:
        if self.currency_overlay is None:
            return

        if not self._currency_positioning_enabled and not save_changes:
            return

        updated = {}
        try:
            updated = self.currency_overlay.disable_positioning(
                save_changes=save_changes
            )
        except Exception as exc:
            print(f"[QuickCraft] Failed to disable positioning: {exc}")

        if save_changes:
            if updated:
                # Extract center anchor from special window if present
                center = updated.pop("__center__", None)
                if center is not None:
                    try:
                        a_left = int(center.get("left", 0))
                        a_top = int(center.get("top", 0))
                    except Exception:
                        a_left, a_top = self._get_center_anchor()
                else:
                    a_left, a_top = self._get_center_anchor()

                for cid, pos in updated.items():
                    cid_key = str(cid)
                    try:
                        abs_left = int(pos.get("left", 0))
                        abs_top = int(pos.get("top", 0))
                    except Exception:
                        abs_left, abs_top = 0, 0
                    off_left = abs_left - a_left
                    off_top = abs_top - a_top
                    cfg = self._quickcraft_positions.get(cid_key, {})
                    cfg["left"] = int(off_left)
                    cfg["top"] = int(off_top)
                    cfg["hotkey"] = str(cfg.get("hotkey", "") or "").strip()
                    self._quickcraft_positions[cid_key] = cfg
            currencies = load_currencies()
            self._currencies_cache = currencies
            active_ids = {
                str(entry.get("id")) for entry in currencies if entry.get("id")
            }
            self._trim_quickcraft_positions(active_ids)
            try:
                save_quickcraft_positions(self._quickcraft_positions)
            except Exception as exc:
                print(f"[QuickCraft] Failed to save positions: {exc}")
            self._register_quickcraft_hotkeys()
            if (
                self._quickcraft_runtime_active
                and self._quickcraft_runtime_active in self._quickcraft_positions
            ):
                self._show_quickcraft_overlay(
                    self._quickcraft_runtime_active, force=True
                )

        self._currency_positioning_enabled = False
        self.hud.set_currency_positioning(False)

    def _handle_triple_ctrl_click(self, game_in_focus: Optional[bool] = None) -> None:
        """Handle double Ctrl press detection and mouse emulation lifecycle.

        Double press (within 300ms) starts emulation. Releasing Ctrl stops it.
        We detect only rising edges (Up -> Down) to avoid auto-repeat while holding Ctrl.
        """
        if not sys.platform.startswith("win"):
            return

        try:
            if not self._is_feature_allowed("triple_ctrl_click", game_in_focus):
                if self._triple_ctrl_click_active:
                    self._stop_mouse_simulation()
                return
            state = win32api.GetAsyncKeyState(win32con.VK_CONTROL)
            ctrl_held = (state & 0x8000) != 0

            # Rising edge detection to avoid typematic repeats while holding
            rising_edge = ctrl_held and not self._ctrl_prev_held
            if rising_edge:
                now = time.time()
                if now - self._last_ctrl_press_time <= 0.3:
                    self._ctrl_press_count += 1
                else:
                    self._ctrl_press_count = 1
                self._last_ctrl_press_time = now

                # Start on double press (do not toggle off here)
                if self._ctrl_press_count >= 2 and not self._triple_ctrl_click_active:
                    self._start_mouse_simulation()
                    print("[Double Ctrl] Mouse simulation started")
                    self._ctrl_press_count = 0

            # Stop when Ctrl is released
            if self._triple_ctrl_click_active and not ctrl_held:
                self._stop_mouse_simulation()
                print("[Double Ctrl] Mouse simulation stopped")

            # Update previous state
            self._ctrl_prev_held = ctrl_held

        except Exception as e:
            print(f"[Double Ctrl] Error: {e}")

    def _start_mouse_simulation(self) -> None:
        """Start simulating continuous left mouse button clicks every 20ms."""
        if not sys.platform.startswith("win"):
            return
        try:
            import threading

            # Set active first to avoid race on thread start
            self._triple_ctrl_click_active = True
            self.hud.set_click_emulation_state(True)
            self._mouse_simulation_thread = threading.Thread(
                target=self._mouse_click_loop, daemon=True
            )
            self._mouse_simulation_thread.start()
        except Exception as e:
            print(f"[Double Ctrl] Error starting mouse simulation: {e}")

    def _stop_mouse_simulation(self) -> None:
        """Stop simulating left mouse button clicks."""
        if not sys.platform.startswith("win"):
            return
        try:
            self._triple_ctrl_click_active = False
            self.hud.set_click_emulation_state(False)
            # Wait a bit for the thread to stop
            if hasattr(self, "_mouse_simulation_thread"):
                self._mouse_simulation_thread.join(timeout=0.1)
        except Exception as e:
            print(f"[Double Ctrl] Error stopping mouse simulation: {e}")

    def _mouse_click_loop(self) -> None:
        """Loop that simulates mouse clicks every 50ms using SendInput."""
        while self._triple_ctrl_click_active:
            try:
                # Create mouse down input
                down_input = INPUT()
                down_input.type = INPUT_MOUSE
                down_input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN

                # Create mouse up input
                up_input = INPUT()
                up_input.type = INPUT_MOUSE
                up_input.mi.dwFlags = MOUSEEVENTF_LEFTUP

                # Send mouse down
                SendInput(1, ctypes.byref(down_input), ctypes.sizeof(INPUT))
                time.sleep(0.01)  # Short press duration

                # Send mouse up
                SendInput(1, ctypes.byref(up_input), ctypes.sizeof(INPUT))
                time.sleep(0.04)  # Wait before next click (total 50ms)

            except Exception as e:
                print(f"[Double Ctrl] Error in click loop: {e}")
                break

    def _update_dock_position_settings(self) -> None:
        """Persist floating dock position into settings."""
        position = self.hud.get_dock_position()
        if not position:
            return

        try:
            left = int(position[0])
            top = int(position[1])
        except Exception:
            return

        ui_cfg = self.settings.setdefault("ui", {})
        dock_cfg = ui_cfg.setdefault("dock_position", {})
        if dock_cfg.get("left") == left and dock_cfg.get("top") == top:
            return

        dock_cfg["left"] = left
        dock_cfg["top"] = top
        save_settings(self.settings_path, self.settings)

    def _apply_focus_policy(self, game_in_focus: bool) -> None:
        """Pause or resume application features based on foreground focus."""
        try:
            self.hud.set_dock_game_focused(bool(game_in_focus))
        except Exception:
            pass

        try:
            self.hud.set_wasd_indicator_visibility(bool(game_in_focus))
        except Exception:
            pass

        copy_allowed = self._is_feature_allowed("copy_overlay", game_in_focus)
        if game_in_focus:
            self._focus_loss_started = 0.0
            if self._focus_state_last is False:
                self.hud.set_status_message("")
            self.mirrors.set_copy_enabled(self._copy_user_requested and copy_allowed)
        else:
            if self._focus_loss_started == 0.0:
                try:
                    self._focus_loss_started = time.time()
                except Exception:
                    self._focus_loss_started = 0.0
            long_loss = False
            try:
                long_loss = (time.time() - self._focus_loss_started) > 0.25
            except Exception:
                long_loss = True
            if self._focus_required:
                if self._focus_state_last in (True, None):
                    self.hud.set_status_message(
                        t(
                            "status.game_focus_required",
                            "Focus the Path of Exile window to resume.",
                        ),
                        level="warning",
                    )
                if long_loss and self.overlay_enabled_last:
                    if not self._is_feature_allowed(
                        "overlay_highlighter", game_in_focus
                    ):
                        try:
                            self.overlay.hide()
                        except Exception:
                            pass
                        self.overlay_enabled_last = False
            self.mirrors.set_copy_enabled(self._copy_user_requested and copy_allowed)
            if long_loss and self._pending_click_currency_id is None:
                if not self._is_feature_allowed(
                    "quickcraft_runtime_overlay", game_in_focus
                ):
                    try:
                        self._hide_quickcraft_overlay()
                    except Exception:
                        pass
            if long_loss and self.tab_overlay is not None:
                if not self._is_feature_allowed("tab_overlay", game_in_focus):
                    try:
                        self.tab_overlay.hide()
                    except Exception:
                        pass
            if long_loss and self._fast_destroy_mode_active:
                if not self._is_feature_allowed("fast_destroy_hotkey", game_in_focus):
                    self._set_fast_destroy_mode(False)

        self._focus_state_last = game_in_focus

    def _is_allowed_process_active(self) -> bool:
        """Check if one of the allowed game processes is in foreground (focus)."""
        now = time.time()
        foreground_process = get_foreground_process_name()

        if foreground_process is None:
            # Foreground can be transiently unavailable during focus transitions.
            return self._is_recent_allowed_focus(now)

        normalized = foreground_process.strip().lower()
        is_self_window_focused = normalized in self._self_process_names
        is_game_focused = normalized in self.allowed_processes or is_self_window_focused

        # Debug: print when state changes
        if (
            not hasattr(self, "_last_foreground")
            or self._last_foreground != foreground_process
        ):
            if is_game_focused:
                print(f"[Game Focus] Game in focus: {foreground_process}")
            self._last_foreground = foreground_process
        if is_game_focused:
            self._last_allowed_focus_ts = now
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                if hwnd:
                    self._last_allowed_hwnd = hwnd
            except Exception:
                pass

        if not is_game_focused:
            return self._is_recent_allowed_focus(now)
        return True

    def _is_recent_allowed_focus(self, now: Optional[float] = None) -> bool:
        grace_s = max(0.0, float(getattr(self, "_dock_interaction_grace_s", 0.0)))
        if grace_s <= 0.0:
            return False
        current = time.time() if now is None else float(now)
        return (current - float(self._last_allowed_focus_ts)) <= grace_s

    def _cleanup(self) -> None:
        """Cleanup application resources."""
        self._stop_wasd_controller()

        try:
            self._disable_currency_positioning(save_changes=True)
        except Exception:
            pass

        try:
            self._hide_quickcraft_overlay()
        except Exception:
            pass

        try:
            self._hide_fast_destroy_overlay()
        except Exception:
            pass

        if self._hotkeys is not None:
            try:
                self._hotkeys.stop()
            except Exception:
                pass

        self.hud.close()

        try:
            self.overlay.hide()
            self.overlay.close()
        except Exception:
            pass

        try:
            if self.tab_overlay is not None:
                self.tab_overlay.close()
        except Exception:
            pass

        try:
            self.mirrors.disable_positioning_mode(save_changes=True)
        except Exception:
            pass

        try:
            self.mirrors.close()
        except Exception:
            pass

        try:
            if self.currency_overlay is not None:
                self.currency_overlay.close()
        except Exception:
            pass

        try:
            self.tray.stop()
        except Exception:
            pass

        self.capture.close()
        try:
            if hasattr(self, "_mouse_clicks") and self._mouse_clicks is not None:
                self._mouse_clicks.stop()
        except Exception:
            pass

    def _parse_sequence_tokens(self, seq: object) -> list[str]:
        tokens: list[str] = []
        if isinstance(seq, (list, tuple)):
            parts = seq
        else:
            raw = str(seq or "").replace(";", ",").replace(" ", ",")
            parts = raw.split(",")
        for part in parts:
            tok = str(part).strip().upper()
            if tok:
                tokens.append(tok)
        return tokens

    def _key_press(self, vk: int) -> None:
        try:
            win32api.keybd_event(int(vk), 0, 0, 0)
            time.sleep(0.01)
            win32api.keybd_event(int(vk), 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def _press_ctrl_v(self) -> None:
        try:
            win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
            time.sleep(0.005)
            win32api.keybd_event(ord("V"), 0, 0, 0)
            time.sleep(0.005)
            win32api.keybd_event(ord("V"), 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.005)
            win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def _paste_text(self, text: str) -> None:
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(str(text), win32con.CF_UNICODETEXT)
        except Exception:
            pass
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
        self._press_ctrl_v()

    def _run_mega_qol_sequence(self) -> None:
        tokens = self._parse_sequence_tokens(self._mega_qol_seq_str)
        delay = max(0, int(self._mega_qol_delay_ms)) / 1000.0
        for tok in tokens:
            vk = self._token_to_vk(tok)
            if vk is None:
                continue
            self._key_press(vk)
            if delay:
                time.sleep(delay)

    def _process_mega_qol_wheel(self, game_in_focus: Optional[bool] = None) -> None:
        if not sys.platform.startswith("win") or self._mouse is None:
            return
        # Always poll to avoid queue growth even when not focused/disabled
        try:
            events = self._mouse.poll()
        except Exception:
            events = []

        any_down = False
        now = time.time()
        for evt in events:
            if evt == "WHEEL_DOWN":
                any_down = True
                self._mega_qol_last_wheel = now

        if not self._mega_qol_enabled:
            return
        if not self._is_feature_allowed("mega_qol_wheel", game_in_focus):
            return
        if self.tab_overlay is not None and self.tab_overlay.is_visible():
            return

        # Rearm after quiet period
        if self._mega_qol_suppress and (now - self._mega_qol_last_wheel) > 0.05:
            self._mega_qol_suppress = False

        # On first event of a burst, emit once and suppress until quiet
        if any_down and not self._mega_qol_suppress:
            self._mega_qol_suppress = True
            try:
                self._run_mega_qol_sequence()
            except Exception:
                pass
