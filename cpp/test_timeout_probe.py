# -*- coding: utf-8 -*-
# 探针：测试不同清空方式后，保存函数实际读到的文本
import ctypes, os, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoOpenApps.exe")
MAIN_CLASS = "AutoOpenApps_MainWnd"
KEYEVENTF_UNICODE = 0x0004; KEYEVENTF_KEYUP = 0x0002; KEYEVENTF_CONTROL = 0x0020
INPUT_KEYBOARD = 1

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

def send(i): user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
def type_text(s):
    for ch in s:
        i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wScan = ord(ch); i.u.ki.dwFlags = KEYEVENTF_UNICODE; send(i)
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP; send(i); time.sleep(0.01)
def key(vk, flags=0):
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = vk; i.u.ki.dwFlags = flags; send(i)
    i.u.ki.dwFlags = flags | KEYEVENTF_KEYUP; send(i); time.sleep(0.03)
def ctrl_a():
    key(0x41, KEYEVENTF_CONTROL)
def backspace():
    key(0x2E)

def main_window():
    r=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h,lp):
        c=ctypes.create_unicode_buffer(256); user32.GetClassNameW(h,c,256)
        if c.value==MAIN_CLASS: r.append(h)
        return True
    user32.EnumWindows(cb,0); return r[0] if r else None
def edit_hwnd(m):
    f=[]
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h,lp):
        c=ctypes.create_unicode_buffer(256); user32.GetClassNameW(h,c,256)
        if c.value=="Edit": f.append(h)
        return True
    user32.EnumChildWindows(m,cb,0); return f[0] if f else None

def dbglog():
    p=os.path.join(os.environ["APPDATA"],"AutoOpenApps","config.txt.dbglog")
    return open(p,encoding="utf-8-sig").read().strip() if os.path.exists(p) else "(none)"

def run_case(label, clear_fn):
    subprocess.Popen([EXE])
    m=None
    for _ in range(30):
        m=main_window()
        if m: break
        time.sleep(0.3)
    time.sleep(0.8)
    user32.SetWindowPos(m,None,100,100,1000,700,0x0040); user32.UpdateWindow(m); time.sleep(0.5)
    user32.SetForegroundWindow(m); time.sleep(0.5)
    ed=edit_hwnd(m)
    # 点击输入框聚焦
    _click(ed)
    clear_fn()
    type_text("10")
    time.sleep(0.2)
    key(0x0D)  # Enter
    time.sleep(0.6)
    cfg=os.path.join(os.environ["APPDATA"],"AutoOpenApps","config.txt")
    print("[%s] config=%s | dbglog=%s" % (label, open(cfg,encoding="utf-8-sig").read().strip(), dbglog()))
    user32.PostMessageW(m,0x0010,0,0); time.sleep(0.3)
    # 等进程退出
    try: subprocess.Popen([EXE]).wait(2)
    except Exception: pass

def _click(ed):
    KEYEVENTF_MOUSE = 0
    from ctypes import wintypes as w
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", w.LONG),("dy", w.LONG),("mouseData", w.DWORD),("dwFlags", w.DWORD),("time", w.DWORD),("dwExtraInfo", ctypes.POINTER(w.ULONG))]
    class MU(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    class MIN(ctypes.Structure):
        _fields_ = [("type", w.DWORD),("u", MU)]
    er=w.RECT(); user32.GetWindowRect(ed,ctypes.byref(er))
    cx,cy=(er.left+er.right)//2,(er.top+er.bottom)//2
    sw=user32.GetSystemMetrics(0); sh=user32.GetSystemMetrics(1)
    for flags,extra in [(0x8001,0),(0x8002,0),(0x8004,0)]:
        i=MIN(); i.type=0; i.u.mi.dx=int(cx*65536/sw); i.u.mi.dy=int(cy*65536/sh); i.u.mi.dwFlags=flags; send(i)
        time.sleep(0.05)
    time.sleep(0.2)

if __name__=="__main__":
    print("=== case A: Ctrl+A + Backspace ===")
    run_case("A", lambda: (ctrl_a(), time.sleep(0.1), backspace(), time.sleep(0.1)))
    print("=== case B: 10x Backspace ===")
    run_case("B", lambda: [backspace() for _ in range(10)])
