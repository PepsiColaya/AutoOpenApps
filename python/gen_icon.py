# -*- coding: utf-8 -*-
"""生成 AutoOpenApps 应用图标：自创几何图形（圆角蓝底 + 白色电源符号）。
电源符号是通用符号，自绘不侵犯任何版权/商标。输出多尺寸 icon.ico + 预览 png。
"""
import os

from PIL import Image, ImageDraw

S = 1024  # 超采样画布，最后缩到 512
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 1) 蓝色垂直渐变背景
base = Image.new("RGB", (S, S))
bd = ImageDraw.Draw(base)
top, bottom = (37, 99, 235), (30, 64, 175)   # #2563eb -> #1e40af
for y in range(S):
    t = y / (S - 1)
    c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    bd.line([(0, y), (S, y)], fill=c)

# 2) 裁成圆角方形（透明四角）
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=230, fill=255)
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(base, (0, 0), mask)
d = ImageDraw.Draw(img)

# 3) 白色“电源”符号：缺口朝上的圆环 + 竖条
W = (255, 255, 255, 255)
cx, cy, R, w = 512, 560, 300, 92
d.arc([cx - R, cy - R, cx + R, cy + R], start=110, end=430, fill=W, width=w)
bar_w = 96
d.rounded_rectangle([cx - bar_w // 2, cy - R - 20, cx + bar_w // 2, cy + 20],
                    radius=bar_w // 2, fill=W)

# 4) 缩到 512 并导出多尺寸 ico + 预览 png
img512 = img.resize((512, 512), Image.LANCZOS)
img512.save("icon.ico", sizes=[(256, 256), (128, 128), (96, 96), (64, 64),
                               (48, 48), (32, 32), (16, 16)])
img512.save("icon_256.png")
print("icon.ico + icon_256.png generated at", os.getcwd())
