# 去背切圖：把 H站產的綠幕素材表去掉綠底，找出每個物件，裁切、縮小後存檔。需要 Pillow 和 numpy（pip install pillow numpy）。
#
# 一般物件，一個物件存一張 WebP（依由上到下、由左到右的順序對應名稱）。遊戲裡的圖示用最長邊 128：
#   python tools/cut.py cut  素材表.png 輸出資料夾 列數 名稱1,名稱2,... 最長邊像素
#   例如：python tools/cut.py cut sheet.png cut 1 pearl,skewer,stool 128
# 動畫分解圖，同一個角色的幾格存成一條橫的 WebP，每格一樣大、頭和身體對準格子中間，
# 腳底對齊同一列的地面（跑步騰空那幾格會保留離地的高度）。分解圖排成幾列就填列數，由上到下、由左到右：
#   python tools/cut.py anim 動畫表.png 輸出.webp 格數 高度像素 [列數]
#   例如：python tools/cut.py anim walk.png cut/ol.webp 4 200
#         python tools/cut.py anim run8.png cut/hero1.webp 8 220 2
# 每次都會在輸出位置旁邊存一張 _preview_*.png 給你檢查，確認沒問題再複製到 assets/。
import sys, os
from collections import deque
import numpy as np
from PIL import Image, ImageFilter

F = 4   # objects are found on a 4x smaller mask


