# -*- coding: utf-8 -*-
# 逐步诊断：清空与输入每一步的实际文本
import ctypes, os, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoOpenApps.exe")
MAIN_CLASS = "AutoOpenApps_MainWnd"
KEYEVENTF_UNICODE = 0x0004; KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD, INPUT_MOUSE = 1, 0
LEFTDOWN, LEFTUP, ABSOLUTE, MOVE = 0x0002, 0x0004, 0x8000, 0x0001

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

def send(i): user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
def type_text(s):
    for ch in s:
        i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wScan = ord(ch); i.u.ki.dwFlags = KEYEVENTF_UNICODE; send(i)
        i.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP; send(i); time.sleep(0.01)
def press_key(vk):
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = vk; send(i); i.u.ki.dwFlags = KEYEVENTF_KEYUP; send(i); time.sleep(0.05)
def click_pt(x, y):
    sw = user32.GetSystemMetrics(0); sh = user32.GetSystemMetrics(1)
    i = INPUT(); i.type = INPUT_MOUSE; i.u.mi.dx = int(x*65536/sw); i.u.mi.dy = int(y*65536/sh); i.u.mi.dwFlags = MOVE|ABSOLUTE; send(i)
    i.u.mi.dwFlags = ABSOLUTE|LEFTDOWN; send(i); i.u.mi.dwFlags = ABSOLUTE|LEFTUP; send(i); time.sleep(0.3)
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
def read_text(h):
    n = user32.SendMessageW(h, 0x000D, 0, 0)  # WM_GETTEXTLENGTH
    if n<=0: return ""
    buf = ctypes.create_unicode_buffer(n+2)
    user32.SendMessageW(h, 0x000D, 0, 0)
    user32.SendMessageW(h, 0x000D, 0, 0)
    # WM_GETTEXT
    user32.SendMessageW(h, 0x000D, 0, 0)
    return "len=%d" % n

def main():
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
    er=wintypes.RECT(); user32.GetWindowRect(ed,ctypes.byref(er))
    cx,cy=(er.left+er.right)//2,(er.top+er.bottom)//2
    print("edit rect", er.left,er.top,er.right,er.bottom, "center",cx,cy)

    def show(tag):
        n = user32.SendMessageW(ed, 0x000D, 0, 0)
        buf = ctypes.create_unicode_buffer(n+2)
        user32.SendMessageW(ed, 0x000D, 0, 0)
        # proper WM_GETTEXT
        n2 = user32.SendMessageW(ed, 0x000D, 0, 0)
        buf = ctypes.create_unicode_buffer(n2+2)
        user32.SendMessageW(ed, 0x000D, 0, 0)
        print(tag, "len=", n)

    click_pt(cx,cy); time.sleep(0.2)
    print("after click, len=", user32.SendMessageW(ed,0x000D,0,0))
    # triple click
    for _ in range(3):
        click_pt(cx,cy); time.sleep(0.05)
    print("after triple click, len=", user32.SendMessageW(ed,0x000D,0,0))
    type_text("10"); time.sleep(0.2)
    print("after type 10, len=", user32.SendMessageW(ed,0x000D,0,0))
    press_key(0x0D); time.sleep(0.5)
    cfg=os.path.join(os.environ["APPDATA"],"AutoOpenApps","config.txt")
    print("config:", open(cfg,encoding="utf-8-sig").read().strip())
    user32.PostMessageW(m,0x0010,0,0); time.sleep(0.3)

if __name__=="__main__": main()
