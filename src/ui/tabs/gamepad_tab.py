"""Gamepad tab with Test / Bind / Behaviour sub-tabs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

from src.i18n.locale import t
from src.ui.styles import BG_COLOR


class GamepadTab:
    """Gamepad configuration with three sub-tabs: Test, Bind, Behaviour."""

    def __init__(
        self,
        parent: tk.Frame,
        enabled: bool = True,
        preferred_index: int = -1,
        poll_interval_ms: int = 33,
        log_max_items: int = 200,
        bindings: Optional[List[Dict[str, Any]]] = None,
        wasd_enabled: bool = False,
        wasd_stick: str = "left",
        wasd_center_offset_x: int = 0,
        wasd_center_offset_y: int = 0,
        wasd_move_offset_pixels: int = 100,
        wasd_enable_skill_cursor: bool = False,
        wasd_distance_skill: int = 0,
        wasd_skill_cursor_delay_s: float = 0.0,
        wasd_input_delay_s: float = 0.0,
    ) -> None:
        self.frame = parent
        self._on_change: Callable[[], None] | None = None
        self._log_max_items = log_max_items
        self._log_lines: List[str] = []
        self._bindings: List[Dict[str, Any]] = []
        for b in (bindings or []):
            self._bindings.append({
                "gamepad_button": str(b.get("gamepad_button", "")),
                "key": str(b.get("key", "")),
                "enabled": bool(b.get("enabled", True)),
            })

        self._enabled_var = tk.BooleanVar(value=bool(enabled))
        idx_str = "Auto" if preferred_index == -1 else str(preferred_index)
        self._preferred_index_var = tk.StringVar(value=idx_str)
        self._poll_interval_var = tk.IntVar(value=max(1, int(poll_interval_ms)))

        self._status_var = tk.StringVar(value="unavailable")
        self._connected_var = tk.StringVar(value="none")
        self._active_var = tk.StringVar(value="-")
        self._buttons_var = tk.StringVar(value="none")
        self._axes_var = tk.StringVar(value="-")
        self._rs_axes_var = tk.StringVar(value="-")
        self._triggers_var = tk.StringVar(value="-")

        self._wasd_enabled_var = tk.BooleanVar(value=bool(wasd_enabled))
        self._wasd_stick_var = tk.StringVar(value=wasd_stick)
        self._wasd_center_offset_x_var = tk.IntVar(value=int(wasd_center_offset_x))
        self._wasd_center_offset_y_var = tk.IntVar(value=int(wasd_center_offset_y))
        self._wasd_move_offset_var = tk.IntVar(value=max(0, int(wasd_move_offset_pixels)))
        self._wasd_skill_cursor_var = tk.BooleanVar(value=bool(wasd_enable_skill_cursor))
        self._wasd_distance_skill_var = tk.IntVar(value=max(0, int(wasd_distance_skill)))
        self._wasd_skill_delay_var = tk.DoubleVar(
            value=max(0.0, float(wasd_skill_cursor_delay_s))
        )
        self._wasd_input_delay_var = tk.DoubleVar(
            value=max(0.0, float(wasd_input_delay_s))
        )

        self._listen_state: str = "idle"
        self._pending_gp_button: str = ""
        self._rebind_index: int = -1

        self._create_widgets()

    # ── widget creation ─────────────────────────────────────────

    def _create_widgets(self) -> None:
        container = tk.Frame(self.frame, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=6, pady=6)

        settings_row = ttk.Frame(container)
        settings_row.pack(fill="x", pady=(0, 4))

        self._chk_enable = ttk.Checkbutton(
            settings_row,
            text=t("gamepad.enable", "Enable Gamepad"),
            variable=self._enabled_var,
            command=self._notify_change,
            style="ToggleGray.TCheckbutton",
        )
        self._chk_enable.pack(side="left", padx=(4, 12))

        self._lbl_pref_index = ttk.Label(
            settings_row,
            text=t("gamepad.preferred_index", "Preferred Index"),
            style="Prompt.TLabel",
        )
        self._lbl_pref_index.pack(side="left", padx=(0, 4))
        idx_combo = ttk.Combobox(
            settings_row,
            textvariable=self._preferred_index_var,
            values=["Auto", "0", "1", "2", "3"],
            state="readonly",
            width=5,
        )
        idx_combo.pack(side="left", padx=(0, 12))
        idx_combo.bind("<<ComboboxSelected>>", lambda _e: self._notify_change())

        self._lbl_poll = ttk.Label(
            settings_row,
            text=t("gamepad.poll_interval_ms", "Poll interval (ms)"),
            style="Prompt.TLabel",
        )
        self._lbl_poll.pack(side="left", padx=(0, 4))
        spn_poll = ttk.Spinbox(
            settings_row, from_=1, to=1000, increment=1,
            textvariable=self._poll_interval_var, width=5,
        )
        spn_poll.pack(side="left")
        spn_poll.bind("<FocusOut>", lambda _e: self._notify_change())
        spn_poll.bind("<Return>", lambda _e: self._notify_change())

        self._inner_nb = ttk.Notebook(container, style="TNotebook")
        self._inner_nb.pack(fill="both", expand=True, pady=(4, 0))

        self._test_frame = tk.Frame(self._inner_nb, bg=BG_COLOR)
        self._bind_frame = tk.Frame(self._inner_nb, bg=BG_COLOR)
        self._behaviour_frame = tk.Frame(self._inner_nb, bg=BG_COLOR)

        self._inner_nb.add(self._test_frame, text=t("gamepad.tab_test", "Test"))
        self._inner_nb.add(self._bind_frame, text=t("gamepad.tab_bind", "Bind"))
        self._inner_nb.add(
            self._behaviour_frame, text=t("gamepad.tab_behaviour", "Behaviour")
        )

        self._build_test_tab()
        self._build_bind_tab()
        self._build_behaviour_tab()

    # ── Test tab ────────────────────────────────────────────────

    def _build_test_tab(self) -> None:
        f = self._test_frame

        self._diag_group = ttk.LabelFrame(
            f, text=t("gamepad.diagnostics", "Diagnostics"), padding=(12, 8)
        )
        self._diag_group.pack(fill="x", padx=8, pady=(8, 4))

        def add_row(parent: tk.Widget, key: str, default: str, var: tk.StringVar) -> ttk.Label:
            row = ttk.Frame(parent)
            row.pack(fill="x", pady=1)
            lbl = ttk.Label(row, text=t(key, default), width=18, style="Prompt.TLabel")
            lbl.pack(side="left")
            ttk.Label(row, textvariable=var).pack(side="left", fill="x", expand=True)
            return lbl

        self._lbl_status = add_row(self._diag_group, "gamepad.status", "Status:", self._status_var)
        self._lbl_connected = add_row(self._diag_group, "gamepad.connected", "Connected:", self._connected_var)
        self._lbl_active = add_row(self._diag_group, "gamepad.active", "Active Index:", self._active_var)
        self._lbl_buttons = add_row(self._diag_group, "gamepad.buttons", "Buttons:", self._buttons_var)
        self._lbl_axes = add_row(self._diag_group, "gamepad.left_stick", "L-Stick (X,Y):", self._axes_var)
        self._lbl_rs_axes = add_row(self._diag_group, "gamepad.right_stick", "R-Stick (X,Y):", self._rs_axes_var)
        self._lbl_triggers = add_row(self._diag_group, "gamepad.triggers", "Triggers (L,R):", self._triggers_var)

        self._log_group = ttk.LabelFrame(
            f, text=t("gamepad.log", "Event Log"), padding=(12, 8)
        )
        self._log_group.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        toolbar = ttk.Frame(self._log_group)
        toolbar.pack(fill="x", pady=(0, 4))
        self._btn_clear = ttk.Button(
            toolbar, text=t("gamepad.log_clear", "Clear Log"),
            command=self._clear_log, width=10,
        )
        self._btn_clear.pack(side="right")

        list_frame = ttk.Frame(self._log_group)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self._log_listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, height=6, activestyle="none",
        )
        self._log_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._log_listbox.yview)

    # ── Bind tab ────────────────────────────────────────────────

    def _build_bind_tab(self) -> None:
        f = self._bind_frame

        top_bar = ttk.Frame(f)
        top_bar.pack(fill="x", padx=8, pady=(8, 4))

        self._btn_listen = ttk.Button(
            top_bar,
            text=t("gamepad.listen_gamepad", "Listen gamepad button"),
            command=self._start_listen_gamepad,
        )
        self._btn_listen.pack(side="left", padx=(0, 8))

        self._lbl_listen_status = ttk.Label(top_bar, text="", style="Prompt.TLabel")
        self._lbl_listen_status.pack(side="left", fill="x", expand=True)

        self._btn_cancel_listen = ttk.Button(
            top_bar, text=t("dialog.cancel", "Cancel"),
            command=self._cancel_listen,
        )

        self._bind_scroll_frame = ttk.Frame(f)
        self._bind_scroll_frame.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        canvas = tk.Canvas(self._bind_scroll_frame, bg=BG_COLOR, highlightthickness=0)
        sb = ttk.Scrollbar(self._bind_scroll_frame, orient="vertical", command=canvas.yview)
        self._bind_list_frame = tk.Frame(canvas, bg=BG_COLOR)
        self._bind_list_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._bind_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._bind_canvas = canvas

        btn_bar = ttk.Frame(f)
        btn_bar.pack(fill="x", padx=8, pady=(0, 8))
        self._btn_bind_delete = ttk.Button(
            btn_bar, text=t("gamepad.bind_delete", "Delete selected"),
            command=self._delete_selected_binding,
        )
        self._btn_bind_delete.pack(side="right")

        self._selected_bind_idx: int = -1
        self._refresh_bindings_list()

    def _refresh_bindings_list(self) -> None:
        for w in self._bind_list_frame.winfo_children():
            w.destroy()

        if not self._bindings:
            ttk.Label(
                self._bind_list_frame, text="No bindings", style="Prompt.TLabel"
            ).pack(anchor="w", padx=8, pady=4)
            return

        for idx, b in enumerate(self._bindings):
            row = tk.Frame(self._bind_list_frame, bg=BG_COLOR)
            row.pack(fill="x", pady=1, padx=4)

            enabled_var = tk.BooleanVar(value=b.get("enabled", True))

            def _make_toggle(i: int, v: tk.BooleanVar):
                def _toggle():
                    self._bindings[i]["enabled"] = v.get()
                    self._notify_change()
                return _toggle

            chk = ttk.Checkbutton(
                row, variable=enabled_var,
                command=_make_toggle(idx, enabled_var),
                style="ToggleGray.TCheckbutton",
            )
            chk.pack(side="left", padx=(0, 4))

            gp_lbl = ttk.Label(
                row, text=b.get("gamepad_button", "?"),
                width=12, anchor="center",
            )
            gp_lbl.pack(side="left", padx=(0, 8))

            ttk.Label(row, text="→").pack(side="left", padx=(0, 8))

            kb_lbl = ttk.Label(
                row, text=b.get("key", "?"),
                width=14, anchor="center",
            )
            kb_lbl.pack(side="left", padx=(0, 4))

            def _make_rebind(i: int):
                def _rebind():
                    self._start_rebind(i)
                return _rebind

            ttk.Button(
                row, text=t("gamepad.rebind", "Rebind"),
                command=_make_rebind(idx), width=7,
            ).pack(side="left", padx=(4, 4))

            def _make_select(i: int, r: tk.Frame):
                def _select(e=None):
                    self._selected_bind_idx = i
                    for child in self._bind_list_frame.winfo_children():
                        child.configure(bg=BG_COLOR)
                    r.configure(bg="#3a3a5a")
                return _select

            row.bind("<Button-1>", _make_select(idx, row))
            gp_lbl.bind("<Button-1>", _make_select(idx, row))
            kb_lbl.bind("<Button-1>", _make_select(idx, row))

    # ── Behaviour tab ───────────────────────────────────────────

    def _build_behaviour_tab(self) -> None:
        f = self._behaviour_frame
        container = tk.Frame(f, bg=BG_COLOR)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        self._beh_group = ttk.LabelFrame(
            container, text=t("gamepad.wasd_title", "Gamepad WASD Movement"),
            padding=(12, 8),
        )
        self._beh_group.pack(fill="x")

        self._chk_wasd = ttk.Checkbutton(
            self._beh_group,
            text=t("gamepad.enable_wasd", "Enable WASD gamepad"),
            variable=self._wasd_enabled_var,
            command=self._notify_change,
            style="ToggleGray.TCheckbutton",
        )
        self._chk_wasd.pack(anchor="w", pady=(0, 4))

        stick_row = ttk.Frame(self._beh_group, padding=(0, 4))
        stick_row.pack(fill="x")
        self._lbl_stick_choice = ttk.Label(
            stick_row, text=t("gamepad.stick_choice", "Movement stick"),
            style="Prompt.TLabel",
        )
        self._lbl_stick_choice.pack(side="left", padx=(0, 8))
        self._rb_left = ttk.Radiobutton(
            stick_row, text=t("gamepad.stick_left", "Left stick"),
            variable=self._wasd_stick_var, value="left",
            command=self._notify_change,
        )
        self._rb_left.pack(side="left", padx=(0, 12))
        self._rb_right = ttk.Radiobutton(
            stick_row, text=t("gamepad.stick_right", "Right stick"),
            variable=self._wasd_stick_var, value="right",
            command=self._notify_change,
        )
        self._rb_right.pack(side="left")

        offset_row = ttk.Frame(self._beh_group, padding=(0, 8))
        offset_row.pack(fill="x")
        self._lbl_cx = ttk.Label(offset_row, text=t("wasd.center_offset_x", "Center offset X"), style="Prompt.TLabel")
        self._lbl_cx.pack(side="left", padx=(0, 4))
        ttk.Spinbox(offset_row, from_=-1000, to=1000, increment=1, textvariable=self._wasd_center_offset_x_var, width=7).pack(side="left", padx=(0, 12))
        self._lbl_cy = ttk.Label(offset_row, text=t("wasd.center_offset_y", "Center offset Y"), style="Prompt.TLabel")
        self._lbl_cy.pack(side="left", padx=(0, 4))
        ttk.Spinbox(offset_row, from_=-1000, to=1000, increment=1, textvariable=self._wasd_center_offset_y_var, width=7).pack(side="left")

        dist_row = ttk.Frame(self._beh_group, padding=(0, 4))
        dist_row.pack(fill="x")
        self._lbl_move_offset = ttk.Label(dist_row, text=t("wasd.move_offset_pixels", "Move offset (px)"), style="Prompt.TLabel")
        self._lbl_move_offset.pack(side="left", padx=(0, 4))
        ttk.Spinbox(dist_row, from_=0, to=1000, increment=1, textvariable=self._wasd_move_offset_var, width=7).pack(side="left")

        skill_row = ttk.Frame(self._beh_group, padding=(0, 4))
        skill_row.pack(fill="x")
        self._chk_skill = ttk.Checkbutton(skill_row, text=t("wasd.enable_skill_cursor", "Enable skill cursor"), variable=self._wasd_skill_cursor_var, command=self._notify_change, style="ToggleGray.TCheckbutton")
        self._chk_skill.pack(side="left", padx=(0, 12))
        self._lbl_dist_skill = ttk.Label(skill_row, text=t("wasd.distance_skill", "Distance skill (%)"), style="Prompt.TLabel")
        self._lbl_dist_skill.pack(side="left", padx=(0, 4))
        ttk.Spinbox(skill_row, from_=0, to=100, increment=1, textvariable=self._wasd_distance_skill_var, width=7).pack(side="left")

        delay_row = ttk.Frame(self._beh_group, padding=(0, 4))
        delay_row.pack(fill="x")
        self._lbl_skill_delay = ttk.Label(delay_row, text=t("wasd.skill_cursor_delay_s", "Skill cursor delay (s)"), style="Prompt.TLabel")
        self._lbl_skill_delay.pack(side="left", padx=(0, 4))
        ttk.Spinbox(delay_row, from_=0.0, to=10.0, increment=0.05, textvariable=self._wasd_skill_delay_var, width=7).pack(side="left", padx=(0, 12))
        self._lbl_input_delay = ttk.Label(delay_row, text=t("wasd.input_delay_s", "Input delay (s)"), style="Prompt.TLabel")
        self._lbl_input_delay.pack(side="left", padx=(0, 4))
        ttk.Spinbox(delay_row, from_=0.0, to=10.0, increment=0.01, textvariable=self._wasd_input_delay_var, width=7).pack(side="left")

    # ── Bind logic ──────────────────────────────────────────────

    def _start_listen_gamepad(self) -> None:
        self._listen_state = "waiting_gamepad"
        self._pending_gp_button = ""
        self._rebind_index = -1
        self._lbl_listen_status.configure(
            text=t("gamepad.waiting_gamepad", "Press any gamepad button...")
        )
        self._btn_listen.configure(state="disabled")
        self._btn_cancel_listen.pack(side="left", padx=(4, 0))

    def _start_rebind(self, idx: int) -> None:
        self._listen_state = "waiting_keyboard"
        self._rebind_index = idx
        self._pending_gp_button = self._bindings[idx].get("gamepad_button", "")
        self._lbl_listen_status.configure(
            text=f"Rebind {self._pending_gp_button} → "
            + t("gamepad.waiting_keyboard", "Press any keyboard or mouse button...")
        )
        self._btn_listen.configure(state="disabled")
        self._btn_cancel_listen.pack(side="left", padx=(4, 0))
        self._bind_frame.focus_set()
        self._bind_frame.bind("<Key>", self._on_key_captured)
        self._bind_frame.bind("<Button>", self._on_mouse_captured)

    def _start_listen_keyboard(self) -> None:
        self._listen_state = "waiting_keyboard"
        self._lbl_listen_status.configure(
            text=f"Gamepad: {self._pending_gp_button} → "
            + t("gamepad.waiting_keyboard", "Press any keyboard or mouse button...")
        )
        self._bind_frame.focus_set()
        self._bind_frame.bind("<Key>", self._on_key_captured)
        self._bind_frame.bind("<Button>", self._on_mouse_captured)

    def _cancel_listen(self) -> None:
        self._listen_state = "idle"
        self._pending_gp_button = ""
        self._rebind_index = -1
        self._lbl_listen_status.configure(text="")
        self._btn_listen.configure(state="normal")
        self._btn_cancel_listen.pack_forget()
        try:
            self._bind_frame.unbind("<Key>")
            self._bind_frame.unbind("<Button>")
        except Exception:
            pass

    def on_gamepad_button_for_listen(self, button_name: str) -> bool:
        if self._listen_state != "waiting_gamepad":
            return False
        self._pending_gp_button = button_name
        self._start_listen_keyboard()
        return True

    def _on_key_captured(self, event: tk.Event) -> None:
        if self._listen_state != "waiting_keyboard":
            return
        self._finish_binding(event.keysym)

    def _on_mouse_captured(self, event: tk.Event) -> None:
        if self._listen_state != "waiting_keyboard":
            return
        mouse_names = {1: "Mouse1", 2: "Mouse3", 3: "Mouse2", 4: "Mouse4", 5: "Mouse5"}
        self._finish_binding(mouse_names.get(event.num, f"Mouse{event.num}"))

    def _finish_binding(self, key_name: str) -> None:
        if not self._pending_gp_button:
            self._cancel_listen()
            return

        if self._rebind_index >= 0 and self._rebind_index < len(self._bindings):
            self._bindings[self._rebind_index]["key"] = key_name
        else:
            for b in self._bindings:
                if b.get("gamepad_button") == self._pending_gp_button:
                    b["key"] = key_name
                    break
            else:
                self._bindings.append({
                    "gamepad_button": self._pending_gp_button,
                    "key": key_name,
                    "enabled": True,
                })

        self._cancel_listen()
        self._refresh_bindings_list()
        self._notify_change()

    def _delete_selected_binding(self) -> None:
        idx = self._selected_bind_idx
        if 0 <= idx < len(self._bindings):
            del self._bindings[idx]
            self._selected_bind_idx = -1
            self._refresh_bindings_list()
            self._notify_change()

    # ── snapshot / events ───────────────────────────────────────

    def set_snapshot(self, snapshot: Dict[str, Any]) -> None:
        try:
            self._status_var.set(str(snapshot.get("status", "unavailable")))
            connected = snapshot.get("connected_indices", [])
            self._connected_var.set(",".join(map(str, connected)) if connected else "none")
            active = snapshot.get("active_index")
            self._active_var.set(str(active) if active is not None else "auto")
            buttons = snapshot.get("buttons", [])
            self._buttons_var.set(",".join(buttons) if buttons else "none")
            ls = snapshot.get("left_stick")
            self._axes_var.set(f"{ls[0]:.2f}, {ls[1]:.2f}" if ls else "-")
            rs = snapshot.get("right_stick")
            self._rs_axes_var.set(f"{rs[0]:.2f}, {rs[1]:.2f}" if rs else "-")
            tr = snapshot.get("triggers")
            self._triggers_var.set(f"{tr[0]:.2f}, {tr[1]:.2f}" if tr else "-")
        except Exception:
            pass

    def append_events(self, events: List[str]) -> None:
        if not events:
            return
        for ev in events:
            self._log_lines.append(ev)
        if len(self._log_lines) > self._log_max_items:
            self._log_lines = self._log_lines[-self._log_max_items:]
        self._update_log_ui()
        for ev in events:
            parts = ev.split()
            if len(parts) >= 2 and parts[1] == "down":
                self.on_gamepad_button_for_listen(parts[0])

    def _update_log_ui(self) -> None:
        try:
            self._log_listbox.delete(0, tk.END)
            for line in self._log_lines:
                self._log_listbox.insert(tk.END, line)
            self._log_listbox.see(tk.END)
        except Exception:
            pass

    def _clear_log(self) -> None:
        self._log_lines.clear()
        self._update_log_ui()

    # ── public API ──────────────────────────────────────────────

    def set_change_handler(self, callback: Callable[[], None]) -> None:
        self._on_change = callback

    def _notify_change(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def get_config(self) -> Dict[str, Any]:
        idx_str = self._preferred_index_var.get()
        idx = -1 if idx_str == "Auto" else int(idx_str)
        try:
            poll = int(self._poll_interval_var.get())
        except Exception:
            poll = 33
        return {
            "enabled": self._enabled_var.get(),
            "preferred_index": idx,
            "poll_interval_ms": poll,
            "log_max_items": self._log_max_items,
            "bindings": [dict(b) for b in self._bindings],
            "wasd_enabled": self._wasd_enabled_var.get(),
            "wasd_stick": self._wasd_stick_var.get(),
            "wasd_center_offset_x": self._wasd_center_offset_x_var.get(),
            "wasd_center_offset_y": self._wasd_center_offset_y_var.get(),
            "wasd_move_offset_pixels": self._wasd_move_offset_var.get(),
            "wasd_enable_skill_cursor": self._wasd_skill_cursor_var.get(),
            "wasd_distance_skill": self._wasd_distance_skill_var.get(),
            "wasd_skill_cursor_delay_s": self._wasd_skill_delay_var.get(),
            "wasd_input_delay_s": self._wasd_input_delay_var.get(),
        }

    def get_log_lines(self) -> List[str]:
        return list(self._log_lines)

    def get_bindings(self) -> List[Dict[str, Any]]:
        return [dict(b) for b in self._bindings]

    # ── i18n ────────────────────────────────────────────────────

    def refresh_texts(self) -> None:
        try:
            self._chk_enable.configure(text=t("gamepad.enable", "Enable Gamepad"))
            self._lbl_pref_index.configure(text=t("gamepad.preferred_index", "Preferred Index"))
            self._lbl_poll.configure(text=t("gamepad.poll_interval_ms", "Poll interval (ms)"))
            self._inner_nb.tab(self._test_frame, text=t("gamepad.tab_test", "Test"))
            self._inner_nb.tab(self._bind_frame, text=t("gamepad.tab_bind", "Bind"))
            self._inner_nb.tab(self._behaviour_frame, text=t("gamepad.tab_behaviour", "Behaviour"))
            self._diag_group.configure(text=t("gamepad.diagnostics", "Diagnostics"))
            self._lbl_status.configure(text=t("gamepad.status", "Status:"))
            self._lbl_connected.configure(text=t("gamepad.connected", "Connected:"))
            self._lbl_active.configure(text=t("gamepad.active", "Active Index:"))
            self._lbl_buttons.configure(text=t("gamepad.buttons", "Buttons:"))
            self._lbl_axes.configure(text=t("gamepad.left_stick", "L-Stick (X,Y):"))
            self._lbl_rs_axes.configure(text=t("gamepad.right_stick", "R-Stick (X,Y):"))
            self._lbl_triggers.configure(text=t("gamepad.triggers", "Triggers (L,R):"))
            self._log_group.configure(text=t("gamepad.log", "Event Log"))
            self._btn_clear.configure(text=t("gamepad.log_clear", "Clear Log"))
            self._btn_listen.configure(text=t("gamepad.listen_gamepad", "Listen gamepad button"))
            self._btn_bind_delete.configure(text=t("gamepad.bind_delete", "Delete selected"))
            self._beh_group.configure(text=t("gamepad.wasd_title", "Gamepad WASD Movement"))
            self._chk_wasd.configure(text=t("gamepad.enable_wasd", "Enable WASD gamepad"))
            self._lbl_stick_choice.configure(text=t("gamepad.stick_choice", "Movement stick"))
            self._rb_left.configure(text=t("gamepad.stick_left", "Left stick"))
            self._rb_right.configure(text=t("gamepad.stick_right", "Right stick"))
            self._lbl_cx.configure(text=t("wasd.center_offset_x", "Center offset X"))
            self._lbl_cy.configure(text=t("wasd.center_offset_y", "Center offset Y"))
            self._lbl_move_offset.configure(text=t("wasd.move_offset_pixels", "Move offset (px)"))
            self._chk_skill.configure(text=t("wasd.enable_skill_cursor", "Enable skill cursor"))
            self._lbl_dist_skill.configure(text=t("wasd.distance_skill", "Distance skill (%)"))
            self._lbl_skill_delay.configure(text=t("wasd.skill_cursor_delay_s", "Skill cursor delay (s)"))
            self._lbl_input_delay.configure(text=t("wasd.input_delay_s", "Input delay (s)"))
        except Exception:
            pass
