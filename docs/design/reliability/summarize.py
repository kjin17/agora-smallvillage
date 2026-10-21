"""신뢰도 시험 결과 요약: 회차별 유형·축별 비율, 같은 조건 두 회차의 문항 일치율과 축 글자 일치.

  python3 summarize.py <items.json> <results_dir> > summary.md
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path


def score(items, answers):
    axes = {}
    for ax in ("EI", "SN", "TF", "JP"):
        first, second = ax[0], ax[1]
        n = sum(1 for it in items if it["axis"] == ax and it[answers[it["id"]]]["pole"] == first)
        axes[ax] = n
    letters = "".join(ax[0] if axes[ax] >= 7 else ax[1] for ax in axes)
    return letters, axes


def main():
    items = json.load(open(sys.argv[1], encoding="utf-8"))["items"]
    runs = {}
    for p in sorted(Path(sys.argv[2]).glob("*.json")):
        runs[p.stem] = json.load(open(p, encoding="utf-8"))
    print("| 회차 | 조건 | seed | 모델 | 유형 | E | S | T | J | 「가」 고른 비율 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    scored = {}
    for name, r in runs.items():
        letters, axes = score(items, r["answers"])
        scored[name] = (letters, axes)
        a_rate = sum(1 for v in r["answers"].values() if v == "a") / len(items)
        print(f"| {name} | {r['condition']} | {r['seed']} | {','.join(r['model'])} | **{letters}** | "
              + " | ".join(f"{axes[ax]}/13" for ax in ("EI", "SN", "TF", "JP")) + f" | {a_rate:.0%} |")
    print()
    print("| 짝 | 문항 일치 | EI | SN | TF | JP | 유형 같음 |")
    print("|---|---|---|---|---|---|---|")
    groups = {}
    for n, r in runs.items():  # 같은 조건·같은 모델끼리 짝
        groups.setdefault((r["condition"], tuple(r["model"])), []).append(n)
    for names in groups.values():
        for x, y in itertools.combinations(names, 2):
            ax_agree = []
            for ax in ("EI", "SN", "TF", "JP"):
                ids = [it["id"] for it in items if it["axis"] == ax]
                same = sum(1 for i in ids if runs[x]["answers"][i] == runs[y]["answers"][i])
                ax_agree.append(f"{same}/13")
            total = sum(1 for it in items if runs[x]["answers"][it["id"]] == runs[y]["answers"][it["id"]])
            print(f"| {x} ↔ {y} | {total}/52 ({total/52:.0%}) | " + " | ".join(ax_agree)
                  + f" | {'예' if scored[x][0] == scored[y][0] else '아니오'} |")


if __name__ == "__main__":
    main()
