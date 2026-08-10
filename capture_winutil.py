"""Locate and capture the WinUtil WPF window through Win32 APIs.

Local discovery enumerates multiple Windows desktops and requires both a WinUtil
title and WPF HwndWrapper class. CI may provide WINUTIL_HWND; the supplied handle
is still validated before it is used.
"""

import ctypes
from ctypes import wintypes
import sys
import os
from PIL import Image

# Force Per-Monitor V2 DPI awareness for full physical screen resolution
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x10000000
PW_RENDERFULLCONTENT = 2  # Tells PrintWindow to render off-screen and layered content
DIB_RGB_COLORS = 0
BI_RGB = 0
DWMWA_EXTENDED_FRAME_BOUNDS = 9  # Returns the window rect excluding DWM drop-shadow padding

# Explicit argtypes/restype declarations are required on 64-bit Windows: without them,
# ctypes defaults pointer arguments to c_int (32-bit), silently truncating handles and
# producing crashes or wrong results that are very hard to trace.
user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenInputDesktop.restype = wintypes.HDESK

user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.OpenDesktopW.restype = wintypes.HDESK

user32.SetThreadDesktop.argtypes = [wintypes.HDESK]
user32.SetThreadDesktop.restype = wintypes.BOOL

user32.CloseDesktop.argtypes = [wintypes.HDESK]
user32.CloseDesktop.restype = wintypes.BOOL

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumDesktopWindows.argtypes = [wintypes.HDESK, WNDENUMPROC, wintypes.LPARAM]
user32.EnumDesktopWindows.restype = wintypes.BOOL

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL

user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL

user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
]
dwmapi.DwmGetWindowAttribute.restype = wintypes.DWORD

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.GetDpiForWindow.argtypes = [wintypes.HWND]
user32.GetDpiForWindow.restype = wintypes.UINT

user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
user32.PrintWindow.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

kernel32.GetLastError.argtypes = []
kernel32.GetLastError.restype = wintypes.DWORD

# BITMAPINFOHEADER and BITMAPINFO mirror the Win32 structs used by GetDIBits.
# biHeight is set negative in capture_window to request a top-down DIB. A positive
# biHeight produces a bottom-up bitmap that would appear vertically flipped.
# bmiColors is a variable-length color table. DWORD*3 satisfies the required struct
# alignment for BI_RGB (uncompressed), where the color table is unused but the
# field still needs to exist for GetDIBits to accept the struct.
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', ctypes.c_long),
        ('biHeight', ctypes.c_long),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', ctypes.c_long),
        ('biYPelsPerMeter', ctypes.c_long),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3)
    ]

gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT
]
gdi32.GetDIBits.restype = ctypes.c_int

def find_winutil_hwnd():
    """Return the validated WinUtil HWND and its physical capture dimensions.

    WINUTIL_HWND takes precedence when present. Otherwise, visible top-level
    windows are enumerated across the current, input, and Default desktops.
    """
    explicit_hwnd = os.environ.get("WINUTIL_HWND")
    if explicit_hwnd:
        try:
            hwnd = int(explicit_hwnd, 0)
        except ValueError as exc:
            raise RuntimeError(
                f"WINUTIL_HWND is not a valid window handle: {explicit_hwnd!r}"
            ) from exc

        title_length = user32.GetWindowTextLengthW(hwnd)
        title_buffer = ctypes.create_unicode_buffer(title_length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
        title = title_buffer.value

        class_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buffer, 256)
        class_name = class_buffer.value

        if "winutil" not in title.lower() or "hwndwrapper" not in class_name.lower():
            raise RuntimeError(
                f"WINUTIL_HWND {hex(hwnd)} is not the WinUtil WPF window: "
                f"title={title!r}, class={class_name!r}"
            )

        width, height = get_window_capture_size(hwnd)
        dpi = user32.GetDpiForWindow(hwnd)
        scale = dpi / 96.0 if dpi > 0 else 1.0
        print(
            f"Located explicit HWND: {hex(hwnd)} | Title: '{title}' | "
            f"Class: '{class_name}' | DPI: {dpi} ({scale:.2f}x) | "
            f"Capture Size: {width}x{height}"
        )
        return hwnd, width, height

    # Keyed by HWND so a window matching both branch conditions is never added twice.
    found_dict = {}

    def enum_cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        if w < 100 or h < 100:
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        buf_class = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf_class, 256)
        class_name = buf_class.value

        # WinUtil is a WPF app so its top-level window always uses the HwndWrapper
        # class. Requiring it here prevents false matches on any other window whose
        # title happens to contain "winutil" (e.g. VS Code showing a file from a
        # winutil-related directory).
        if "winutil" in title.lower() and "hwndwrapper" in class_name.lower():
            found_dict[hwnd] = (hwnd, title, class_name, w, h, rect)

        return True

    cb = WNDENUMPROC(enum_cb)

    # EnumWindows covers the desktop associated with this process. Explicitly
    # enumerate the input and Default desktops as well because hosted CI runners
    # can launch GUI processes on Default while a different desktop is considered
    # the input desktop. Enumerating a desktop does not require attaching this
    # thread to it with SetThreadDesktop.
    user32.EnumWindows(cb, 0)
    desktop_handles = [
        user32.OpenInputDesktop(0, False, GENERIC_ALL),
        user32.OpenDesktopW("Default", 0, False, GENERIC_ALL),
    ]
    for desktop_handle in desktop_handles:
        if not desktop_handle:
            continue
        try:
            user32.EnumDesktopWindows(desktop_handle, cb, 0)
        finally:
            user32.CloseDesktop(desktop_handle)

    found_windows = list(found_dict.values())
    if not found_windows:
        raise RuntimeError("Could not find visible WinUtil GUI window!")

    if len(found_windows) > 1:
        print(f"Warning: {len(found_windows)} WinUtil windows found, capturing the largest HwndWrapper.")

    found_windows.sort(key=lambda x: x[3] * x[4], reverse=True)
    best_hwnd, best_title, best_class, w, h, rect = found_windows[0]

    phys_width, phys_height = get_window_capture_size(best_hwnd)
    dpi = user32.GetDpiForWindow(best_hwnd)
    scale = dpi / 96.0 if dpi > 0 else 1.0

    print(
        f"Located HWND: {hex(best_hwnd)} | Title: '{best_title}' | "
        f"Class: '{best_class}' | DPI: {dpi} ({scale:.2f}x) | "
        f"Capture Size: {phys_width}x{phys_height}"
    )
    return best_hwnd, phys_width, phys_height


