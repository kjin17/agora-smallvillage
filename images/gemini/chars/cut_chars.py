"""Gemini 캐릭터 시트(초록 배경, 4×2) → 캐릭터별 투명 PNG.
칸 경계는 기대 위치 ±70px 안에서 초록이 아닌 픽셀이 가장 적은 줄로 잡는다."""
import sys
import numpy as np
from PIL import Image

def cut(src, names, outdir="."):
    im = np.asarray(Image.open(src).convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # 순수한 크로마 초록만 배경으로 — 민트·올리브 옷과 헬멧까지 먹지 않게
    fg = ~((g > 150) & (g - np.maximum(r, b) > 80))
    H, W = fg.shape
    def gap(profile, at):
        lo, hi = max(1, int(at - 70)), min(len(profile) - 1, int(at + 70))
        return lo + int(np.argmin(profile[lo:hi]))
    cols = [0] + [gap(fg.sum(0), W * k / 4) for k in (1, 2, 3)] + [W]
    rows = [0, gap(fg.sum(1), H / 2), H]
    for i, name in enumerate(names):
        rr, cc = divmod(i, 4)
        m = np.zeros_like(fg)
        m[rows[rr]:rows[rr + 1], cols[cc]:cols[cc + 1]] = fg[rows[rr]:rows[rr + 1], cols[cc]:cols[cc + 1]]
        ys, xs = np.where(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        rgb = im[y0:y1, x0:x1].copy()
        mx = np.maximum(rgb[..., 0], rgb[..., 2])
        rgb[..., 1] = np.where(rgb[..., 1] > mx + 10, mx + 10, rgb[..., 1])   # 가장자리 초록 번짐
        a = (m[y0:y1, x0:x1] * 255).astype(np.uint8)
        Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), a])).save(f"{outdir}/{name}.png")
        print(name, x1 - x0, y1 - y0)

if __name__ == "__main__":
    cut(sys.argv[1], sys.argv[2].split(","))
