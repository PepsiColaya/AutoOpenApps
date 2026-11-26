# -*- coding: utf-8 -*-
# 用 SendInput 模拟真实键盘/鼠标操作编辑对话框
import ctypes, subprocess, sys, time, os
from ctypes import wintypes

EXE = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp\AutoOpenApps.exe"
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
BM_CLICK = 0x00F5
WM_CLOSE = 0x0010

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

KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
LEFTDOWN, LEFTUP, ABSOLUTE, MOVE = 0x0002, 0x0004, 0x8000, 0x0001

def send(i):
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))

def type_text(s):
    for ch in s:
        i = INPUT(); i.type = INPUT_KEYBOARD
        i.u.ki.wScan = ord(ch); i.u.ki.dwFlags = KEYEVENTF_UNICODE
        send(i)
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        send(i)
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
    send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTDOWN
    send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTUP
    send(i)
    time.sleep(0.15)

def get_text(h):
    n = user32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(h, buf, n + 2)
    return buf.value

def wait_window(cls, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = user32.FindWindowW(cls, None)
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(0.2)
    return None

def child_by_text(parent, text):
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        if text in get_text(h):
            res.append(h)
        return True
    user32.EnumChildWindows(parent, cb, 0)
    return res

def main():
    proc = subprocess.Popen([EXE])
    hwnd = wait_window("AutoOpenApps_MainWnd")
    if not hwnd:
        print("FAIL: no main window"); sys.exit(1)
    time.sleep(0.6)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    btn = child_by_text(hwnd, "添加软件")[0]
    click_hwnd(btn)          # 真实鼠标点击
    ed = wait_window("AutoOpenApps_EditDlg", 8)
    if not ed:
        print("FAIL: no edit dialog"); sys.exit(1)
    time.sleep(0.3)
    user32.SetForegroundWindow(ed)
    time.sleep(0.3)

    name_e = user32.GetDlgItem(ed, 3001)
    path_e = user32.GetDlgItem(ed, 3002)
    click_hwnd(name_e)
    type_text("测试-记事本")
    time.sleep(0.2)
    click_hwnd(path_e)
    type_text(r"C:\Windows\System32\notepad.exe")
    time.sleep(0.3)
    print("name in edit:", repr(get_text(name_e)))
    print("path in edit:", repr(get_text(path_e)))

    ok_btn = user32.GetDlgItem(ed, 3017)
    click_hwnd(ok_btn)       # 真实鼠标点击“确定”
    time.sleep(1.0)

    apps = os.path.join(os.environ["APPDATA"], "AutoOpenApps", "apps.txt")
    ok = os.path.exists(apps)
    print("apps.txt exists:", ok)
    if ok:
        print("content:", open(apps, encoding="utf-8-sig").read().strip())
    else:
        # 是否被校验 MessageBox 卡住
        print("dialog still open:", user32.IsWindowVisible(ed))
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.4)
    proc.terminate()
    print("DONE", "PASS" if ok else "FAIL")

if __name__ == "__main__":
    main()
