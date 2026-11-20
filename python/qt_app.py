#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AutoOpenApps - 软件启动助手（本地原生窗口版，PySide6/Qt）

用法：
  AutoOpenApps.exe            管理界面：维护软件清单、一键启动、开机自启开关
  AutoOpenApps.exe --auto     开机模式：弹出确认窗口，勾选要打开的软件后确认启动

配置： %APPDATA%/AutoOpenApps/config.json
开机自启： 启动文件夹/AutoOpenApps.bat  ->  start "" "本exe" --auto
"""
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime

try:
    import winreg
except ImportError:
    winreg = None

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

APP_NAME = "AutoOpenApps"
DEFAULT_CONFIRM_SECONDS = 5   # 开机确认窗倒计时；0 表示不自动确认，需手动点
CONFIRM_TEXT = ("开机软件清单待确认：勾选要打开的软件后点“确认启动”；"
                "不需要的取消勾选即可；点“取消”则本次不打开任何软件。")

WEEKDAY_NAMES = ["一", "二", "三", "四", "五", "六", "日"]


def normalize_days(days):
    """归一化生效星期为 0-6（周一=0）列表；为空则视为每天。"""
    try:
        ds = [int(x) for x in (days or [])]
    except Exception:
        ds = []
    ds = sorted({d for d in ds if 0 <= d <= 6})
    return ds if ds else [0, 1, 2, 3, 4, 5, 6]


def days_label(days):
    ds = normalize_days(days)
    if len(ds) == 7:
        return "每天"
    return "、".join("周" + WEEKDAY_NAMES[d] for d in ds)


def is_scheduled_today(app):
    return datetime.now().weekday() in normalize_days(app.get("days"))


def app_icon_path():
    """定位随包分发的图标文件（打包后在 _internal，源码运行时在同目录）。"""
    if getattr(sys, "frozen", False):
        p = os.path.join(getattr(sys, "_MEIPASS", ""), "icon.ico")
    else:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    return p if os.path.exists(p) else ""


# ---------------- config ----------------

def config_file():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        APP_NAME, "config.json")


def load_config():
    try:
        with open(config_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("apps"), list):
            apps = []
            for a in data["apps"]:
                if not isinstance(a, dict) or not a.get("path"):
                    continue
                try:
                    delay = max(0, min(300, int(a.get("delay") or 0)))
                except Exception:
                    delay = 0
                apps.append({
                    "name": str(a.get("name") or os.path.basename(str(a.get("path")))),
                    "path": str(a.get("path")),
                    "delay": delay,
                    "args": str(a.get("args") or ""),
                    "enabled": bool(a.get("enabled", True)),
                    "days": normalize_days(a.get("days")),
                })
            try:
                sec = max(0, min(120, int(data.get("confirm_seconds", DEFAULT_CONFIRM_SECONDS))))
            except Exception:
                sec = DEFAULT_CONFIRM_SECONDS
            return {"apps": apps, "confirm_seconds": sec}
    except Exception:
        pass
    return {"apps": [], "confirm_seconds": DEFAULT_CONFIRM_SECONDS}


def save_config(cfg):
    os.makedirs(os.path.dirname(config_file()), exist_ok=True)
    with open(config_file(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------- error log ----------------

def log_error(tag, exc):
    try:
        os.makedirs(os.path.dirname(config_file()), exist_ok=True)
        with open(os.path.join(os.path.dirname(config_file()), "error.log"),
                  "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(tag) + ": "
                    + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                    + "\n")
    except Exception:
        pass


def log_exc(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            log_error(fn.__name__, e)
            return None
    wrapper.__name__ = fn.__name__
    return wrapper


def _sys_excepthook(t, v, tb):
    log_error("uncaught", v)


sys.excepthook = _sys_excepthook


# ---------------- installed-apps index ----------------

def index_file():
    return os.path.join(os.path.dirname(config_file()), "app_index.json")


def load_index():
    try:
        with open(index_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("apps"), list):
            return data
    except Exception:
        pass
    return {"built_at": 0, "apps": []}


def save_index(data):
    os.makedirs(os.path.dirname(index_file()), exist_ok=True)
    with open(index_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_BAD_EXE_HINTS = ("uninst", "unins", "setup", "update", "crash", "report", "helper",
                  "eula", "redist", "vc_redist", "dotnet", "install", "patch")


def scan_installed_apps():
    """扫描注册表卸载项等位置，生成本机已安装软件索引。"""
    results = {}

    def add(path, name):
        if not path or not path.lower().endswith(".exe"):
            return
        path = os.path.normpath(path)
        if not os.path.exists(path):
            return
        low = os.path.basename(path).lower()
        if any(h in low for h in _BAD_EXE_HINTS):
            return
        results.setdefault(path, name or os.path.basename(path)[:-4])

    if winreg is not None:
        roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                 (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
        for root, sub in roots:
            try:
                k = winreg.OpenKey(root, sub)
            except OSError:
                continue
            i = 0
            while True:
                try:
                    keyname = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    sk = winreg.OpenKey(k, keyname)
                    try:
                        name = str(winreg.QueryValueEx(sk, "DisplayName")[0]).strip()
                    except OSError:
                        continue
                    if not name:
                        continue
                    exe = ""
                    try:
                        icon = str(winreg.QueryValueEx(sk, "DisplayIcon")[0]).strip()
                        icon = icon.split(",")[0].strip().strip('"')
                        if icon.lower().endswith(".exe"):
                            exe = icon
                    except OSError:
                        pass
                    if not exe:
                        try:
                            loc = str(winreg.QueryValueEx(sk, "InstallLocation")[0]).strip().strip('"')
                            if loc and os.path.isdir(loc):
                                cands = [f for f in os.listdir(loc)
                                         if f.lower().endswith(".exe")
                                         and not any(h in f.lower() for h in _BAD_EXE_HINTS)]
                                if len(cands) == 1:
                                    exe = os.path.join(loc, cands[0])
                        except OSError:
                            pass
                    add(exe, name)
                except OSError:
                    continue

    return [{"name": n, "path": p}
            for p, n in sorted(results.items(), key=lambda kv: kv[1].lower())]


def refresh_index():
    apps = scan_installed_apps()
    data = {"built_at": time.time(), "apps": apps}
    save_index(data)
    return data


# ---------------- autostart (startup folder bat) ----------------

def startup_dir():
    base = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(base, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def bat_path():
    return os.path.join(startup_dir(), "AutoOpenApps.bat")


def autostart_installed():
    try:
        with open(bat_path(), "r", encoding="utf-8", errors="ignore") as f:
            return "--auto" in f.read()
    except Exception:
        return False


def set_autostart(enable):
    if enable:
        if not getattr(sys, "frozen", False):
            return {"ok": False, "message": "开发模式下不支持开机自启：请先打包成 exe 再开启。"}
        content = ('@echo off\r\n'
                   'rem AutoOpenApps boot launcher\r\n'
                   'start "" "{0}" --auto\r\n').format(sys.executable)
        try:
            os.makedirs(startup_dir(), exist_ok=True)
            with open(bat_path(), "w", encoding="ascii", errors="ignore") as f:
                f.write(content)
            return {"ok": True, "message": "已开启开机自启：开机登录后弹出确认窗口，勾选后再打开。"}
        except Exception as e:
            return {"ok": False, "message": "写入启动文件夹失败：%s" % e}
    try:
        if os.path.exists(bat_path()):
            os.remove(bat_path())
        return {"ok": True, "message": "已关闭开机自启（启动脚本已删除）。"}
    except Exception as e:
        return {"ok": False, "message": "删除启动脚本失败：%s" % e}


# ---------------- launching ----------------

def is_running(exe_path):
    name = os.path.basename(exe_path)
    if not name:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq {0}".format(name)],
                             capture_output=True, text=True, timeout=10).stdout or ""
        return name.lower() in out.lower()
    except Exception:
        return False


def launch_apps(items):
    launched, skipped, failed = [], [], []
    for it in items:
        name = it.get("name") or os.path.basename(it.get("path", ""))
        delay = it.get("delay") or 0
        if delay > 0:
            time.sleep(min(int(delay), 300))
        p = (it.get("path") or "").strip()
        if not p or not os.path.exists(p):
            failed.append([name, "路径不存在"])
            continue
        if is_running(p):
            skipped.append(name)
            continue
        args = (it.get("args") or "").strip()
        try:
            cmd = [p] + (args.split() if args else [])
            # 关键：禁止为子进程新建控制台窗口（否则每个启动项弹一个黑窗）
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            si = None
            if os.name == "nt":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 0  # SW_HIDE
            subprocess.Popen(cmd, close_fds=True, creationflags=flags, startupinfo=si)
            launched.append(name)
        except Exception as e:
            failed.append([name, str(e)])
        time.sleep(0.4)
    return {"launched": launched, "skipped": skipped, "failed": failed}


def summary_text(res):
    lines = ["已启动 %d 个" % len(res["launched"])]
    if res["skipped"]:
        lines.append("跳过已运行：%s" % "、".join(res["skipped"]))
    if res["failed"]:
        lines.append("失败：" + "；".join("%s（%s）" % (f[0], f[1]) for f in res["failed"]))
    if res["launched"]:
        lines.append("已打开：" + "、".join(res["launched"]))
    return "\n".join(lines)


# ---------------- dialogs ----------------

class EditDialog(QDialog):
    def __init__(self, parent, item=None):
        super().__init__(parent)
        self.setWindowTitle("编辑软件" if item else "添加软件")
        self.item = dict(item) if item else {"name": "", "path": "", "delay": 0, "args": "",
                                             "enabled": True, "days": list(range(7))}
        form = QFormLayout(self)
        self.setMinimumWidth(520)
        self.edName = QLineEdit(self.item["name"])
        self.edPath = QLineEdit(self.item["path"])
        self.edPath.setPlaceholderText(r"C:\Program Files\Example\App.exe")
        btnBrowse = QPushButton("浏览…")
        btnBrowse.clicked.connect(self.browse)
        h = QHBoxLayout()
        h.addWidget(self.edPath, 1)
        h.addWidget(btnBrowse)
        self.edDelay = QLineEdit(str(self.item.get("delay", 0)))
        self.edArgs = QLineEdit(self.item.get("args", ""))
        self.edArgs.setPlaceholderText("可留空，如：--new-window")
        self.dayBoxes = []
        hd = QHBoxLayout()
        for i, nm in enumerate(WEEKDAY_NAMES):
            cb = QCheckBox(nm)
            cb.setChecked(i in normalize_days(self.item.get("days")))
            self.dayBoxes.append(cb)
            hd.addWidget(cb)
        form.addRow("名称", self.edName)
        form.addRow("程序路径", h)
        form.addRow("延迟(秒)", self.edDelay)
        form.addRow("启动参数", self.edArgs)
        form.addRow("生效星期", hd)
        ok = QPushButton("保存")
        cancel = QPushButton("取消")
        ok.clicked.connect(self.accept_check)
        cancel.clicked.connect(self.reject)
        hb = QHBoxLayout()
        hb.addStretch(1)
        hb.addWidget(ok)
        hb.addWidget(cancel)
        form.addRow(hb)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择要启动的程序", "",
                                              "程序 (*.exe *.lnk *.bat);;所有文件 (*.*)")
        if path:
            self.edPath.setText(path)

    def accept_check(self):
        p = self.edPath.text().strip()
        if not p:
            QMessageBox.warning(self, "提示", "请填写程序路径。")
            return
        try:
            delay = max(0, min(300, int(self.edDelay.text() or 0)))
        except Exception:
            delay = 0
        days = [i for i, cb in enumerate(self.dayBoxes) if cb.isChecked()]
        self.item.update(name=self.edName.text().strip() or os.path.basename(p),
                         path=p, delay=delay, args=self.edArgs.text().strip(),
                         days=normalize_days(days))
        self.accept()


class ConfirmDialog(QDialog):
    """开机确认窗口：列出清单，可勾选；倒计时结束自动启动勾选项。"""

    def __init__(self, apps, seconds=DEFAULT_CONFIRM_SECONDS):
        super().__init__()
        self.setWindowTitle("开机启动确认")
        self.resize(560, 390)
        self.apps = apps
        self.selected = []
        self.seconds = int(seconds) if seconds and seconds > 0 else 0
        self._left = self.seconds
        v = QVBoxLayout(self)
        tip = QLabel(CONFIRM_TEXT)
        tip.setWordWrap(True)
        v.addWidget(tip)
        today = QLabel("今天是周%s，仅显示今天计划打开的软件。"
                       % WEEKDAY_NAMES[datetime.now().weekday()])
        today.setWordWrap(True)
        v.addWidget(today)
        self.checks = []
        if apps:
            for a in apps:
                cb = QCheckBox("%s   —   %s" % (a["name"], a["path"]), self)
                cb.setChecked(True)
                self.checks.append((cb, a))
                v.addWidget(cb)
        else:
            empty = QLabel("清单为空：没有待启动的软件。\n请先打开管理界面（直接双击 AutoOpenApps.exe）添加。")
            v.addWidget(empty)
        v.addStretch(1)

        # 倒计时提示 + 按钮
        self.lblCountdown = QLabel("")
        self.lblCountdown.setWordWrap(True)
        v.addWidget(self.lblCountdown)
        h = QHBoxLayout()
        self.ok = QPushButton("确认启动")
        no = QPushButton("取消")
        self.ok.clicked.connect(lambda: self.do_confirm(auto=False))
        no.clicked.connect(self.reject)
        h.addStretch(1)
        h.addWidget(self.ok)
        h.addWidget(no)
        v.addLayout(h)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.on_tick)
        if self.seconds > 0 and self.checks:
            self._left = self.seconds
            self._update_countdown()
            self.timer.start()
        else:
            self.lblCountdown.setText("请手动勾选后点“确认启动”。")

    def _update_countdown(self):
        self.lblCountdown.setText(
            "%d 秒后自动启动勾选的软件；点“取消”可中止本次。" % self._left)
        self.ok.setText("确认启动（%ds）" % self._left)

    def on_tick(self):
        self._left -= 1
        if self._left <= 0:
            self.timer.stop()
            self.do_confirm(auto=True)
        else:
            self._update_countdown()

    def reject(self):
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().reject()

    def do_confirm(self, auto=False):
        if self.timer.isActive():
            self.timer.stop()
        if not self.checks:
            self.reject()
            return
        self.selected = [dict(a) for cb, a in self.checks if cb.isChecked()]
        if not self.selected:
            if auto:
                # 自动确认时若全部取消勾选，则不启动（尊重用户取消意图）
                self.reject()
                return
            QMessageBox.information(self, "提示", "请至少勾选一个软件，或点“取消”。")
            return
        self.accept()


class LaunchWorker(QThread):
    done = Signal(dict)

    def __init__(self, items):
        super().__init__()
        self.items = items

    def run(self):
        self.done.emit(launch_apps(self.items))


class IndexWorker(QThread):
    done = Signal(list)

    def run(self):
        try:
            data = refresh_index()
            self.done.emit(data.get("apps", []))
        except Exception as e:
            log_error("IndexWorker.run", e)
            self.done.emit([])


class IndexDialog(QDialog):
    """从本机软件索引中选择软件加入清单。"""

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("从本机软件索引添加")
        self.resize(680, 480)
        self.cfg = cfg
        v = QVBoxLayout(self)
        tip = QLabel("扫描注册表中的已安装软件生成索引；首次约数秒，之后每次打开程序自动更新。\n"
                     "勾选多个软件后点“添加勾选项”可一次全部加入；搜索过滤、重新扫描都不会丢失已勾选状态。")
        tip.setWordWrap(True)
        v.addWidget(tip)
        self.edSearch = QLineEdit()
        self.edSearch.setPlaceholderText("搜索软件名或路径…")
        self.edSearch.textChanged.connect(self.filter_list)
        v.addWidget(self.edSearch)
        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(lambda it: self.add_checked(single=it))
        self.listw.itemChanged.connect(self.on_item_changed)
        v.addWidget(self.listw, 1)
        self.lblCount = QLabel("已勾选 0 项")
        v.addWidget(self.lblCount)
        h = QHBoxLayout()
        btnRescan = QPushButton("⟳ 重新扫描")
        btnRescan.clicked.connect(self.rescan)
        btnAll = QPushButton("全选可见项")
        btnAll.clicked.connect(self.check_all_visible)
        btnAdd = QPushButton("添加勾选项")
        btnAdd.clicked.connect(lambda: self.add_checked())
        btnCancel = QPushButton("关闭")
        btnCancel.clicked.connect(self.reject)
        h.addWidget(btnRescan)
        h.addWidget(btnAll)
        h.addStretch(1)
        h.addWidget(btnAdd)
        h.addWidget(btnCancel)
        v.addLayout(h)
        self.apps = []
        self.checked = {}   # path -> app dict（搜索/刷新时保留勾选）
        self._loading = False
        self.rescan()

    def rescan(self):
        self._loading = True
        self.listw.clear()
        self.listw.addItem(QListWidgetItem("正在扫描本机软件索引，请稍候…"))
        self.listw.setEnabled(False)
        self._loading = False
        self.worker = IndexWorker()
        self.worker.done.connect(self.on_index)
        self.worker.start()

    def on_index(self, apps):
        self._loading = True
        self.apps = apps
        self.listw.clear()
        self.listw.setEnabled(True)
        if not apps:
            self.listw.addItem(QListWidgetItem("未扫描到已安装软件（可尝试“重新扫描”）。"))
            self._loading = False
            self.update_count()
            return
        for a in apps:
            it = QListWidgetItem("%s    [%s]" % (a["name"], a["path"]))
            it.setData(Qt.UserRole, a)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if a["path"] in self.checked else Qt.Unchecked)
            self.listw.addItem(it)
        self._loading = False
        self.update_count()
        self.filter_list(self.edSearch.text())

    def filter_list(self, text):
        text = (text or "").lower()
        for row in range(self.listw.count()):
            it = self.listw.item(row)
            a = it.data(Qt.UserRole)
            if a is None:
                continue
            visible = (not text) or (text in a["name"].lower()) or (text in a["path"].lower())
            it.setHidden(not visible)

    def on_item_changed(self, item):
        if self._loading:
            return
        a = item.data(Qt.UserRole)
        if not a:
            return
        if item.checkState() == Qt.Checked:
            self.checked[a["path"]] = a
        else:
            self.checked.pop(a["path"], None)
        self.update_count()

    def update_count(self):
        self.lblCount.setText("已勾选 %d 项（搜索、刷新不会丢失勾选）" % len(self.checked))

    def check_all_visible(self):
        self._loading = True
        visible = [self.listw.item(r) for r in range(self.listw.count())
                   if not self.listw.item(r).isHidden() and self.listw.item(r).data(Qt.UserRole)]
        all_on = bool(visible) and all(it.checkState() == Qt.Checked for it in visible)
        for it in visible:
            it.setCheckState(Qt.Unchecked if all_on else Qt.Checked)
        self._loading = False
        self.update_count()

    def add_checked(self, single=None):
        if single is not None and not hasattr(single, "data"):
            single = None   # clicked(bool) 信号误传布尔值时忽略
        if single is not None:
            a = single.data(Qt.UserRole)
            chosen = [a] if a else []
        else:
            chosen = list(self.checked.values())
        added, dup = 0, 0
        for a in chosen:
            if any(x["path"].lower() == a["path"].lower() for x in self.cfg["apps"]):
                dup += 1
                continue
            self.cfg["apps"].append({"name": a["name"], "path": a["path"], "delay": 0,
                                     "args": "", "enabled": True, "days": normalize_days(None)})
            added += 1
        if added:
            save_config(self.cfg)
        QMessageBox.information(self, "已添加", "新增 %d 个软件到清单%s。"
                                % (added, ("，忽略重复 %d 个" % dup) if dup else ""))
        if added:
            self.accept()


# ---------------- main window ----------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("软件启动助手")
        self.resize(880, 500)
        self.cfg = load_config()
        self._loading = False
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

        h = QHBoxLayout()
        btnAdd = QPushButton("＋ 添加软件")
        btnAdd.clicked.connect(self.add_item)
        btnIndex = QPushButton("🔍 从索引添加")
        btnIndex.clicked.connect(self.add_from_index)
        self.btnLaunch = QPushButton("▶ 一键启动（全部启用项）")
        self.btnLaunch.clicked.connect(self.launch_all)
        self.chkAuto = QCheckBox("开机自启")
        self.chkAuto.setChecked(autostart_installed())
        self.chkAuto.toggled.connect(self.toggle_auto)
        self.spinCountdown = QSpinBox()
        self.spinCountdown.setRange(0, 120)
        self.spinCountdown.setSuffix(" 秒")
        self.spinCountdown.setToolTip("开机确认窗倒计时；0=不自动确认，需手动点。默认 5 秒")
        self.spinCountdown.setValue(self.cfg.get("confirm_seconds", DEFAULT_CONFIRM_SECONDS))
        self.spinCountdown.valueChanged.connect(self.on_countdown_changed)
        self.lblCd = QLabel("确认倒计时")
        btnQuit = QPushButton("退出程序")
        btnQuit.clicked.connect(self.close)
        h.addWidget(btnAdd)
        h.addWidget(btnIndex)
        h.addWidget(self.btnLaunch)
        h.addWidget(self.chkAuto)
        h.addStretch(1)
        h.addWidget(self.lblCd)
        h.addWidget(self.spinCountdown)
        h.addWidget(btnQuit)
        v.addLayout(h)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels(["启用", "名称", "程序路径", "延迟(秒)", "启动参数", "生效星期"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda it: self.edit_item(it.row()))
        self.table.itemChanged.connect(self.on_item_changed)
        v.addWidget(self.table)

        h2 = QHBoxLayout()
        btnEdit = QPushButton("编辑选中")
        btnEdit.clicked.connect(self.edit_selected)
        btnDel = QPushButton("删除选中")
        btnDel.clicked.connect(self.del_selected)
        h2.addWidget(btnEdit)
        h2.addWidget(btnDel)
        h2.addStretch(1)
        v.addLayout(h2)

        self.status = QLabel("")
        v.addWidget(self.status)
        self.render()

        # 后台刷新本机软件索引（首次建立，之后每次打开自动更新）
        self._idxWorker = IndexWorker()
        self._idxWorker.done.connect(self.on_index_updated)
        self._idxWorker.start()

    # ----- helpers -----
    def on_index_updated(self, apps):
        self.msg("本机软件索引已更新（%d 项）。" % len(apps))

    @log_exc
    def add_from_index(self):
        dlg = IndexDialog(self, self.cfg)
        if dlg.exec() == QDialog.Accepted:
            self.render()
            self.msg("清单已更新，共 %d 项。" % len(self.cfg["apps"]))
    def render(self):
        self._loading = True
        apps = self.cfg["apps"]
        self.table.setRowCount(len(apps))
        for i, a in enumerate(apps):
            en = QTableWidgetItem()
            en.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            en.setCheckState(Qt.Checked if a.get("enabled", True) else Qt.Unchecked)
            en.setTextAlignment(Qt.AlignCenter)
            cells = [en, QTableWidgetItem(a["name"]), QTableWidgetItem(a["path"]),
                     QTableWidgetItem(str(a.get("delay", 0))), QTableWidgetItem(a.get("args", "")),
                     QTableWidgetItem(days_label(a.get("days")))]
            for col, item in enumerate(cells):
                self.table.setItem(i, col, item)
        self._loading = False

    def msg(self, text):
        self.status.setText(text)

    # ----- events -----
    @log_exc
    def on_countdown_changed(self, value):
        self.cfg["confirm_seconds"] = int(value)
        save_config(self.cfg)
        self.msg("开机确认倒计时已设为 %d 秒%s。"
                 % (value, "（0=需手动确认）" if value == 0 else ""))

    @log_exc
    def on_item_changed(self, item):
        if self._loading or item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self.cfg["apps"]):
            self.cfg["apps"][row]["enabled"] = (item.checkState() == Qt.Checked)
            save_config(self.cfg)

    @log_exc
    def add_item(self):
        dlg = EditDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.cfg["apps"].append(dlg.item)
            save_config(self.cfg)
            self.render()
            self.msg("已添加：%s" % dlg.item["name"])

    @log_exc
    def edit_item(self, row):
        if not (0 <= row < len(self.cfg["apps"])):
            return
        dlg = EditDialog(self, self.cfg["apps"][row])
        if dlg.exec() == QDialog.Accepted:
            self.cfg["apps"][row] = dlg.item
            save_config(self.cfg)
            self.render()
            self.msg("已保存：%s" % dlg.item["name"])

    def edit_selected(self):
        r = self.table.currentRow()
        if r < 0:
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        self.edit_item(r)

    @log_exc
    def del_selected(self):
        r = self.table.currentRow()
        if not (0 <= r < len(self.cfg["apps"])):
            QMessageBox.information(self, "提示", "请先在表格中选中一行。")
            return
        name = self.cfg["apps"][r].get("name", "")
        if QMessageBox.question(self, "确认", "确定删除“%s”？" % name) != QMessageBox.Yes:
            return
        self.cfg["apps"].pop(r)
        save_config(self.cfg)
        self.render()
        self.msg("已删除：%s" % name)

    @log_exc
    def launch_all(self):
        enabled = [a for a in self.cfg["apps"] if a.get("enabled", True)]
        items = [a for a in enabled if is_scheduled_today(a)]
        self._not_today = len(enabled) - len(items)
        if not items:
            QMessageBox.information(self, "提示", "清单为空，或今天没有计划打开的软件。")
            return
        self.btnLaunch.setEnabled(False)
        self.msg("正在启动…")
        self.worker = LaunchWorker(items)
        self.worker.done.connect(self.on_launched)
        self.worker.start()

    @log_exc
    def on_launched(self, res):
        self.btnLaunch.setEnabled(True)
        extra = ""
        if getattr(self, "_not_today", 0) > 0:
            extra = "\n另有 %d 个启用软件不属于今天计划，未启动。" % self._not_today
        self.msg(summary_text(res) + extra)

    @log_exc
    def toggle_auto(self, checked):
        r = set_autostart(checked)
        self.msg(r["message"])
        if not r["ok"]:
            self.chkAuto.blockSignals(True)
            self.chkAuto.setChecked(not checked)
            self.chkAuto.blockSignals(False)


def main():
    app = QApplication(sys.argv)
    ip = app_icon_path()
    if ip:
        app.setWindowIcon(QIcon(ip))   # 窗口标题栏/任务栏图标
    if "--auto" in sys.argv:
        cfg = load_config()
        dlg = ConfirmDialog([a for a in cfg["apps"]
                             if a.get("enabled", True) and is_scheduled_today(a)],
                            seconds=cfg.get("confirm_seconds", DEFAULT_CONFIRM_SECONDS))
        if dlg.exec() == QDialog.Accepted:
            res = launch_apps(dlg.selected)
            QMessageBox.information(None, "开机启动", summary_text(res))
        return
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
