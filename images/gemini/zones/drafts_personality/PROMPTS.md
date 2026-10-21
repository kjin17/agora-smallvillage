# 갈림길 장소 시안 (2026-10-22, 미채택)

- 도구: Gemini 전용 크롬 웹 `/app`, 장마다 새 대화, 참고 이미지 없이 글로만 화풍을 적었다(`props/`·`zones/` 화풍 문구 재사용)
- 출력 1024×559 PNG 원본. 채택되면 `cut_sheet.py` 로 초록을 빼고 `zones/` 로 옮겨 PROMPTS.md 에 기록한다. 오른쪽 아래 반짝이는 Gemini 표식도 그때 지운다
- 설계: [docs/design/personality-place.md](../../../../docs/design/personality-place.md) 1절

| 파일 | 이름 후보 |
|---|---|
| a_crossroads.png | 갈림길 (추천) |
| b_mirror_spring.png | 거울샘 (2단계 「거울」 자리로도) |
| c_four_tiles_hall.png | 네 글자 정자 · 성격검사소 비교용 |

## a_crossroads

```
Create an image: one small building for a plaza game, drawn in EXACTLY this style: flat pastel cartoon illustration like a cozy mobile game prop, thin warm-brown outlines, isometric three-quarter top-down view, soft small drop shadow, cream / white marble / warm wood / terracotta roof tile palette, for a round Greek-style white marble plaza with terracotta-roofed colonnade. Solid pure green (#00FF00) background, the building centered with wide green margins. No text, no letters, no numbers, no labels, no characters, no people. The building: a small open-sided white marble pavilion with a terracotta tile roof, standing where a short cobblestone path splits into TWO paths (a fork). In front of it a wooden signpost with exactly two arrow boards pointing to the left path and the right path. Inside the pavilion a small marble lectern holding an open blank book. Two small potted plants.
```

## b_mirror_spring

```
Create an image: one small building for a plaza game, drawn in EXACTLY this style: flat pastel cartoon illustration like a cozy mobile game prop, thin warm-brown outlines, isometric three-quarter top-down view, soft small drop shadow, cream / white marble / warm wood / terracotta roof tile palette, for a round Greek-style white marble plaza with terracotta-roofed colonnade. Solid pure green (#00FF00) background, the building centered with wide green margins. No text, no letters, no numbers, no labels, no characters, no people. The building: a small round marble well-house (a tholos with six slim columns and a terracotta tile dome-like roof) sheltering a calm round reflecting pool of light-blue water; on one side a tall polished bronze hand-mirror shaped standing mirror on a marble pedestal, reflecting soft light. A low marble rim around the pool, a couple of stepping stones.
```

## c_four_tiles_hall

```
Create an image: one small building for a plaza game, drawn in EXACTLY this style: flat pastel cartoon illustration like a cozy mobile game prop, thin warm-brown outlines, isometric three-quarter top-down view, soft small drop shadow, cream / white marble / warm wood / terracotta roof tile palette, for a round Greek-style white marble plaza with terracotta-roofed colonnade. Solid pure green (#00FF00) background, the building centered with wide green margins. No text, no letters, no numbers, no labels, no characters, no people. The building: a tiny Greek temple-style hall with four white marble columns at the front and a terracotta tile roof; across the frieze above the columns are FOUR blank square cream plaques in a row (no letters on them). Two wide steps lead up to an open doorway, and in front of the steps stand two small wooden pedestals side by side, one with a small round blue token and one with a small round orange token (a choice between two). A small bunting of four pastel flags.
```
