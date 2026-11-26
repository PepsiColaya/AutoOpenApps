# 测试主窗口「启动倒计时」输入框：窗口内修改并保存
# -*- coding: utf-8 -*-
import ctypes, os, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoOpenApps.exe")
CFG = os.path.join(os.environ["APPDATA"], "AutoOpenApps", "config.txt")
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


def press_key(vk):
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = vk; send(i)
    i.u.ki.dwFlags = KEYEVENTF_KEYUP; send(i)
    time.sleep(0.05)


def ctrl_a():
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = 0x41
    i.u.ki.dwFlags = 0x0020; send(i)
    i.u.ki.dwFlags = 0x0020 | KEYEVENTF_KEYUP; send(i)
    time.sleep(0.05)


def delete_all():
    # 鼠标三击全选（Edit 控件标准全选，跨进程比 Ctrl+A 可靠）
    for _ in range(3):
        click_pt(*LAST_CLICK)
        time.sleep(0.05)


LAST_CLICK = (0, 0)


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
    time.sleep(0.2)


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


def cfg_value():
    try:
        for ln in open(CFG, encoding="utf-8-sig").read().splitlines():
            if ln.startswith("confirm_seconds="):
                return int(ln.split("=")[1])
    except OSError:
        pass
    return None


ed = None


def set_timeout(v):
    """点击输入框 -> 三击全选 -> 输入(替换) -> 回车保存"""
    er = wintypes.RECT()
    user32.GetWindowRect(ed, ctypes.byref(er))
    cx, cy = (er.left + er.right) // 2, (er.top + er.bottom) // 2
    global LAST_CLICK
    LAST_CLICK = (cx, cy)
    click_pt(cx, cy)
    time.sleep(0.2)
    delete_all()
    type_text(str(v))
    time.sleep(0.2)
    press_key(0x0D)
    time.sleep(0.8)


def main():
    global ed
    subprocess.Popen([EXE])
    mwnd = None
    for _ in range(30):
        mwnd = main_window()
        if mwnd:
            break
        time.sleep(0.3)
    assert mwnd, "main window not found"
    time.sleep(0.8)
    # 固定窗口位置与尺寸，保证输入框坐标确定
    user32.SetWindowPos(mwnd, None, 100, 100, 1000, 700, 0x0040)  # SWP_NOZORDER|SWP_NOACTIVATE
    user32.UpdateWindow(mwnd)
    time.sleep(0.5)
    user32.SetForegroundWindow(mwnd)
    time.sleep(0.3)
    ed = edit_hwnd(mwnd)
    assert ed, "timeout edit not found"
    print("[0] config before:", cfg_value())

    set_timeout(10)
    print("[1] typed 10 -> config:", cfg_value())
    assert cfg_value() == 10, "FAIL[1] config not saved"

    set_timeout(999)  # 超上限，应回退为 10
    print("[2] typed 999 -> config:", cfg_value())
    assert cfg_value() == 10, "FAIL[2] should revert on out-of-range"

    set_timeout(5)
    print("[3] restored 5 -> config:", cfg_value())
    assert cfg_value() == 5, "FAIL[3] restore failed"

    set_timeout(0)  # 0 = 手动确认，合法
    print("[4] typed 0 -> config:", cfg_value())
    assert cfg_value() == 0, "FAIL[4] zero should be valid"

    set_timeout(5)
    assert cfg_value() == 5, "FAIL restore"
    print("ALL PASS")


if __name__ == "__main__":
    main()