def key_out(src):
    a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
    border = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    key = np.median(border, axis=0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    dist = np.sqrt(((a - key) ** 2).sum(-1))
    green = g - np.maximum(r, b)                      # how much greener than the other channels
    alpha = np.clip((dist - 70) / 90, 0, 1)
    if key[1] > 150: alpha = np.minimum(alpha, np.clip((150 - green) / 80, 0, 1))
    amask = Image.fromarray((alpha * 255).astype(np.uint8))
    edge = np.asarray(amask.filter(ImageFilter.MinFilter(7))) < 250    # pixels near the cut line
    spill = edge & (g > np.maximum(r, b))
    a[..., 1] = np.where(spill, np.maximum(r, b), g)
    return np.dstack([a, alpha * 255]).clip(0, 255).astype(np.uint8), alpha


def objects(alpha):
    H, W = alpha.shape; h4, w4 = H // F, W // F
    m = alpha[:h4 * F, :w4 * F].reshape(h4, F, w4, F).max(axis=(1, 3)) > 0.5
    lab = np.zeros(m.shape, np.int32); comps = []
    for y in range(h4):
        for x in range(w4):
            if m[y, x] and not lab[y, x]:
                n = len(comps) + 1; q = deque([(y, x)]); lab[y, x] = n; x0 = x1 = x; y0 = y1 = y; area = 0
                while q:
                    cy, cx = q.popleft(); area += 1
                    x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                    for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                        if 0 <= ny < h4 and 0 <= nx < w4 and m[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n; q.append((ny, nx))
                comps.append([x0, y0, x1 + 1, y1 + 1, area, [n]])
    comps.sort(key=lambda c: -c[4])
    big = [c for c in comps if c[4] >= comps[0][4] * 0.06]
    for s in (c for c in comps if c[4] < comps[0][4] * 0.06 and c[4] >= 6):   # attach detached bits (drops, sparkles) to the nearest big object
        cx, cy = (s[0] + s[2]) / 2, (s[1] + s[3]) / 2
        best = min(big, key=lambda c: max(c[0] - cx, 0, cx - c[2]) + max(c[1] - cy, 0, cy - c[3]))
        if max(best[0] - cx, 0, cx - best[2]) + max(best[1] - cy, 0, cy - best[3]) < 12:
            best[0], best[1], best[2], best[3] = min(best[0], s[0]), min(best[1], s[1]), max(best[2], s[2]), max(best[3], s[3]); best[5] += s[5]
    return lab, big


def crop(rgba, lab, c, bottom=False):
    """Only this object's pixels, never a neighbour's, cropped to its bounding box."""
    H, W = rgba.shape[:2]
    own = np.isin(lab, c[5]).repeat(F, 0).repeat(F, 1)
    own = np.pad(own, ((0, H - own.shape[0]), (0, W - own.shape[1])))
    own = np.asarray(Image.fromarray(own.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(5))) > 0
    mine = rgba.copy(); mine[..., 3] = np.where(own, mine[..., 3], 0)
    box = (max(0, c[0] * F - 6), max(0, c[1] * F - 6), min(W, c[2] * F + 6), min(H, c[3] * F + 6))
    im = Image.fromarray(mine, 'RGBA').crop(box); bb = im.getbbox()
    if bottom: return im.crop(bb), box[1] + bb[3]   # also where its lowest pixel sits on the sheet
    return im.crop(bb)


def preview(ims, path, gap=10):
    w = sum(i.width for i in ims) + gap * (len(ims) + 1); h = max(i.height for i in ims) + gap * 2
    p = Image.new('RGBA', (w, h), (28, 24, 54, 255)); x = gap
    for i in ims: p.alpha_composite(i, (x, h - gap - i.height)); x += i.width + gap
    p.save(path)


def cut(src, outdir, rows, names, maxpx):
    os.makedirs(outdir, exist_ok=True)
    rgba, alpha = key_out(src); lab, big = objects(alpha)
    print('找到', len(big), '個物件，預期', len(names))
    big.sort(key=lambda c: (c[1] + c[3]) / 2)
    per = -(-len(big) // rows); ordered = []
    for i in range(rows): ordered += sorted(big[i * per:(i + 1) * per], key=lambda c: c[0])
    outs = []
    for name, c in zip(names, ordered):
        im = crop(rgba, lab, c); s = maxpx / max(im.size)
        if s < 1: im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
        im.save(os.path.join(outdir, name + '.webp'), 'WEBP', quality=88, method=6); outs.append(im)
        print(name, im.size)
    preview([o.copy() for o in outs], os.path.join(outdir, '_preview_' + os.path.basename(src)))


def anim(src, dst, n, height, rows=1):
    rgba, alpha = key_out(src); lab, big = objects(alpha)
    big.sort(key=lambda c: (c[1] + c[3]) / 2)
    ys = [(c[1] + c[3]) / 2 for c in big]   # split into rows at the widest vertical gaps
    cuts = sorted(sorted(range(1, len(big)), key=lambda i: ys[i] - ys[i - 1])[-(rows - 1):]) if rows > 1 else []
    groups = [big[i:j] for i, j in zip([0] + cuts, cuts + [len(big)])]
    frames, row_of = [], []
    for r, grp in enumerate(groups):
        grp.sort(key=lambda c: c[0]); row = []
        for c in grp:   # a piece that sits mostly inside the previous frame's left-to-right span belongs to that frame
            if row and min(row[-1][2], c[2]) - c[0] > 0.5 * (c[2] - c[0]):
                f = row[-1]; f[0], f[1], f[2], f[3] = min(f[0], c[0]), min(f[1], c[1]), max(f[2], c[2]), max(f[3], c[3]); f[5] += c[5]
            else: row.append(c)
        frames += row; row_of += [r] * len(row)
    if len(frames) != n:
        print('找到', len(frames), '格，預期', n, '格，請重產這張'); sys.exit(1)
    got = [crop(rgba, lab, c, bottom=True) for c in frames]
    base = {r: max(b for (_, b), rr in zip(got, row_of) if rr == r) for r in set(row_of)}
    lift = [base[r] - b for (_, b), r in zip(got, row_of)]   # how far a frame's feet are off its row's ground (a jump in a run cycle)
    ims = [i for i, _ in got]
    s = height / max(i.height for i in ims)
    ims = [i.resize((max(1, round(i.width * s)), max(1, round(i.height * s))), Image.LANCZOS) for i in ims]
    lift = [l * s for l in lift]
    anchors = []
    for i in ims:   # centre on the head and body, not on the swinging legs
        a = np.asarray(i)[..., 3].astype(np.float32)[: int(i.height * 0.55)]
        cols = a.sum(0); anchors.append(float((cols * np.arange(len(cols))).sum() / max(cols.sum(), 1)))
    left = max(anchors); right = max(i.width - a for i, a in zip(ims, anchors))
    cw, ch = int(np.ceil(left + right)) + 2, int(np.ceil(max(i.height + l for i, l in zip(ims, lift))))
    strip = Image.new('RGBA', (cw * n, ch), (0, 0, 0, 0))
    for k, (i, a, l) in enumerate(zip(ims, anchors, lift)): strip.alpha_composite(i, (k * cw + round(left - a) + 1, round(ch - i.height - l)))
    os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
    strip.save(dst, 'WEBP', quality=82, method=6)
    preview([strip], os.path.join(os.path.dirname(dst) or '.', '_preview_' + os.path.splitext(os.path.basename(dst))[0] + '.png'))
    print(os.path.basename(dst), '每格', cw, 'x', ch, '離地', [round(l) for l in lift])


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'cut': cut(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5].split(','), int(sys.argv[6]))
    elif mode == 'anim': anim(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]) if len(sys.argv) > 6 else 1)
    else: print('第一個參數要是 cut 或 anim')
