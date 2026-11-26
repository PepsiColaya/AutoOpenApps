# -*- coding: utf-8 -*-
# C++ 版完整流程测试：索引添加 / 编辑添加 / 星期过滤 / 倒计时自动启动
import ctypes, subprocess, sys, time, os
from ctypes import wintypes

EXE = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp\AutoOpenApps.exe"
CPP = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp"
APPDATA_CFG = os.path.join(os.environ["APPDATA"], "AutoOpenApps")
APPS_TXT = os.path.join(APPDATA_CFG, "apps.txt")
CONFIG_TXT = os.path.join(APPDATA_CFG, "config.txt")

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDPIAware()

BM_CLICK = 0x00F5
WM_CLOSE = 0x0010
LVM_GETITEMCOUNT = 0x1004

def get_text(h):
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, buf, n + 2)
    return buf.value

def find_window(cls):
    return user32.FindWindowW(cls, None)

def wait_window(cls, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = find_window(cls)
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(0.2)
    return None

def wait_gone(cls, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not find_window(cls):
            return True
        time.sleep(0.2)
    return False

def child_by_text(parent, text):
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        if text in get_text(h):
            res.append(h)
        return True
    user32.EnumChildWindows(parent, cb, 0)
    return res

def shot(hwnd, path):
    rc = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rc))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)
    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH); bi.biWidth = w; bi.biHeight = -h
    bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
    row = w * 3; pad = (4 - (row % 4)) % 4
    data = bytearray(); px = buf.raw
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
    gdi32.SelectObject(mem, old); gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)

import struct  # noqa

# ---- SendInput（模拟真实键盘/鼠标） ----
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]
KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002
INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
LEFTDOWN, LEFTUP, ABSOLUTE, MOVE = 0x0002, 0x0004, 0x8000, 0x0001

def _send(i):
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))

def type_text(s):
    for ch in s:
        i = INPUT(); i.type = INPUT_KEYBOARD
        i.u.ki.wScan = ord(ch); i.u.ki.dwFlags = KEYEVENTF_UNICODE
        _send(i)
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        _send(i)
        time.sleep(0.005)

def click_hwnd(h):
    rc = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(rc))
    cx = (rc.left + rc.right) // 2
    cy = (rc.top + rc.bottom) // 2
    sw = user32.GetSystemMetrics(0); sh = user32.GetSystemMetrics(1)
    i = INPUT(); i.type = INPUT_MOUSE
    i.u.mi.dx = int(cx * 65536 / sw); i.u.mi.dy = int(cy * 65536 / sh)
    i.u.mi.dwFlags = MOVE | ABSOLUTE
    _send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTDOWN
    _send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTUP
    _send(i)
    time.sleep(0.15)

def cleanup_cfg():
    for p in (APPS_TXT, CONFIG_TXT):
        if os.path.exists(p):
            os.remove(p)

