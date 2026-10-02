"""아바타 표정 그림 만들기: 캐릭터별 이모티콘 원본(360×360 투명 PNG)을 관전 화면 크기로 줄여 WebP 로 넣는다.

  python3 images/gemini/faces/make_faces.py --src <이모티콘 원본 폴더>

- 원본 폴더(리포 밖)는 <캐릭터>_kakao_v1/<NN_이름>.png 모양이다. 원본은 읽기만 한다
- 넣는 것은 web/faces.json 규칙표가 쓰는 표정만, 캐릭터는 chars/pool.json 30명 전부. 안 쓰는 표정은 넣지 않는다
- 크기는 faces.json size(한 변). 화면의 서 있는 키가 최대 약 110px 이라 2배 기준. 캔버스 여백 비율은 원본 그대로
- 메타데이터는 싣지 않는다: 새로 인코딩하고 EXIF·XMP·ICC 를 넘기지 않는다. 다 쓴 뒤 RIFF 청크를 읽어 그림 청크 말고는
  없는지 다시 잰다(원본 Gemini PNG 에는 C2PA 청크가 있다)
- 다 쓰면 faces.json 의 rev 를 그림 전부의 해시로 바꾼다. 관전 화면은 그림 주소에 ?v=rev 를 붙인다(CDN·브라우저 캐시)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FACES_JSON = REPO / "web" / "faces.json"
POOL = HERE.parent / "chars" / "pool.json"
PICTURE_CHUNKS = {b"VP8X", b"VP8 ", b"VP8L", b"ALPH"}
QUALITY = 82


def riff_chunks(p: Path) -> list[bytes]:
    b = p.read_bytes()
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP":
        raise ValueError(f"{p}: WebP 아님")
    out, i = [], 12
    while i + 8 <= len(b):
        tag, n = b[i:i + 4], struct.unpack("<I", b[i + 4:i + 8])[0]
        out.append(tag)
        i += 8 + n + (n & 1)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="이모티콘 원본 폴더 (<캐릭터>_kakao_v1/…)")
    a = ap.parse_args(argv)
    src = Path(a.src).expanduser()
    cfg = json.loads(FACES_JSON.read_text(encoding="utf-8"))
    size = int(cfg["size"])
    faces = sorted({f for r in cfg["rules"] for f in r["faces"]})
    chars = [c["id"] for c in json.loads(POOL.read_text(encoding="utf-8"))["pool"]]
    missing = [f"{c}/{f}" for c in chars for f in faces if not (src / f"{c}_kakao_v1" / f"{f}.png").exists()]
    if missing:
        print("원본 없음:", ", ".join(missing[:10]), file=sys.stderr)
        return 1
    written = []
    for c in chars:
        (HERE / c).mkdir(exist_ok=True)
        for f in faces:
            im = Image.open(src / f"{c}_kakao_v1" / f"{f}.png").convert("RGBA")
            if im.size != (cfg["canvas"], cfg["canvas"]):
                print(f"{c}/{f}: 캔버스 {im.size} ≠ {cfg['canvas']}", file=sys.stderr)
                return 1
            # 투명 가장자리가 검게 번지지 않게 알파를 곱한 채로 줄인다
            small = im.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")
            out = HERE / c / f"{f}.webp"
            small.save(out, "WEBP", quality=QUALITY, method=6, alpha_quality=90, exif=b"", icc_profile=None)
            extra = [t.decode("latin-1") for t in riff_chunks(out) if t not in PICTURE_CHUNKS]
            if extra:
                print(f"{out}: 그림 아닌 청크 {extra}", file=sys.stderr)
                return 1
            written.append(out)
    stale = [p for p in HERE.glob("*/*.webp") if p not in written]
    for p in stale:
        p.unlink()
    h = hashlib.sha256()
    for p in sorted(written):
        h.update(p.relative_to(HERE).as_posix().encode() + b"\0" + p.read_bytes())
    cfg_text = FACES_JSON.read_text(encoding="utf-8")
    old = cfg["rev"]
    new = h.hexdigest()[:10]
    FACES_JSON.write_text(cfg_text.replace(f'"rev": "{old}"', f'"rev": "{new}"', 1), encoding="utf-8")
    total = sum(p.stat().st_size for p in written)
    print(f"캐릭터 {len(chars)} × 표정 {len(faces)} = {len(written)}장 · {total / 1024:.0f}KB (한 장 평균 {total / len(written) / 1024:.1f}KB)"
          f" · 지운 옛 그림 {len(stale)} · rev {old} → {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
