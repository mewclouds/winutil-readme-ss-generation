"""Write WinUtil window and UI Automation diagnostics to inspect_output.txt.

The inspector uses the same strict WPF window lookup as the capture scripts. It
also clicks ThemeButton so transient theme-menu controls appear in the dump.
Run it at the same elevation level as WinUtil.
"""
import sys
import time
from pywinauto import Desktop
from pywinauto.application import Application
from capture_winutil import find_winutil_hwnd

OUTPUT_FILE = "inspect_output.txt"

def dump_tree(element, depth=0, max_depth=6):
    """Print a bounded UI Automation subtree for diagnostics."""
    if depth > max_depth:
        return
    indent = "  " * depth
    try:
        ctrl_type = element.element_info.control_type
        name      = element.element_info.name or ""
        auto_id   = element.element_info.automation_id or ""
        class_n   = element.element_info.class_name or ""
        print(f"{indent}[{ctrl_type}] name={name!r:40s} auto_id={auto_id!r:30s} class={class_n!r}")
    except Exception as e:
        print(f"{indent}<error: {e}>")
        return
    try:
        for child in element.children():
            dump_tree(child, depth + 1, max_depth)
    except Exception:
        pass

def main():
    print("=== All visible top-level windows (win32 backend) ===")
    wins32 = Desktop(backend="win32").windows()
    for w in wins32:
        try:
            title = w.window_text()
            cls   = w.class_name()
            if w.is_visible():
                print(f"  title={title!r:50s} class={cls!r}")
        except Exception:
            pass

    print("\n=== Looking for WinUtil (shared strict lookup) ===")
    winutil_hwnd, _, _ = find_winutil_hwnd()

    print("\n=== Control tree via UIA backend ===")
    try:
        app = Application(backend="uia").connect(handle=winutil_hwnd)
        win = app.window(handle=winutil_hwnd)
        dump_tree(win)

        print("\n=== Opening theme popup and dumping its UIA tree ===")
        theme_button = win.child_window(
            auto_id="ThemeButton", control_type="Button"
        ).wrapper_object()
        win.set_focus()
        theme_button.click_input()
        time.sleep(0.5)

        print("\n=== Main WinUtil UIA tree with theme popup open ===")
        dump_tree(win)

        popup_windows = [
            candidate
            for candidate in app.windows(visible_only=True)
            if candidate.handle != winutil_hwnd
        ]
        if not popup_windows:
            print("No separate same-process popup window was found.")
        for popup in popup_windows:
            print(
                f"Popup HWND={hex(popup.handle)} "
                f"title={popup.window_text()!r} class={popup.class_name()!r}"
            )
            dump_tree(popup)
    except Exception as e:
        print(f"UIA connect failed: {e}")

if __name__ == "__main__":
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        sys.stdout = f
        main()
        sys.stdout = sys.__stdout__
    print(f"Done. Results written to {OUTPUT_FILE}")
