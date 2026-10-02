"""Gemini 소품 시트(초록 배경) → 소품별 투명 PNG. 4열×2행 칸 경계는 시트를 보고 정한 값."""
import sys
from PIL import Image
import numpy as np
src = sys.argv[1] if len(sys.argv) > 1 else "sheet_v1.png"
names = [["stele", "stall", "bell", "bell2"], ["board", "fountain", "bench", "bench2"]]
im = np.asarray(Image.open(src).convert("RGB")).astype(int)
r, g, b = im[..., 0], im[..., 1], im[..., 2]
green = (g > r + 35) & (g > b + 35)          # 배경과 초록 그림자
H, W = green.shape
COLS, ROWS = [0, 370, 740, 1040, W], [0, 395, H]
for row in range(2):
  for col in range(4):
    m = np.zeros_like(green)
    m[ROWS[row]:ROWS[row + 1], COLS[col]:COLS[col + 1]] = ~green[ROWS[row]:ROWS[row + 1], COLS[col]:COLS[col + 1]]
    ys, xs = np.where(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = im[y0:y1, x0:x1].copy(); mk = m[y0:y1, x0:x1]
    # 가장자리 초록 번짐 걷기
    gg = rgb[..., 1]; mx = np.maximum(rgb[..., 0], rgb[..., 2])
    spill = gg > mx + 10
    rgb[..., 1] = np.where(spill, mx + 10, gg)
    a = (mk * 255).astype(np.uint8)
    out = np.dstack([rgb.clip(0, 255).astype(np.uint8), a])
    name = names[row][col]
    Image.fromarray(out, "RGBA").save(f"{name}.png")
    print(name, x1 - x0, y1 - y0)
