# -*- coding: utf-8 -*-
# 多选 + 批量设置/移除开机启动 功能测试（SendInput 真实输入模拟）
# 行坐标通过 LVM_GETITEMRECT（跨进程远程内存）精确获取，不依赖魔法偏移
import ctypes, subprocess, sys, time, os
from ctypes import wintypes

EXE = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps\cpp\AutoOpenApps.exe"
APPS_TXT = os.path.join(os.environ["APPDATA"], "AutoOpenApps", "apps.txt")
STARTUP = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.SetProcessDPIAware()
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_longlong
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

BM_CLICK = 0x00F5
WM_CLOSE = 0x0010
LVM_GETITEMRECT = 0x100E
LVIR_BOUNDS = 0
PROCESS_VM = 0x0008 | 0x0010 | 0x0020  # OPERATION | READ | WRITE
MEM_COMMIT_RESERVE = 0x3000
PAGE_READWRITE = 0x04
MEM_RELEASE = 0x8000
INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
KEYEVENTF_KEYUP = 0x0002
LEFTDOWN, LEFTUP, ABSOLUTE, MOVE = 0x0002, 0x0004, 0x8000, 0x0001
VK_CONTROL = 0x11

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

PID = None  # 被测进程 PID

def send_inputs(items):
    arr = (INPUT * len(items))()
    for i, it in enumerate(items):
        arr[i] = it
    user32.SendInput(len(items), arr, ctypes.sizeof(INPUT))

def click_xy(x, y):
    sw = user32.GetSystemMetrics(0); sh = user32.GetSystemMetrics(1)
    dx = int(x * 65536 / sw); dy = int(y * 65536 / sh)
    i1 = INPUT(); i1.type = INPUT_MOUSE; i1.u.mi.dx = dx; i1.u.mi.dy = dy; i1.u.mi.dwFlags = MOVE | ABSOLUTE
    i2 = INPUT(); i2.type = INPUT_MOUSE; i2.u.mi.dx = dx; i2.u.mi.dy = dy; i2.u.mi.dwFlags = ABSOLUTE | LEFTDOWN
    i3 = INPUT(); i3.type = INPUT_MOUSE; i3.u.mi.dx = dx; i3.u.mi.dy = dy; i3.u.mi.dwFlags = ABSOLUTE | LEFTUP
    send_inputs([i1, i2, i3])
    time.sleep(0.25)

def ctrl_click_xy(x, y):
    sw = user32.GetSystemMetrics(0); sh = user32.GetSystemMetrics(1)
    dx = int(x * 65536 / sw); dy = int(y * 65536 / sh)
    k = INPUT(); k.type = INPUT_KEYBOARD; k.u.ki.wVk = VK_CONTROL
    m1 = INPUT(); m1.type = INPUT_MOUSE; m1.u.mi.dx = dx; m1.u.mi.dy = dy; m1.u.mi.dwFlags = MOVE | ABSOLUTE
    m2 = INPUT(); m2.type = INPUT_MOUSE; m2.u.mi.dx = dx; m2.u.mi.dy = dy; m2.u.mi.dwFlags = ABSOLUTE | LEFTDOWN
    m3 = INPUT(); m3.type = INPUT_MOUSE; m3.u.mi.dx = dx; m3.u.mi.dy = dy; m3.u.mi.dwFlags = ABSOLUTE | LEFTUP
    k2 = INPUT(); k2.type = INPUT_KEYBOARD; k2.u.ki.wVk = VK_CONTROL; k2.u.ki.dwFlags = KEYEVENTF_KEYUP
    send_inputs([k, m1, m2, m3, k2])
    time.sleep(0.25)

def get_text(h):
    n = user32.SendMessageW(h, 0x000E, 0, 0)  # WM_GETTEXTLENGTH
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.SendMessageW(h, 0x000D, n + 1, ctypes.addressof(buf))  # WM_GETTEXT
    return buf.value

