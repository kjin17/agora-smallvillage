"""Gemini 초록 배경 시트 → 칸별 투명 PNG.

사용: cut_sheet.py <sheet.png> <out_dir> <cols> <rows> name1 name2 ...  (행 우선, '-' 는 건너뜀)
- 배경 판정은 g>90 && g-max(r,b)>60 (어두운 초록 그림자 포함). 느슨한 g>r+35 는 초록 엄지·플라스크 같은 연두를 뚫는다
- 칸 안에서 가장 큰 덩어리의 5% 미만 조각은 버린다(오른쪽 아래 Gemini 반짝이 워터마크, 튄 점)
- 배경에 닿은 테두리에서 초록기 도는 픽셀은 2겹까지 깎고, 남은 테두리 2px 는 초록 번짐만 걷는다(그림 속 초록은 그대로)
"""
import os, sys
from collections import deque

import numpy as np
from PIL import Image

src, out_dir, cols, rows = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
names = sys.argv[5:]
assert len(names) == cols * rows, 'names != cols*rows'
os.makedirs(out_dir, exist_ok=True)
im = np.asarray(Image.open(src).convert('RGB')).astype(int)
r, g, b = im[..., 0], im[..., 1], im[..., 2]
bg = (g > 90) & (g - np.maximum(r, b) > 60)
H, W = bg.shape


def components(m):
    lab = np.zeros(m.shape, int)
    sizes = [0]
    h, w = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if lab[y0, x0]:
            continue
        k = len(sizes); sizes.append(0)
        q = deque([(y0, x0)]); lab[y0, x0] = k
        while q:
            y, x = q.popleft(); sizes[k] += 1
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = k; q.append((yy, xx))
    return lab, sizes


def near(mask, n):
    out = mask.copy()
    for _ in range(n):
        s = out.copy()
        s[1:] |= out[:-1]; s[:-1] |= out[1:]; s[:, 1:] |= out[:, :-1]; s[:, :-1] |= out[:, 1:]
        out = s
    return out


for i, name in enumerate(names):
    if name == '-':
        continue
    rr, cc = divmod(i, cols)
    y0, y1 = rr * H // rows, (rr + 1) * H // rows
    x0, x1 = cc * W // cols, (cc + 1) * W // cols
    fg = ~bg[y0:y1, x0:x1]
    lab, sizes = components(fg)
    big = max(sizes)
    keep = np.isin(lab, [k for k, s in enumerate(sizes) if k and s >= 0.05 * big])
    ys, xs = np.nonzero(keep)
    a0, a1, b0, b1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = im[y0:y1, x0:x1][a0:a1, b0:b1].copy()
    mk = keep[a0:a1, b0:b1].copy()
    gg = rgb[..., 1]; mx = np.maximum(rgb[..., 0], rgb[..., 2])
    for _ in range(2):  # 배경에 닿은 초록기 도는 반투명 테두리 깎기
        mk &= ~(near(~mk, 1) & (gg > mx + 12))
    edge = near(~mk, 2) & mk
    rgb[..., 1] = np.where(edge & (gg > mx + 10), mx + 10, gg)
    out = np.dstack([rgb.clip(0, 255).astype(np.uint8), (mk * 255).astype(np.uint8)])
    dst = os.path.join(out_dir, f'{name}.png')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray(out).save(dst)
    print(name, b1 - b0, a1 - a0, 'touches-cell-edge' if (a0 == 0 or b0 == 0 or a1 == y1 - y0 or b1 == x1 - x0) else '')
