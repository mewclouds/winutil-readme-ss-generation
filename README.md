# WinUtil Screenshot & Light/Dark Comparison Generator

Automated suite to capture high-quality, DPI-aware screenshots of the WinUtil application window and generate a polished, anti-aliased diagonal theme comparison image.

> **Note**: This project is an independent proof of concept built to demonstrate screenshot and composite image automation. I do not own the rights to WinUtil or the original WinUtil repository.

![WinUtil Light and Dark Theme Comparison](./winutil-light-dark-comparison.png)

## Output Artifacts

The tool suite generates output PNG files:
- `winutil-dark.png`: Pure WinUtil window in Dark Mode.
- `winutil-light.png`: Pure WinUtil window in Light Mode.
- `winutil-light-dark-comparison.png`: Composite image split diagonally (`\`) with Light Mode on the upper-left (16% top edge) and Dark Mode on the lower-right (86% bottom edge), framed with a clean 2pt white-grey border.

## Requirements

- **Administrator Terminal**: Must run from an **Elevated PowerShell / Terminal session (Run as administrator)**. WinUtil runs elevated, so Win32 `PrintWindow` calls require administrative privileges to bypass Windows User Interface Privilege Isolation (UIPI).
- **Python 3, Pillow, and pywinauto**: Managed via `uv` or system Python:
   ```bash
   uv run --with pillow --with pywinauto python automate_winutil.py
   ```

## How to Run & Reproduce

- **Launch WinUtil** via PowerShell.
- Open an **Admin Terminal** and navigate to this folder:
   ```powershell
   cd <path-to-this-repo>
   ```
- Run the automated generator to select and capture both themes, then build the
  comparison image:
   ```powershell
   uv run --with pillow --with pywinauto python automate_winutil.py
   ```
- Or run the interactive generator:
   ```powershell
   uv run --with pillow python generate_all.py
   ```
- Follow the prompts:
   - Switch WinUtil to **Dark Mode**, then press `Enter`.
   - Switch WinUtil to **Light Mode** (without moving or resizing the window), then press `Enter`.
- The scripts handle HWND lookup, physical-pixel sizing, shadow margin trimming,
  diagonal compositing, and 2pt border framing.

## Architecture & Capture Details

- **HWND Lookup**: Enumerates top-level Win32 windows using `EnumDesktopWindows` looking for title `WinUtil` and class `HwndWrapper`.
- **DPI Awareness**: Calls `SetProcessDpiAwarenessContext(-4)` (Per-Monitor V2) to ensure 100% native physical pixel rendering (handling 125%, 150%, 200% Windows display scaling).
- **PrintWindow P/Invoke**: Captures the HWND surface directly via `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` (`2`), capturing only the WinUtil window without background desktop or terminal bleed.
- **DWM Shadow Trim**: Auto-detects and crops away outer black DWM window drop-shadow margins.
- **Anti-Aliased Diagonal Mask**: Generates the `\` diagonal boundary at 4x resolution and downsamples using `LANCZOS` for smooth anti-aliased edge transitions.
