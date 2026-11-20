#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate README screenshots with FICTIONAL data only (no real user info).

Uses PySide6 offscreen rendering so no real desktop / window is captured.
All software names and paths below are invented placeholders.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Point config at a throwaway temp dir so the real config is never read.
_TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shot_tmp")
os.makedirs(_TMP, exist_ok=True)
os.environ["APPDATA"] = _TMP

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

import qt_app

FAKE_APPS = [
    {"name": "示例浏览器", "path": r"C:\Program Files\Example\Browser.exe",
     "delay": 0, "args": "", "enabled": True, "days": [0, 1, 2, 3, 4, 5, 6]},
    {"name": "示例邮件客户端", "path": r"C:\Program Files\Example\Mail.exe",
     "delay": 2, "args": "", "enabled": True, "days": [0, 1, 2, 3, 4]},
    {"name": "示例代码编辑器", "path": r"C:\Program Files\Example\Editor.exe",
     "delay": 0, "args": "--new-window", "enabled": True, "days": [0, 1, 2, 3, 4]},
    {"name": "示例音乐播放器", "path": r"C:\Program Files\Example\Music.exe",
     "delay": 0, "args": "", "enabled": True, "days": [5, 6]},
]


def shot(widget, path, w, h):
    widget.resize(w, h)
    widget.show()
    app.processEvents()
    app.processEvents()
    pm = widget.grab()
    pm.save(path)
    widget.hide()
    print("saved", path, pm.width(), "x", pm.height())


app = QApplication(sys.argv)
# Offscreen Qt has no system font DB; load the CJK font file explicitly.
_fid = QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\msyh.ttc")
_fams = QFontDatabase.applicationFontFamilies(_fid)
_cjk = _fams[0] if _fams else "Microsoft YaHei"
app.setFont(QFont(_cjk, 9))
print("font:", _fams)

icon = qt_app.app_icon_path()
if icon:
    app.setWindowIcon(QIcon(icon))

# 1) Manager window with fictional list
win = qt_app.MainWindow()
win.cfg = {"apps": [dict(a) for a in FAKE_APPS]}
win.render()
win.msg("清单就绪：共 4 项（演示数据）。")
shot(win, os.path.join(os.path.dirname(__file__), "docs", "manager.png"), 900, 520)

# 2) Confirm dialog with fictional list
confirm = qt_app.ConfirmDialog([dict(a) for a in FAKE_APPS if 0 in a["days"]])
shot(confirm, os.path.join(os.path.dirname(__file__), "docs", "confirm.png"), 620, 400)

print("DONE")
