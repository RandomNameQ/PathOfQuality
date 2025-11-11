# PathOfQuality

<p align="center">
  <img src="https://img.shields.io/badge/Windows-10%2B-0078D6?logo=windows&logoColor=white" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Build-PyInstaller-FFDF00" />
</p>

<p align="center">
  <b>Overlay toolkit to speed up routine actions in Path of Exile</b><br/>
  <sub>Created to improve the gaming experience based on my personal time with the game</sub>
</p>

<p align="center">
  <a href="./README.en.md">🇺🇸 English</a> • <a href="./README.ru.md">🇷🇺 Русский</a>
</p>

---

## ✨ Highlights
- 🧭 Scan buffs/debuffs inside a configurable ROI, with a subtle analysis outline
- 🖼️ Copy Areas: live cropped regions; hide on hover; mouse‑wheel square resize
- 🧪 Quick Craft overlay: non‑activating, click‑through, single‑click execution; global/per‑item hotkeys
- 🖱️ Mega QoL: mouse‑wheel down → send a sequence of keys (1–4) with burst suppression
- ⌨️ Double Ctrl: continuous left‑click emulation (stops when you release)
- 🎛️ Floating control dock (bottom‑center by default) for quick Scan/Copy toggles and Settings
- 🧠 Focus policy: “Run only when the game is focused” or allow while this app is focused
- 🧩 Modern UI, grouped tabs (Overview, Library, Tools, Settings)
- 📦 Portable one‑file EXE; settings are external next to the EXE and persist across runs

> Built for Windows. Uses layered, non‑activating windows and low‑level keyboard/mouse hooks. No network calls.

---

## 🚀 Getting Started

### Run from source
```
python -m pip install -r requirements.txt
python app.py
```

### Build a one‑file EXE (recommended)
Option A — helper script:
```
build_exe.bat
```
Outputs: `dist/PathOfQuality.exe` plus `dist/settings.json` and `dist/assets/` for easy edits.

Option B — PyInstaller directly:
```
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name PathOfQuality ^
  --add-data "assets;assets" ^
  --add-data "settings.json;." ^
  app.py
```

---

## 🛠️ Configuration
- ⚙️ Settings live in `settings.json`. In the EXE build, a user‑editable copy sits next to the EXE.
- 🎯 Focus gating list: `assets/allowed_processes.json` — add your game EXE names (e.g. `PathOfExileSteam.exe`).
- 🖼️ Templates: drop PNG/JPG icons into `assets/templates/` (tight crops around the icon).

---

## 💡 Usage Tips
- 👆 Hovering Scan/Copy overlays temporarily hides them to interact with the game UI beneath.
- 📐 During positioning, use the mouse wheel to resize — width and height always change together (perfect square).
- 🧪 Quick Craft overlays are non‑activating; a single left‑click on an overlay runs the action immediately.

---

## 📚 Tabs Overview
- Overview: start/stop scanning, see detected templates
- Library: Buffs, Debuffs, Copy Areas (with per‑item size/position/transparency)
- Tools: Currency (Quick Craft), Mega QoL (wheel→keys, double Ctrl click)
- Settings: ROI selection, focus policy, floating dock visibility/reset, language

---

## 🔧 Troubleshooting
- Overlays visible on taskbar/Alt‑Tab → Fixed via TOOLWINDOW/NOACTIVATE styles; ensure you’re on a recent build
- Quick Craft requires two clicks → Fixed; single click via low‑level mouse hook and non‑activating overlays
- Nothing triggers → add your game EXE to `assets/allowed_processes.json` or uncheck “Run only when the game is focused”

---

## 🤝 A note
This tool was created to improve the gameplay flow. Please use responsibly and follow the game’s Terms of Service.

<p align="center">
  <a href="./README.ru.md">🇷🇺 Читать на русском</a>
</p>