def wait_window(cls, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = user32.FindWindowW(cls, None)
        if h and user32.IsWindowVisible(h):
            return h
        time.sleep(0.2)
    return None

def apps_lines():
    return open(APPS_TXT, encoding="utf-8-sig").read().strip().splitlines()

def enabled_flags():
    return [ln.split("\t")[3] for ln in apps_lines()]

def reset_all_enabled():
    """测试前把 apps.txt 全部重置为启用，保证初始状态确定。"""
    lines = apps_lines()
    out = []
    for ln in lines:
        parts = ln.split("\t")
        if len(parts) >= 4:
            parts[3] = "1"
            out.append("\t".join(parts))
    with open(APPS_TXT, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(out) + "\n")

def row_rect_screen(lv, i):
    """LVM_GETITEMRECT 取第 i 行边界（列表客户区坐标），转屏幕坐标。"""
    hproc = kernel32.OpenProcess(PROCESS_VM, False, PID)
    if not hproc:
        raise OSError("OpenProcess failed: %d" % kernel32.GetLastError())
    remote = None
    try:
        remote = kernel32.VirtualAllocEx(hproc, None, 16, MEM_COMMIT_RESERVE, PAGE_READWRITE)
        if not remote:
            raise OSError("VirtualAllocEx failed: %d" % kernel32.GetLastError())
        rect_in = (wintypes.LONG * 4)(LVIR_BOUNDS, 0, 0, 0)  # left=LVIR_BOUNDS
        written = ctypes.c_size_t(0)
        kernel32.WriteProcessMemory(hproc, remote, ctypes.byref(rect_in), 16, ctypes.byref(written))
        user32.SendMessageW(lv, LVM_GETITEMRECT, i, remote)
        out = (wintypes.LONG * 4)()
        read = ctypes.c_size_t(0)
        kernel32.ReadProcessMemory(hproc, remote, ctypes.byref(out), 16, ctypes.byref(read))
        pt = wintypes.POINT(out[0], out[1])
        user32.ClientToScreen(lv, ctypes.byref(pt))
        return pt.x, pt.y, pt.x + (out[2] - out[0]), pt.y + (out[3] - out[1])
    finally:
        if remote:
            kernel32.VirtualFreeEx(hproc, remote, 0, MEM_RELEASE)
        kernel32.CloseHandle(hproc)

def row_xy(lv, i):
    l, t, r, b = row_rect_screen(lv, i)
    return (l + r) // 2, (t + b) // 2

def main():
    global PID
    reset_all_enabled()
    proc = subprocess.Popen([EXE])
    PID = proc.pid
    hwnd = wait_window("AutoOpenApps_MainWnd")
    if not hwnd:
        print("FAIL: no main window"); sys.exit(1)
    time.sleep(0.8)
    lv = user32.GetDlgItem(hwnd, 2001)
    btn = user32.GetDlgItem(hwnd, 2007)
    run_btn = user32.GetDlgItem(hwnd, 2006)
    lnk = os.path.join(STARTUP, "AutoOpenApps.lnk")
    print("[0] initial flags:", enabled_flags())
    # 打印行几何，便于诊断
    for i in range(3):
        print("    row", i, "rect:", row_rect_screen(lv, i))
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    # 1. 单击第 1 行 + Ctrl+单击第 2 行 → 多选（两项均启用）
    click_xy(*row_xy(lv, 0))
    ctrl_click_xy(*row_xy(lv, 1))
    t = get_text(btn)
    run_ok = user32.IsWindowEnabled(run_btn)
    print("[1] multi-select 1,2 -> button:", t, "| run enabled:", bool(run_ok))
    assert t == "移除开机启动", "FAIL[1] button: " + t
    assert run_ok, "FAIL[1] run button disabled"

    # 2. 点击“移除开机启动”→ 两项停用
    user32.PostMessageW(btn, BM_CLICK, 0, 0)
    time.sleep(0.5)
    flags = enabled_flags()
    t = get_text(btn)
    print("[2] flags:", flags, "button:", t)
    assert flags[0] == "0" and flags[1] == "0", "FAIL[2] not disabled"
    assert t == "设为开机启动", "FAIL[2] button: " + t
    print("[2] OK - batch remove works, button switched")

    # 3. 改选第 3 行（启用中）→ 按钮“移除开机启动”
    click_xy(*row_xy(lv, 2))
    t = get_text(btn)
    print("[3] select 3 (enabled) -> button:", t)
    assert t == "移除开机启动", "FAIL[3] button: " + t

    # 4. Ctrl+加选第 2 行（已停用）→ 混合 → “设为开机启动”
    ctrl_click_xy(*row_xy(lv, 1))
    t = get_text(btn)
    print("[4] mixed 2(disabled)+3(enabled) -> button:", t)
    assert t == "设为开机启动", "FAIL[4] button: " + t

    # 5. 点击 → 选中两项（第2、3行）恢复启用，未选中的第1行保持停用
    user32.PostMessageW(btn, BM_CLICK, 0, 0)
    time.sleep(0.5)
    flags = enabled_flags()
    t = get_text(btn)
    print("[5] flags:", flags, "button:", t)
    assert flags == ["0", "1", "1", "1", "1"], "FAIL[5] flags: " + str(flags)
    assert t == "移除开机启动", "FAIL[5] button: " + t
    print("[5] OK - batch set works (only selected rows toggled)")

    # 6. Ctrl+加选第1行（停用）→ 混合 → 点击全部设为启用 → 快捷方式存在
    ctrl_click_xy(*row_xy(lv, 0))
    t = get_text(btn)
    assert t == "设为开机启动", "FAIL[6] button: " + t
    user32.PostMessageW(btn, BM_CLICK, 0, 0)
    time.sleep(0.5)
    flags = enabled_flags()
    print("[6] flags:", flags, "lnk exists:", os.path.exists(lnk))
    assert all(f == "1" for f in flags), "FAIL[6] flags: " + str(flags)
    assert os.path.exists(lnk), "FAIL[6] lnk missing"

    # 7. 全部停用 → 快捷方式自动移除
    click_xy(*row_xy(lv, 0))
    for i in range(1, 5):
        ctrl_click_xy(*row_xy(lv, i))
    t = get_text(btn)
    print("[7] all selected, button:", t)
    user32.PostMessageW(btn, BM_CLICK, 0, 0)
    time.sleep(0.5)
    flags = enabled_flags()
    print("[7] all disabled, flags:", flags, "lnk removed:", not os.path.exists(lnk))
    assert all(f == "0" for f in flags), "FAIL[7] flags: " + str(flags)
    assert not os.path.exists(lnk), "FAIL[7] lnk should be removed"

    # 8. 全部恢复启用 → 快捷方式重建
    click_xy(*row_xy(lv, 0))
    for i in range(1, 5):
        ctrl_click_xy(*row_xy(lv, i))
    user32.PostMessageW(btn, BM_CLICK, 0, 0)
    time.sleep(0.5)
    flags = enabled_flags()
    print("[8] restored flags:", flags, "lnk exists:", os.path.exists(lnk))
    assert all(f == "1" for f in flags), "FAIL[8] restore failed"
    assert os.path.exists(lnk), "FAIL[8] lnk not recreated"

    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(0.4)
    proc.terminate()
    print("ALL PASS")

if __name__ == "__main__":
    main()