def main():
    cleanup_cfg()
    proc = subprocess.Popen([EXE])
    hwnd = wait_window("AutoOpenApps_MainWnd")
    if not hwnd:
        print("FAIL: no main window"); sys.exit(1)
    time.sleep(0.6)
    print("[1] main window ok")

    # --- 从索引添加 ---
    btn = child_by_text(hwnd, "从索引添加")
    user32.PostMessageW(btn[0], BM_CLICK, 0, 0)
    idx = wait_window("AutoOpenApps_IndexDlg", 15)
    if not idx:
        print("FAIL: index dialog not shown"); sys.exit(1)
    time.sleep(0.5)
    lv = user32.GetDlgItem(idx, 4003)
    n = user32.SendMessageW(lv, LVM_GETITEMCOUNT, 0, 0)
    print("[2] index dialog ok, installed apps found:", n)
    shot(idx, os.path.join(CPP, "shot_index.bmp"))
    user32.PostMessageW(idx, WM_CLOSE, 0, 0)
    time.sleep(0.5)

    # --- 添加软件（编辑对话框，真实键盘输入）---
    btn = child_by_text(hwnd, "添加软件")
    click_hwnd(btn[0])
    ed = wait_window("AutoOpenApps_EditDlg", 8)
    if not ed:
        print("FAIL: edit dialog not shown"); sys.exit(1)
    print("[3] edit dialog ok")
    user32.SetForegroundWindow(ed)
    time.sleep(0.3)
    click_hwnd(user32.GetDlgItem(ed, 3001))
    type_text("测试-记事本")
    click_hwnd(user32.GetDlgItem(ed, 3002))
    type_text(r"C:\Windows\System32\notepad.exe")
    click_hwnd(user32.GetDlgItem(ed, 3017))  # 确定
    time.sleep(1.0)
    if not os.path.exists(APPS_TXT):
        print("FAIL: apps.txt not created"); sys.exit(1)
    content = open(APPS_TXT, encoding="utf-8-sig").read()
    print("[4] apps.txt saved:", repr(content.strip()[:120]))
    if "notepad.exe" not in content:
        print("FAIL: apps.txt missing notepad"); sys.exit(1)

    # --- 追加星期测试项（直接写文件，验证读取与过滤）---
    with open(APPS_TXT, "a", encoding="utf-8") as f:
        f.write("测试-周五软件\tC:\\Windows\\System32\\notepad.exe\t16\t1\n")   # bit4=周五
        f.write("测试-周六软件\tC:\\Windows\\System32\\notepad.exe\t32\t1\n")   # bit5=周六

    # --- --auto 确认窗口：今天周五，应显示 2 项（记事本+周五软件），不含周六软件 ---
    auto = subprocess.Popen([EXE, "--auto"])
    conf = wait_window("AutoOpenApps_ConfirmWnd", 10)
    if not conf:
        print("FAIL: confirm window not shown"); sys.exit(1)
    time.sleep(0.4)
    clv = user32.GetDlgItem(conf, 5001)
    rows = user32.SendMessageW(clv, LVM_GETITEMCOUNT, 0, 0)
    print("[5] confirm window ok, today's items:", rows, "(expect 2)")
    shot(conf, os.path.join(CPP, "shot_confirm.bmp"))
    # 倒计时 3 秒自动启动（config 已默认 30，这里等不到；手动点击启动）
    okb = user32.GetDlgItem(conf, 5003)
    user32.PostMessageW(okb, BM_CLICK, 0, 0)
    time.sleep(1.2)
    if find_window("AutoOpenApps_ConfirmWnd"):
        print("WARN: confirm window still open after click")
    else:
        print("[6] confirm -> launch ok (window closed)")
    # 检查 notepad 是否被启动
    np = user32.FindWindowW("Notepad", None)
    print("[7] notepad launched:", bool(np))
    if np:
        subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)

    # --- 倒计时自动启动测试：config 3 秒 ---
    with open(CONFIG_TXT, "w") as f:
        f.write("confirm_seconds=3\n")
    auto2 = subprocess.Popen([EXE, "--auto"])
    conf2 = wait_window("AutoOpenApps_ConfirmWnd", 10)
    if not conf2:
        print("FAIL: confirm window 2 not shown"); sys.exit(1)
    print("[8] countdown test: window shown, waiting auto-launch...")
    gone = wait_gone("AutoOpenApps_ConfirmWnd", 12)
    print("[9] auto-launch after countdown:", gone)
    time.sleep(0.5)
    if user32.FindWindowW("Notepad", None):
        print("[10] notepad launched by countdown: True")
        subprocess.run(["taskkill", "/IM", "notepad.exe", "/F"], capture_output=True)
    else:
        print("[10] notepad launched by countdown: False (check manually)")

    # --- 清理 ---
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.5)
    cleanup_cfg()
    print("DONE - config cleaned")

if __name__ == "__main__":
    main()
