# Shadow Desktop App

This is a Tauri-based desktop wrapper for the Shadow Python dashboard. It provides a native macOS, Windows, and Linux application that manages the Python Shadow process and wraps the web UI in a native window.

## What is Tauri?

Tauri is a lightweight framework for building desktop applications with web technologies. Unlike Electron, it uses the system's native webview (WebKit on macOS, WebView2 on Windows, WebKit on Linux), resulting in much smaller app bundles and lower memory usage.

## Prerequisites

To build and run the Shadow desktop app, you need:

### All Platforms

1. **Node.js 16+** — for npm/package management
2. **Rust 1.70+** — for Tauri compilation
   - Install via [rustup.rs](https://rustup.rs)
3. **Python 3.10+** — for the Shadow backend
   - Shadow must be installed: `pip install shadow-agent`

### macOS Specific

- Xcode Command Line Tools: `xcode-select --install`
- or Xcode from App Store

### Windows Specific

- Microsoft Visual Studio 2019 or later (Build Tools are sufficient)
- or Visual Studio Community Edition

### Linux Specific

- GTK 3.6+ development libraries
- On Ubuntu/Debian: `sudo apt-get install libgtk-3-dev libwebkit2gtk-4.0-dev`
- On Fedora/RHEL: `sudo dnf install gtk3-devel webkit2gtk3-devel`

## Development

### Install Dependencies

```bash
npm install
```

### Run in Development Mode

```bash
npm run dev
```

This will:
1. Start the Tauri dev server
2. Spawn the Python Shadow process
3. Open the Shadow dashboard in a native window
4. Enable hot-reload for frontend changes

### How It Works

1. **Tauri wraps the web UI** — Tauri's main.rs spawns a webview pointing to `http://127.0.0.1:4747`
2. **Python process management** — On startup, main.rs spawns `python -m shadow` as a subprocess
3. **Readiness check** — The app polls the dashboard URL until it's ready before opening the window
4. **Graceful shutdown** — When the window closes, the Python process is terminated

### Tauri Commands

The Rust backend exposes these commands to the frontend (callable via Tauri invoke):

- `get_shadow_status()` — Returns "running" or "stopped"
- `restart_shadow()` — Kills and respawns the Python process
- `get_python_path()` — Returns the detected Python executable path

Example frontend usage:
```javascript
import { invoke } from '@tauri-apps/api/tauri';

const status = await invoke('get_shadow_status');
console.log(status);  // "running"

await invoke('restart_shadow');
```

## Building

### Create App Icons

First, prepare a 1024x1024 PNG icon and run:

```bash
npm run tauri icon /path/to/icon.png
```

This generates all necessary icon files for each platform.

### Build for Your Platform

```bash
npm run build
```

This creates optimized bundles in `src-tauri/target/release/bundle/`.

### Output Locations

- **macOS**: `src-tauri/target/release/bundle/dmg/Shadow.dmg`
- **Windows**: `src-tauri/target/release/bundle/msi/Shadow_0.1.0_x64_en-US.msi`
- **Linux**: `src-tauri/target/release/bundle/appimage/Shadow_0.1.0_amd64.AppImage`

## Troubleshooting

### "Python not found" Error

The app tries to detect Python using `which python3` or `which python`. If this fails:

1. Verify Python is installed: `python3 --version`
2. Add Python to PATH
3. Or edit `src-tauri/src/main.rs` and hardcode the path to your Python executable

### "Shadow module not found" Error

Install the Shadow package in your Python environment:

```bash
pip install shadow-agent
```

Or for development:

```bash
cd ..  # Go to the Shadow project root
pip install -e ".[intent]"
```

### Dashboard Times Out

- Ensure the Shadow Python package is properly installed
- Check that port 4747 is not in use by another process
- Verify the dashboard can start independently: `python -m shadow dashboard`

### Build Fails on Windows

Ensure you have:
- Visual Studio 2019 or later
- Windows SDK installed
- MSVC v142 or later

On Windows, you may need to run in a Visual Studio Developer PowerShell.

### Build Fails on Linux

Install missing GTK/WebKit development headers:

```bash
# Ubuntu/Debian
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.0-dev

# Fedora/RHEL
sudo dnf install gtk3-devel webkit2gtk3-devel

# Arch
sudo pacman -S gtk3 webkit2gtk
```

## Project Structure

```
tauri/
├── package.json                # Node/npm config
├── src-tauri/                  # Rust application code
│   ├── src/
│   │   ├── main.rs             # Entry point, process management
│   │   └── lib.rs              # Shared types and utilities
│   ├── Cargo.toml              # Rust dependencies
│   ├── tauri.conf.json         # Tauri config (window, bundle, etc.)
│   ├── build.rs                # Build script
│   └── icons/                  # App icons (various formats)
├── dist/                       # Frontend build output (created at build time)
└── README.md                   # This file
```

## Configuration

Edit `src-tauri/tauri.conf.json` to customize:

- **App name and version** — `productName` and `version`
- **Window size** — `app.windows[0].width` and `height`
- **Dashboard URL** — `build.devPath` (for dev, points to http://127.0.0.1:4747)
- **Bundle settings** — Icons, code signing, platform-specific config

## Performance Notes

- Tauri apps are significantly smaller than Electron (typically 30-50MB vs 150-300MB)
- Memory footprint is lower due to native webviews
- Startup time is fast (~1-2s after Python dashboard is ready)
- The bottleneck is usually waiting for the Python process to initialize

## Advanced: Native Commands from Frontend

You can extend main.rs with additional Tauri commands to interact with the OS (file dialogs, notifications, tray menus, etc.). See [Tauri docs](https://tauri.app/docs) for examples.

## License

MIT — same as Shadow
