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
    """Enumerate visible top-level windows to locate the WinUtil GUI HWND."""
    # OpenInputDesktop returns the desktop the user is currently interacting with.
    # When WinUtil runs elevated under UAC, it lives on a separate window station.
    # SetThreadDesktop switches this thread to that station so EnumDesktopWindows
    # can see WinUtil's windows. The fallback to "Default" covers configurations
    # where OpenInputDesktop fails (such as Remote Desktop or service sessions).
    hDesk = user32.OpenInputDesktop(0, False, GENERIC_ALL)
    if not hDesk:
        hDesk = user32.OpenDesktopW("Default", 0, False, GENERIC_ALL)
    if hDesk:
        user32.SetThreadDesktop(hDesk)

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

        # HwndWrapper is the Win32 host window class created by WPF for top-level windows.
        # It is the preferred match because it is the actual render surface.
        # The Cascadia exclusion prevents matching Windows Terminal (the console running
        # this script), whose title also contains "WinUtil" when launched via irm/iex.
        if "winutil" in title.lower() and "hwndwrapper" in class_name.lower():
            found_dict[hwnd] = (hwnd, title, class_name, w, h, rect)
        elif "winutil" in title.lower() and "cascadia" not in class_name.lower():
            found_dict[hwnd] = (hwnd, title, class_name, w, h, rect)

        return True

    cb = WNDENUMPROC(enum_cb)
    if hDesk:
        try:
            user32.EnumDesktopWindows(hDesk, cb, 0)
        finally:
            # Close unconditionally so the handle is released even if the callback raises.
            user32.CloseDesktop(hDesk)
    else:
        user32.EnumWindows(cb, 0)

    found_windows = list(found_dict.values())
    if not found_windows:
        raise RuntimeError("Could not find visible WinUtil GUI window!")

    if len(found_windows) > 1:
        print(f"Warning: {len(found_windows)} WinUtil windows found, capturing the largest HwndWrapper.")

    found_windows.sort(key=lambda x: (1 if "hwndwrapper" in x[2].lower() else 0, x[3] * x[4]), reverse=True)
    best_hwnd, best_title, best_class, w, h, rect = found_windows[0]

    rect_dwm = RECT()
    # DwmGetWindowAttribute with DWMWA_EXTENDED_FRAME_BOUNDS returns the window rect
    # in physical pixels, excluding DWM drop-shadow. If it fails (e.g. window is
    # minimised), rect_dwm stays zeroed and the max() below falls back gracefully.
    dwmapi.DwmGetWindowAttribute(best_hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect_dwm), ctypes.sizeof(rect_dwm))
    dpi = user32.GetDpiForWindow(best_hwnd)
    scale = dpi / 96.0 if dpi > 0 else 1.0

    w_dwm = rect_dwm.right - rect_dwm.left
    h_dwm = rect_dwm.bottom - rect_dwm.top

    # Take a conservative max across logical bounds, DWM bounds, and DPI-scaled dimensions
    # so the capture size is never truncated on high-DPI displays.
    phys_width = max(w, w_dwm, int(w * scale))
    phys_height = max(h, h_dwm, int(h * scale))

    print(f"Located HWND: {hex(best_hwnd)} | Title: '{best_title}' | DPI: {dpi} ({scale:.2f}x) | Capture Size: {phys_width}x{phys_height}")
    return best_hwnd, phys_width, phys_height

def capture_window(hwnd, width, height, output_path):
    """Capture specified HWND directly using PrintWindow with PW_RENDERFULLCONTENT."""
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
