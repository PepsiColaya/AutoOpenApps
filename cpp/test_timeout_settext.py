# -*- coding: utf-8 -*-
# 验证 WM_SETTEXT 跨进程设置输入框文本后，回车保存是否读到正确值
import ctypes, os, subprocess, time
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AutoOpenApps.exe")
MAIN_CLASS = "AutoOpenApps_MainWnd"
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

def send(i): user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = wintypes.LRESULT
def press_key(vk):
    i = INPUT(); i.type = INPUT_KEYBOARD; i.u.ki.wVk = vk; send(i); i.u.ki.dwFlags = KEYEVENTF_KEYUP; send(i); time.sleep(0.05)

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
    # 用 WM_SETTEXT 直接设置文本（LPARAM = 指向 UTF-16 字符串的指针）
    for val in ["10", "999", "5", "0"]:
        txt = ctypes.create_unicode_buffer(val)
        user32.SendMessageW(ed, 0x000C, 0, ctypes.addressof(txt))  # WM_SETTEXT
        time.sleep(0.2)
        press_key(0x0D)
        time.sleep(0.6)
        cfg=os.path.join(os.environ["APPDATA"],"AutoOpenApps","config.txt")
        dbg=os.path.join(os.environ["APPDATA"],"AutoOpenApps","config.txt.dbglog")
        logtxt = open(dbg,encoding="utf-8-sig").read().strip().splitlines()[-1] if os.path.exists(dbg) else "(none)"
        print("set %-4s -> config:%s | log:%s" % (val, open(cfg,encoding="utf-8-sig").read().strip(), logtxt))
    user32.PostMessageW(m,0x0010,0,0); time.sleep(0.3)

if __name__=="__main__": main()
