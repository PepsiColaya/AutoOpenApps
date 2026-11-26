# -*- coding: utf-8 -*-
# C++ 版冒烟测试：启动主窗口 -> 截图 -> 找控件
import ctypes, subprocess, sys, time, os, struct
from ctypes import wintypes

EXE = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp\AutoOpenApps.exe"
OUT = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp\shot_main2.bmp"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()  # 观察物理像素，避免逻辑视图误判

def find_window(cls):
    return user32.FindWindowW(cls, None)

def wait_window(cls, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = find_window(cls)
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(0.2)
    return None

def get_text(h):
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, buf, n + 2)
    return buf.value

def child_by_text(parent, text):
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        t = get_text(h)
        if text in t:
            res.append(h)
        return True
    user32.EnumChildWindows(parent, cb, 0)
    return res

def shot(hwnd, path):
    # 纯 ctypes PrintWindow -> DIB -> BMP
    rc = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth = w
    bi.biHeight = -h   # top-down
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0  # BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)  # DIB_RGB_COLORS
    # BGRA -> BGR
    row = w * 3
    pad = (4 - (row % 4)) % 4
    data = bytearray()
    px = buf.raw
    for y in range(h):
        base = y * w * 4
        for x in range(w):
            i = base + x * 4
            data += px[i:i+3]
        data += b"\x00" * pad
    filesize = 54 + len(data)
    hdr = struct.pack("<2sIHHI", b"BM", filesize, 0, 0, 54)
    ih = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 24, 0, len(data), 0, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(hdr + ih + bytes(data))
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)

def main():
    proc = subprocess.Popen([EXE])
    hwnd = wait_window("AutoOpenApps_MainWnd")
    if not hwnd:
        print("FAIL: main window not found")
        sys.exit(1)
    time.sleep(0.8)
    print("main window:", hex(hwnd), get_text(hwnd))
    for t in ["添加软件", "从索引添加", "编辑", "删除", "立即启动", "开机自启"]:
        lst = child_by_text(hwnd, t)
        print(("OK  " if lst else "MISS"), t)
    shot(hwnd, OUT)
    print("shot saved:", OUT, os.path.getsize(OUT), "bytes")
    print("PID:", proc.pid)

if __name__ == "__main__":
    main()
