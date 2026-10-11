# 地面磚：把 H站產的地面圖裁成正方形、做成可以無縫拼接，並調暗讓角色比較顯眼。
# 用法：python tools/tile.py 地面.png assets/ground1.jpg 640 亮度(0.85) 飽和度(0.95)
import sys
import numpy as np
from PIL import Image, ImageEnhance
src, dst, px, bright, sat = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
im = Image.open(src).convert('RGB'); w, h = im.size; s = min(w, h)
im = im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((px, px), Image.LANCZOS)
im = ImageEnhance.Color(ImageEnhance.Brightness(im).enhance(bright)).enhance(sat)
a = np.asarray(im).astype(np.float32)
b = np.roll(a, (px // 2, px // 2), (0, 1))                 # its seams sit in the middle, its edges wrap cleanly
t = np.linspace(-1, 1, px); d = np.maximum(np.abs(t)[None, :], np.abs(t)[:, None])
wgt = np.clip((0.92 - d) / 0.5, 0, 1)[..., None]            # 1 in the centre, 0 at the tile edges
out = a * wgt + b * (1 - wgt)
Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst, quality=82, optimize=True, progressive=True)
