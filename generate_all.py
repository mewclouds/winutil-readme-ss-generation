"""Run the manual fallback for capturing and compositing both WinUtil themes.

Unlike automate_winutil.py, this entry point prompts the user to select each
theme and does not interact with WinUtil through UI Automation.
"""

import os
import sys
import time
from capture_winutil import find_winutil_hwnd, capture_window
from create_composite import process_and_composite

def _assert_fresh_file(path, since, label):
    """Raise if path was not written (or not updated) after `since`."""
    if not os.path.exists(path):
        raise RuntimeError(f"{label} capture did not produce an output file: {path}")
    if os.path.getmtime(path) < since:
        raise RuntimeError(
            f"{label} capture failed: {path} was not updated. "
            "Verify that WinUtil is running and that the terminal is elevated."
        )

def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    dark_png = os.path.join(out_dir, "winutil-dark.png")
    light_png = os.path.join(out_dir, "winutil-light.png")
    comp_png = os.path.join(out_dir, "winutil-light-dark-comparison.png")

    print("WinUtil Screenshot & Comparison Generator\n")

    input("Set WinUtil to DARK MODE, then press Enter to capture...")
    t_dark = time.time()
    hwnd, w, h = find_winutil_hwnd()
    capture_window(hwnd, w, h, dark_png)
    _assert_fresh_file(dark_png, t_dark, "Dark mode")

    input("\nSet WinUtil to LIGHT MODE (do not move or resize window), then press Enter to capture...")
    t_light = time.time()
    hwnd, w, h = find_winutil_hwnd()
    capture_window(hwnd, w, h, light_png)
    _assert_fresh_file(light_png, t_light, "Light mode")

    print("\nProcessing bounds, trimming shadow padding, applying border & compositing...")
    dark_framed_png, light_framed_png = process_and_composite(dark_png, light_png, comp_png)

    print("\nGenerated files:")
    print(f"  Dark Screenshot:       {dark_png}")
    print(f"  Dark Framed:           {dark_framed_png}")
    print(f"  Light Screenshot:      {light_png}")
    print(f"  Light Framed:          {light_framed_png}")
    print(f"  Comparison Composite:  {comp_png}")

if __name__ == "__main__":
    main()
