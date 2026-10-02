"""09-25 추가 캐릭터 시트(초록 배경, 4×2) → 캐릭터별 투명 PNG.

사용: cut_chars_0925.py <sheet.png> <out_dir> name1 … name8  (행 우선, '-' 는 건너뜀, `candidates/이름` 가능)
- 칸으로 자르지 않고 덩어리로 가른다. 시트 전체에서 가장 큰 덩어리 8개 = 캐릭터(윗줄·아랫줄, 왼→오 순),
  나머지 덩어리는 가장 가까운 캐릭터에 붙인다(저글링 공, 떨어진 반짝이). 등분으로 자르면 윗줄 발끝이
  잘리고, 윗칸으로 솟은 연·떨어진 공은 칸 경계를 넘는다
- MIN_PX 미만 조각은 버린다(튄 점). 붙인 조각은 전부 출력해 워터마크가 딸려 가지 않았는지 눈으로 본다
- 배경 판정·테두리 번짐 처리는 ../cut_sheet.py 와 같다
"""
import os, sys
from collections import deque

import numpy as np
from PIL import Image

MIN_PX = 60
src, out_dir, names = sys.argv[1], sys.argv[2], sys.argv[3:]
assert len(names) == 8, 'need 8 names'
im = np.asarray(Image.open(src).convert('RGB')).astype(int)
r, g, b = im[..., 0], im[..., 1], im[..., 2]
fg = ~((g > 90) & (g - np.maximum(r, b) > 60))
H, W = fg.shape


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


lab, sizes = components(fg)
order = sorted(range(1, len(sizes)), key=lambda k: -sizes[k])
chars = order[:8]
cent = {}
for k in chars:
    ys, xs = np.nonzero(lab == k)
    cent[k] = (ys.mean(), xs.mean())
top = sorted(chars, key=lambda k: cent[k][0])[:4]
chars = sorted(top, key=lambda k: cent[k][1]) + sorted([k for k in chars if k not in top], key=lambda k: cent[k][1])
members = {k: [k] for k in chars}
for k in order[8:]:
    if sizes[k] < MIN_PX:
        continue
    ys, xs = np.nonzero(lab == k)
    cy, cx = ys.mean(), xs.mean()
    owner = min(chars, key=lambda c: (cent[c][0] - cy) ** 2 + (cent[c][1] - cx) ** 2)
    members[owner].append(k)
    print(f'  piece {sizes[k]}px at ({int(cx)},{int(cy)}) -> {names[chars.index(owner)]}')

for i, name in enumerate(names):
    if name == '-':
        continue
    keep = np.isin(lab, members[chars[i]])
    ys, xs = np.nonzero(keep)
    a0, a1, b0, b1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = im[a0:a1, b0:b1].copy()
    mk = keep[a0:a1, b0:b1].copy()
    gg = rgb[..., 1]; mx = np.maximum(rgb[..., 0], rgb[..., 2])
    for _ in range(2):
        mk &= ~(near(~mk, 1) & (gg > mx + 12))
    edge = near(~mk, 2) & mk
    rgb[..., 1] = np.where(edge & (gg > mx + 10), mx + 10, gg)
    out = np.dstack([rgb.clip(0, 255).astype(np.uint8), (mk * 255).astype(np.uint8)])
    dst = os.path.join(out_dir, f'{name}.png')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    Image.fromarray(out).save(dst)
    print(name, b1 - b0, a1 - a0)
