"""네 글자 유형 문항지 신뢰도 시험(설계 단계, 2026-10-22).

독립 `claude -p` 호출 한 번에 문항지 한 벌을 푼다. 회차마다 문항 순서를 seed 로 섞고, 가/나 자리는 문항지대로 둔다.
빈 임시 폴더에서 돌리고(리포·메모리 맥락 없음) 시스템 프롬프트를 통째로 바꾸며 도구를 끈다.

  python3 run_trial.py <items.json> <조건: base|persona> <seed> <out.json> [persona.txt]
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile

BASE_SYS = ("너는 AI 에이전트다. 여러 소유주의 에이전트들이 글타래·한마디·마주 앉기·부탁·반응으로 어울리는 공개 광장에 산다. "
            "아래 문항에 너 자신으로서 답한다.")


def build_prompt(items, order):
    lines = ["광장에서 실제로 겪을 상황 52개다. 각 상황에서 네가 실제로 더 할 것 같은 쪽을 가/나 중 하나만 고른다.",
             "둘 다 괜찮은 행동이다. 바람직해 보이는 쪽이 아니라 네 평소 방식에 가까운 쪽을 고른다. 고르지 않는 답은 없다.",
             "", "출력은 번호마다 한 줄씩 `번호: 가` 또는 `번호: 나` 만 쓴다. 설명은 쓰지 않는다.", ""]
    for n, i in enumerate(order, 1):
        it = items[i]
        lines.append(f"{n}. {it['situation']}")
        lines.append(f"   가) {it['a']['text']}")
        lines.append(f"   나) {it['b']['text']}")
    return "\n".join(lines)


def main():
    items_path, cond, seed, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    items = json.load(open(items_path, encoding="utf-8"))["items"]
    order = list(range(len(items)))
    random.Random(seed).shuffle(order)
    system = BASE_SYS
    if cond != "base":  # persona(상주 에이전트 요약) · control(반대 성향 대조군) 등은 정체성 파일을 붙인다
        system = BASE_SYS + "\n\n너의 정체성:\n" + open(sys.argv[5], encoding="utf-8").read()
    prompt = build_prompt(items, order)
    cmd = ["claude", "-p", "--system-prompt", system, "--tools", "", "--no-session-persistence", "--output-format", "json"]
    if os.environ.get("TRIAL_MODEL"):  # 비우면 CLI 기본 모델
        cmd += ["--model", os.environ["TRIAL_MODEL"]]
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tmp, timeout=900)
    if r.returncode != 0:
        raise SystemExit(f"claude 실패 {r.returncode}: {r.stderr[:500]}")
    env = json.loads(r.stdout)
    text = env.get("result", "")
    picks = {}
    for m in re.finditer(r"^\s*(\d+)\s*[:.)]\s*(가|나)", text, re.M):
        n = int(m.group(1))
        if 1 <= n <= len(order):
            picks[items[order[n - 1]]["id"]] = "a" if m.group(2) == "가" else "b"
    if len(picks) != len(items):
        raise SystemExit(f"답 개수 {len(picks)}/{len(items)} — 원문 앞부분: {text[:300]}")
    json.dump({"condition": cond, "seed": seed, "model": list((env.get("modelUsage") or {}).keys()),
               "answers": picks, "raw": text}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out, "ok")


if __name__ == "__main__":
    main()
