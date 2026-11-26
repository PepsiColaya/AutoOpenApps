# -*- coding: utf-8 -*-
# 生成虚构演示数据的界面截图（替换含真实信息的仓库截图）
from PIL import Image, ImageDraw, ImageFont
import os

BASE = r"C:\Users\cola\WorkBuddy AI\myComputer\AutoOpenApps"
OUT = os.path.join(BASE, "screenshots")

FONT = r"C:\Windows\Fonts\msyh.ttc"
def F(size):
    return ImageFont.truetype(FONT, size)

BG      = (240, 240, 240)   # Win11 浅灰
WHITE   = (255, 255, 255)
BORDER  = (200, 200, 200)
TEXT    = (30, 30, 30)
SUB     = (110, 110, 110)
BLUE    = (0, 102, 204)
HEADBG  = (249, 249, 249)
LINE    = (229, 229, 229)

def rrect(d, xy, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def checkbox(d, x, y, s=15):
    d.rectangle([x, y, x + s, y + s], fill=WHITE, outline=(150, 150, 150), width=1)

def titlebar(d, w, title, h=34):
    d.rectangle([0, 0, w, h], fill=BG)
    d.text((12, h // 2), title, font=F(15), fill=TEXT, anchor="lm")
    # 关闭按钮
    d.line([w - 26, 10, w - 12, 24], fill=TEXT, width=2)
    d.line([w - 12, 10, w - 26, 24], fill=TEXT, width=2)
    d.line([0, h, w, h], fill=BORDER, width=1)

# ------------------------------------------------------------
# 1) 索引对话框（虚构数据）
# ------------------------------------------------------------
def gen_index():
    W, H = 1020, 663
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    titlebar(d, W, "从本机索引添加")

    # 搜索框
    rrect(d, [14, 56, 500, 94], 6, fill=WHITE, outline=BORDER, width=1)
    d.text((28, 75), "搜索软件名 / 路径...", font=F(15), fill=SUB, anchor="lm")
    # 刷新按钮
    rrect(d, [514, 56, 646, 94], 6, fill=WHITE, outline=BORDER, width=1)
    d.text((580, 75), "刷新索引", font=F(15), fill=TEXT, anchor="lm")
    # 计数
    d.text((W - 20, 75), "索引到 15 个软件，当前显示 15 个", font=F(15), fill=TEXT, anchor="rm")

    # 列表
    lx0, ly0, lx1, ly1 = 14, 106, W - 24, H - 66
    d.rectangle([lx0, ly0, lx1, ly1], fill=WHITE, outline=BORDER, width=1)
    # 表头
    d.text((lx0 + 14, ly0 + 16), "软件名称", font=F(15), fill=TEXT, anchor="lm")
    d.text((lx0 + 320, ly0 + 16), "程序路径", font=F(15), fill=TEXT, anchor="lm")
    d.line([lx0, ly0 + 32, lx1, ly0 + 32], fill=LINE, width=1)

    apps = [
        ("示例浏览器",       r"C:\Program Files\Example\Browser\browser.exe"),
        ("示例音乐播放器",   r"C:\Program Files\Example\Music\music.exe"),
        ("示例视频播放器",   r"C:\Program Files\Example\Video\video.exe"),
        ("示例压缩工具",     r"C:\Program Files\Example\Zip\zip.exe"),
        ("示例办公套件",     r"C:\Program Files\Example\Office\office.exe"),
        ("示例笔记软件",     r"C:\Program Files\Example\Notes\notes.exe"),
        ("示例邮箱客户端",   r"C:\Program Files\Example\Mail\mail.exe"),
        ("示例网盘",         r"C:\Program Files\Example\Cloud\cloud.exe"),
        ("示例输入法",       r"C:\Program Files\Example\IME\ime.exe"),
        ("示例安全卫士",     r"C:\Program Files\Example\Security\security.exe"),
        ("示例下载工具",     r"C:\Program Files\Example\Download\download.exe"),
        ("示例聊天软件",     r"C:\Program Files\Example\Chat\chat.exe"),
        ("示例日历",         r"C:\Program Files\Example\Calendar\calendar.exe"),
        ("示例截图工具",     r"C:\Program Files\Example\Capture\capture.exe"),
        ("示例文本编辑器",   r"C:\Program Files\Example\Editor\editor.exe"),
    ]
    y = ly0 + 33
    rh = (ly1 - y) // len(apps)
    for i, (name, path) in enumerate(apps):
        ry = y + i * rh
        if i % 2 == 1:
            d.rectangle([lx0 + 1, ry, lx1 - 1, ry + rh], fill=(250, 250, 250))
        checkbox(d, lx0 + 14, ry + rh // 2 - 8)
        d.text((lx0 + 42, ry + rh // 2), name, font=F(15), fill=TEXT, anchor="lm")
        d.text((lx0 + 320, ry + rh // 2), path, font=F(14), fill=TEXT, anchor="lm")
        d.line([lx0 + 1, ry, lx1 - 1, ry], fill=LINE, width=1)
    # 滚动条
    d.rectangle([lx1 + 3, ly0, W - 15, ly1], fill=(245, 245, 245))
    d.rectangle([lx1 + 5, ly0 + 4, W - 17, ly0 + 260], fill=(205, 205, 205))

    # 添加勾选项按钮
    rrect(d, [W - 152, H - 52, W - 16, H - 14], 6, fill=WHITE, outline=(120, 160, 220), width=1)
    d.text((W - 84, H - 33), "添加勾选项", font=F(15), fill=TEXT, anchor="lm")

    img.save(os.path.join(OUT, "index.png"), optimize=True)
    print("index.png", os.path.getsize(os.path.join(OUT, "index.png")))

# ------------------------------------------------------------
# 2) 主窗口（虚构数据）
# ------------------------------------------------------------
def gen_manager():
    W, H = 940, 620
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    # 标题栏
    d.rectangle([0, 0, W, 30], fill=BG)
    d.ellipse([10, 8, 26, 24], fill=(70, 130, 220))
    d.text((34, 15), "AutoOpenApps 软件管理", font=F(14), fill=TEXT, anchor="lm")
    for i, sym in enumerate(["—", "□", "×"]):
        d.text((W - 96 + i * 32, 15), sym, font=F(14), fill=TEXT, anchor="mm")
    d.line([0, 30, W, 30], fill=BORDER, width=1)

    btns = ["添加软件", "从索引添加", "编辑", "删除", "立即启动", "移除开机启动"]
    x = 12
    for b in btns:
        w = 96 if len(b) <= 4 else 118
        rrect(d, [x, 40, x + w, 72], 4, fill=WHITE, outline=BORDER, width=1)
        d.text((x + w // 2, 56), b, font=F(14), fill=TEXT, anchor="mm")
        x += w + 8

    # 列表
    lx0, ly0, lx1, ly1 = 12, 84, W - 12, H - 40
    d.rectangle([lx0, ly0, lx1, ly1], fill=WHITE, outline=BORDER, width=1)
    cols = [(lx0 + 8, "#"), (lx0 + 52, "软件名称"), (lx0 + 210, "路径"), (lx0 + 620, "打开计划"), (lx0 + 760, "状态")]
    for cx, t in cols:
        d.text((cx, ly0 + 16), t, font=F(15), fill=TEXT, anchor="lm")
    d.line([lx0, ly0 + 32, lx1, ly0 + 32], fill=LINE, width=1)

    rows = [
        ("1", "示例音乐播放器", r"C:\Program Files\Example\Music\music.exe", "每天", "开机启动"),
        ("2", "示例压缩工具",   r"C:\Program Files\Example\Zip\zip.exe",     "周一至周五", "开机启动"),
        ("3", "示例笔记软件",   r"C:\Program Files\Example\Notes\notes.exe", "周六、周日", "已停用"),
    ]
    y = ly0 + 33
    rh = 34
    for i, row in enumerate(rows):
        ry = y + i * rh
        if i < 2:  # 演示多选：前两行选中高亮
            d.rectangle([lx0 + 1, ry, lx1 - 1, ry + rh], fill=(0, 120, 215))
            tcol = WHITE
        else:
            if i % 2 == 1:
                d.rectangle([lx0 + 1, ry, lx1 - 1, ry + rh], fill=(250, 250, 250))
            tcol = TEXT
        d.text((lx0 + 8, ry + rh // 2), row[0], font=F(14), fill=tcol, anchor="lm")
        d.text((lx0 + 52, ry + rh // 2), row[1], font=F(14), fill=tcol, anchor="lm")
        d.text((lx0 + 210, ry + rh // 2), row[2], font=F(13), fill=tcol, anchor="lm")
        d.text((lx0 + 620, ry + rh // 2), row[3], font=F(14), fill=tcol, anchor="lm")
        d.text((lx0 + 760, ry + rh // 2), row[4], font=F(14), fill=tcol, anchor="lm")
        d.line([lx0 + 1, ry, lx1 - 1, ry], fill=LINE, width=1)

    # 状态栏
    d.text((12, H - 20), "配置: C:\\Users\\Demo\\AppData\\Roaming\\AutoOpenApps\\apps.txt    |    "
                         "参与开机启动: 2 个软件    |    启动快捷方式: 已创建    |    确认倒计时: 30 秒",
           font=F(13), fill=TEXT, anchor="lm")

    img.save(os.path.join(OUT, "manager.png"), optimize=True)
    print("manager.png", os.path.getsize(os.path.join(OUT, "manager.png")))

# ------------------------------------------------------------
# 3) 开机确认窗口（虚构数据）
# ------------------------------------------------------------
def gen_confirm():
    W, H = 810, 645
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    titlebar(d, W, "AutoOpenApps - 开机启动确认")

    d.rectangle([10, 46, W - 10, 78], fill=HEADBG)
    d.text((22, 62), "以下软件计划在今天自动打开，请核对并勾选需要启动的项目：", font=F(15), fill=TEXT, anchor="lm")

    # 列表
    lx0, ly0, lx1 = 24, 92, W - 24
    d.text((lx0 + 8, ly0 + 14), "软件名称", font=F(15), fill=TEXT, anchor="lm")
    d.text((lx0 + 300, ly0 + 14), "程序路径", font=F(15), fill=TEXT, anchor="lm")
    d.line([lx0, ly0 + 32, lx1, ly0 + 32], fill=LINE, width=1)

    apps = [
        ("示例音乐播放器", r"C:\Program Files\Example\Music\music.exe"),
        ("示例压缩工具",   r"C:\Program Files\Example\Zip\zip.exe"),
        ("示例笔记软件",   r"C:\Program Files\Example\Notes\notes.exe"),
    ]
    y = ly0 + 33
    rh = 30
    for i, (name, path) in enumerate(apps):
        ry = y + i * rh
        bx, by = lx0 + 8, ry + rh // 2 - 8  # 选中复选框（蓝底白勾）
        d.rectangle([bx, by, bx + 15, by + 15], fill=(0, 120, 215))
        d.line([bx + 3, by + 8, bx + 6, by + 11], fill=WHITE, width=2)
        d.line([bx + 6, by + 11, bx + 12, by + 4], fill=WHITE, width=2)
        d.text((lx0 + 34, ry + rh // 2), str(i + 1), font=F(14), fill=TEXT, anchor="lm")
        d.text((lx0 + 70, ry + rh // 2), name, font=F(14), fill=TEXT, anchor="lm")
        d.text((lx0 + 300, ry + rh // 2), path, font=F(13), fill=TEXT, anchor="lm")
        d.line([lx0, ry, lx1, ry], fill=LINE, width=1)

    # 倒计时与按钮
    d.rectangle([10, H - 150, W - 10, H - 118], fill=HEADBG)
    d.text((22, H - 134), "5 秒后将自动启动勾选的软件...", font=F(15), fill=TEXT, anchor="lm")
    rrect(d, [W - 320, H - 100, W - 180, H - 58], 6, fill=WHITE, outline=(120, 160, 220), width=1)
    d.text((W - 250, H - 79), "启动 (5)", font=F(15), fill=TEXT, anchor="mm")
    rrect(d, [W - 168, H - 100, W - 28, H - 58], 6, fill=WHITE, outline=BORDER, width=1)
    d.text((W - 98, H - 79), "取消", font=F(15), fill=TEXT, anchor="mm")

    img.save(os.path.join(OUT, "confirm.png"), optimize=True)
    print("confirm.png", os.path.getsize(os.path.join(OUT, "confirm.png")))

gen_index()
gen_manager()
gen_confirm()
print("done")