def get_window_capture_size(hwnd):
    """Return the current physical-pixel capture size for a window."""
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError(f"GetWindowRect failed for HWND {hex(hwnd)}")

    window_width = rect.right - rect.left
    window_height = rect.bottom - rect.top

    rect_dwm = RECT()
    dwm_result = dwmapi.DwmGetWindowAttribute(
        hwnd,
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect_dwm),
        ctypes.sizeof(rect_dwm),
    )
    dwm_width = rect_dwm.right - rect_dwm.left
    dwm_height = rect_dwm.bottom - rect_dwm.top

    # This module opts into Per-Monitor V2 awareness before querying either API,
    # so both rectangles are already physical pixels and must not be DPI-scaled.
    if dwm_result == 0 and dwm_width > 0 and dwm_height > 0:
        return dwm_width, dwm_height
    if window_width > 0 and window_height > 0:
        return window_width, window_height
    raise RuntimeError(f"Window {hex(hwnd)} has invalid bounds")

def capture_window(hwnd, width, height, output_path):
    """Capture an HWND to a validated PNG and return the Pillow image.

    The requested dimensions must describe the current physical window bounds.
    PrintWindow is retried without PW_RENDERFULLCONTENT when the extended capture
    mode fails.
    """
    hdc_win = user32.GetWindowDC(hwnd)
    if not hdc_win:
        raise RuntimeError("Failed GetWindowDC")

    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    if not hdc_mem:
        user32.ReleaseDC(hwnd, hdc_win)
        raise RuntimeError("Failed CreateCompatibleDC")

    hbitmap = gdi32.CreateCompatibleBitmap(hdc_win, width, height)
    if not hbitmap:
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
        raise RuntimeError("Failed CreateCompatibleBitmap")

    old_bmp = gdi32.SelectObject(hdc_mem, hbitmap)

    # PrintWindow with PW_RENDERFULLCONTENT (2)
    success = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
    if not success:
        err = kernel32.GetLastError()
        print(f"PrintWindow(2) returned False (error {err}), falling back to PrintWindow(0)...")
        success = user32.PrintWindow(hwnd, hdc_mem, 0)
        if not success:
            err0 = kernel32.GetLastError()
            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_win)
            raise RuntimeError(f"PrintWindow failed entirely (PW(2) error {err}, PW(0) error {err0}). Note: requires Admin elevation!")

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    # Negative biHeight requests a top-down DIB from GetDIBits. A positive value
    # would produce a bottom-up bitmap, which PIL would load vertically flipped.
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    buffer_size = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_size)

    gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS)

    gdi32.SelectObject(hdc_mem, old_bmp)
    gdi32.DeleteObject(hbitmap)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(hwnd, hdc_win)

    # GDI stores pixels in BGRA order. Passing BGRA tells PIL to reorder channels
    # so the output image has correct colors instead of swapped red and blue.
    img = Image.frombytes("RGBA", (width, height), buffer.raw, "raw", "BGRA")

    if img.size[0] != width or img.size[1] != height:
        raise ValueError(f"Image dimension mismatch: expected {width}x{height}, got {img.size}")

    extrema = img.getextrema()
    r_min, r_max = extrema[0]
    g_min, g_max = extrema[1]
    b_min, b_max = extrema[2]

    if r_max == 0 and g_max == 0 and b_max == 0:
        raise ValueError("Captured image is completely black!")
    if r_min == 255 and g_min == 255 and b_min == 255:
        raise ValueError("Captured image is completely white!")

    img.save(output_path, "PNG")
    print(f"VERIFIED & SAVED: {output_path} ({width}x{height})")
    return img

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "output.png"
    hwnd, w, h = find_winutil_hwnd()
    capture_window(hwnd, w, h, out_file)
