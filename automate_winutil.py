"""
Automates the full WinUtil screenshot workflow.

Finds the running WinUtil window, maximizes it, selects explicit dark and light
options from ThemeButton, captures both themes, and generates the composite.

Requires admin elevation for the same reason as capture_winutil.py (PrintWindow
across a UIPI boundary needs matching privilege level).
"""
import os
import time
from PIL import ImageStat
from pywinauto.application import Application
from capture_winutil import capture_window, find_winutil_hwnd, get_window_capture_size
from create_composite import process_and_composite

THEME_SETTLE_SECS = 2.0  # time to wait after clicking ThemeButton for WPF to repaint
TAB_SETTLE_SECS = 1.0
MENU_SETTLE_SECS = 0.25
CONTROL_TIMEOUT_SECS = 10


def is_dark_mode(img):
    """Return True if the centre strip of the image looks like a dark theme.

    Samples a horizontal band through the middle and checks average brightness.
    WinUtil dark mode sits around 30-40, light mode near 240+.
    """
    w, h = img.size
    strip = img.crop((w // 4, h // 2 - 10, 3 * w // 4, h // 2 + 10)).convert("L")
    return ImageStat.Stat(strip).mean[0] < 128


def capture_theme(hwnd, width, height, output_path, expected_dark):
    """Capture a theme and fail if the requested theme is not visible."""
    image = capture_window(hwnd, width, height, output_path)
    actual_dark = is_dark_mode(image)
    if actual_dark != expected_dark:
        expected_name = "dark" if expected_dark else "light"
        actual_name = "dark" if actual_dark else "light"
        raise RuntimeError(
            f"Expected {expected_name} mode after toggling ThemeButton, "
            f"but the capture still looks {actual_name}."
        )
    return image


def requested_capture_size():
    """Return a fixed capture size requested through the environment, if any."""
    width_value = os.environ.get("WINUTIL_CAPTURE_WIDTH")
    height_value = os.environ.get("WINUTIL_CAPTURE_HEIGHT")
    if width_value is None and height_value is None:
        return None
    if width_value is None or height_value is None:
        raise RuntimeError(
            "WINUTIL_CAPTURE_WIDTH and WINUTIL_CAPTURE_HEIGHT must be set together."
        )

    try:
        width = int(width_value)
        height = int(height_value)
    except ValueError as exc:
        raise RuntimeError("WinUtil capture dimensions must be integers.") from exc
    if width <= 0 or height <= 0:
        raise RuntimeError("WinUtil capture dimensions must be positive.")
    return width, height


def resize_window(hwnd, width, height):
    """Resize WinUtil beyond the desktop viewport for a fixed-size capture."""
    app = Application(backend="win32").connect(handle=hwnd, timeout=CONTROL_TIMEOUT_SECS)
    win = app.window(handle=hwnd).wrapper_object()
    win.restore()
    win.move_window(x=0, y=0, width=width, height=height, repaint=True)
    time.sleep(0.5)
    return get_window_capture_size(hwnd)


def set_theme(hwnd, theme_name):
    """Open WinUtil's theme popup and select Dark or Light explicitly."""
    if theme_name not in {"Dark", "Light"}:
        raise ValueError(f"Unsupported WinUtil theme: {theme_name!r}")

    # Resolve the UIA tree afresh after every theme change. WPF can replace
    # automation elements while applying a new resource dictionary.
    app = Application(backend="uia").connect(handle=hwnd, timeout=CONTROL_TIMEOUT_SECS)
    win = app.window(handle=hwnd)
    button_spec = win.child_window(auto_id="ThemeButton", control_type="Button")
    try:
        button_spec.wait("exists enabled visible ready", timeout=CONTROL_TIMEOUT_SECS)
        button = button_spec.wrapper_object()
    except Exception as exc:
        title = win.window_text()
        raise RuntimeError(
            f"ThemeButton was not available in HWND {hex(hwnd)} ({title!r}). "
            "Confirm WinUtil is open and run this script at the same elevation level."
        ) from exc

    # WinUtil's theme handler does not react to UIA InvokePattern even though the
    # WPF button advertises it. Send real mouse input to the resolved control.
    win.set_focus()
    button.click_input()
    time.sleep(MENU_SETTLE_SECS)

    deadline = time.monotonic() + CONTROL_TIMEOUT_SECS
    popup_details = []
    while time.monotonic() < deadline:
        popup_windows = [
            candidate
            for candidate in app.windows(visible_only=True)
            if candidate.handle != hwnd
        ]
        popup_details = [
            f"{popup.window_text()!r} ({popup.class_name()})"
            for popup in popup_windows
        ]
        search_roots = [*popup_windows, win.wrapper_object()]
        for root in search_roots:
            matching_controls = root.descendants(title=theme_name)
            if matching_controls:
                matching_controls[0].click_input()
                time.sleep(THEME_SETTLE_SECS)
                return
        time.sleep(0.1)

    visible_popups = ", ".join(popup_details) if popup_details else "none"
    raise RuntimeError(
        f"Theme popup opened, but its {theme_name!r} option was not found "
        "in the refreshed WinUtil UIA tree. "
        f"Visible same-process popup windows: {visible_popups}."
    )


def select_tweaks_tab(hwnd):
    """Select WinUtil's Tweaks tab before taking screenshots."""
    app = Application(backend="uia").connect(handle=hwnd, timeout=CONTROL_TIMEOUT_SECS)
    win = app.window(handle=hwnd)
    tweaks_spec = win.child_window(auto_id="WPFTab2BT", control_type="Button")
    try:
        tweaks_spec.wait("exists enabled visible ready", timeout=CONTROL_TIMEOUT_SECS)
        tweaks_button = tweaks_spec.wrapper_object()
    except Exception as exc:
        raise RuntimeError(
            f"Tweaks tab was not available in HWND {hex(hwnd)}. "
            "Confirm WinUtil is open and run this script at the same elevation level."
        ) from exc

    win.set_focus()
    tweaks_button.click_input()
    time.sleep(TAB_SETTLE_SECS)


def maximize_window(hwnd):
    """Maximize WinUtil using its top-level HWND."""
    import ctypes

    ctypes.windll.user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
    time.sleep(0.5)


def main():
    out_dir   = os.path.dirname(os.path.abspath(__file__))
    dark_png  = os.path.join(out_dir, "winutil-dark.png")
    light_png = os.path.join(out_dir, "winutil-light.png")
    comp_png  = os.path.join(out_dir, "winutil-light-dark-comparison.png")

    # The shared lookup requires WinUtil's WPF HwndWrapper class, so editor and
    # terminal titles containing "winutil" cannot become automation targets.
    print("Locating WinUtil window...")
    hwnd, w, h = find_winutil_hwnd()
    fixed_capture_size = requested_capture_size()

    print("Maximizing window...")
    maximize_window(hwnd)
    # Maximizing changes the HWND bounds, so discard the dimensions returned by
    # the initial lookup and measure the same window again.
    w, h = get_window_capture_size(hwnd)

    print("Selecting Tweaks tab...")
    select_tweaks_tab(hwnd)

    print("Selecting dark mode...")
    set_theme(hwnd, "Dark")

    if fixed_capture_size:
        print(
            f"Resizing WinUtil to {fixed_capture_size[0]}x{fixed_capture_size[1]} "
            "for capture..."
        )
        w, h = resize_window(hwnd, *fixed_capture_size)

    print("Capturing dark mode...")
    capture_theme(hwnd, w, h, dark_png, expected_dark=True)

    if fixed_capture_size:
        # Theme controls at the right edge would be outside the hosted runner's
        # physical desktop while the oversized capture layout is active.
        print("Restoring visible viewport for theme controls...")
        maximize_window(hwnd)

    print("Selecting light mode...")
    set_theme(hwnd, "Light")

    if fixed_capture_size:
        print(
            f"Resizing WinUtil to {fixed_capture_size[0]}x{fixed_capture_size[1]} "
            "for capture..."
        )
        w, h = resize_window(hwnd, *fixed_capture_size)

    print("Capturing light mode...")
    capture_theme(hwnd, w, h, light_png, expected_dark=False)

    print("Generating composite...")
    dark_framed, light_framed = process_and_composite(dark_png, light_png, comp_png)

    print("\nGenerated files:")
    print(f"  Dark Screenshot:       {dark_png}")
    print(f"  Dark Framed:           {dark_framed}")
    print(f"  Light Screenshot:      {light_png}")
    print(f"  Light Framed:          {light_framed}")
    print(f"  Comparison Composite:  {comp_png}")


if __name__ == "__main__":
    main()
