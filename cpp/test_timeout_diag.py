# -*- coding: utf-8 -*-
# 诊断：主窗口「启动倒计时」输入框的焦点与输入投递
import ctypes, os, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoOpenApps.exe")
MAIN_CLASS = "AutoOpenApps_MainWnd"

KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
LEFTDOWN, LEFTUP, ABSOLUTE, MOVE = 0x0002, 0x0004, 0x8000, 0x0001


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


def send(i):
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))


def type_text(s):
    for ch in s:
        i = INPUT(); i.type = INPUT_KEYBOARD
        i.u.ki.wScan = ord(ch); i.u.ki.dwFlags = KEYEVENTF_UNICODE
        send(i)
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        send(i)
        time.sleep(0.01)


def click_pt(x, y):
    sw = user32.GetSystemMetrics(0); sh = user32.GetSystemMetrics(1)
    i = INPUT(); i.type = INPUT_MOUSE
    i.u.mi.dx = int(x * 65536 / sw); i.u.mi.dy = int(y * 65536 / sh)
    i.u.mi.dwFlags = MOVE | ABSOLUTE
    send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTDOWN
    send(i)
    i.u.mi.dwFlags = ABSOLUTE | LEFTUP
    send(i)
    time.sleep(0.3)


def main_window():
    result = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        if cls.value == MAIN_CLASS:
            result.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return result[0] if result else None


def edit_hwnd(mwnd):
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, lp):
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, cls, 256)
        if cls.value == "Edit":
            found.append(h)
        return True
    user32.EnumChildWindows(mwnd, cb, 0)
    return found[0] if found else None


def txtlen(h):
    return user32.SendMessageW(h, 0x000D, 0, 0)  # WM_GETTEXTLENGTH


def focus_is(h):
    f = user32.GetFocus()
    return f == h


def main():
    subprocess.Popen([EXE])
    mwnd = None
    for _ in range(30):
        mwnd = main_window()
        if mwnd:
            break
        time.sleep(0.3)
    assert mwnd, "main window not found"
    time.sleep(0.8)
    user32.SetWindowPos(mwnd, None, 100, 100, 1000, 700, 0x0040)
    user32.UpdateWindow(mwnd)
    time.sleep(0.5)
    user32.SetForegroundWindow(mwnd)
    time.sleep(0.5)
    ed = edit_hwnd(mwnd)
    assert ed, "edit not found"

    er = wintypes.RECT()
    user32.GetWindowRect(ed, ctypes.byref(er))
    print("edit rect:", er.left, er.top, er.right, er.bottom)
    cx, cy = (er.left + er.right) // 2, (er.top + er.bottom) // 2

    print("focus==edit before click:", focus_is(ed))
    click_pt(cx, cy)
    print("focus==edit after click:", focus_is(ed))

    # 尝试直接 SetFocus
    user32.SetFocus(ed)
    time.sleep(0.2)
    print("focus==edit after SetFocus:", focus_is(ed))

    print("textlen before:", txtlen(ed))
    type_text("10")
    time.sleep(0.3)
    print("textlen after type '10':", txtlen(ed))

    # 回车
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = 0x0D; send(i)
    i.u.ki.dwFlags = KEYEVENTF_KEYUP; send(i)
    time.sleep(0.5)
    cfg = os.path.join(os.environ["APPDATA"], "AutoOpenApps", "config.txt")
    print("config now:", open(cfg, encoding="utf-8-sig").read().strip() if os.path.exists(cfg) else "(none)")

    user32.PostMessageW(mwnd, 0x0010, 0, 0)  # WM_CLOSE
    time.sleep(0.3)


if __name__ == "__main__":
    main()
