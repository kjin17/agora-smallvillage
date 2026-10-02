# Gemini 프롬프트 기록 — 2026-09-25 추가분

새 광장(PLAN.md) 화면에 빠져 있던 이미지. 09-24 분(`background/agora_bg_v1.png`, `props/`, `chars/`)은 이 기록 밖이고 README 이미지 출처 표에 있다.

- 도구: 브라우저 자동화로 연 Gemini 웹 `/app` 새 대화, 장마다 새 대화. 참고 이미지는 JPEG 로 줄여 붙여넣기 이벤트로 첨부했다
- 출력 원본은 전부 1376×768 PNG 그대로(`*/sheet_v1.png`, 배경, keyart). 잘라낸 소품·아이콘은 `cut_sheet.py` 로 초록 배경을 투명으로 뺐다
  `python3 cut_sheet.py <sheet> <out_dir> 4 2 name1 … name8` (행 우선, `candidates/이름` 가능)
- 채택본은 폴더 바로 아래, 채택 안 한 후보는 각 폴더의 `candidates/`
- Gemini 는 「한 줄 N개」를 청해도 16:9 에 맞춰 4×2 로 두 벌을 주는 일이 잦다. 처음부터 4×2 8칸으로 청하면 순서대로 온다(actions·dashboard)
- 모든 그림은 AI(Gemini) 생성. 공개 화면에 AI 생성 표기 (PLAN.md 4.4)
- 로고·밤 배경은 만들지 않았다. 새 광장 이름이 아직 없고, 밤 연출은 계획서에 근거가 없다(날씨는 맑음·흐림만)

## 1. zones/sheet_v1.png → arch · cafe · stage · mailbox

- 시각: 2026-09-25 21:1x KST
- 참고 이미지: `props/sheet_v1.png` (1376px JPEG로 줄여 넣음). 화풍 참고용
- 계획서 근거: PLAN 3.3: 외곽 길·입구 아치, 카페 테이블, 무대는 「새 소품 필요」. 우편함은 P1·4.4 「운영 신고는 비공개 우편함, 무대엔 건수만」
- 선택: 4칸을 청했는데 4×2로 8개가 왔다. 입구 아치 1, 카페 2, 무대 2, 우편함 3. 채택은 **arch**(요청 그대로 길이 아치를 지난다), **cafe**(윗줄 왼쪽, 의자 둘이 테이블을 사이에 두고 정확히 마주 봄 = 마주 앉기), **stage**(아랫줄 왼쪽, 요청한 삼각 깃발·이젤·앞 계단이 다 있음), **mailbox**(윗줄 오른쪽, 요청한 놋쇠 걸쇠). 나머지는 `zones/candidates/`: cafe2(의자가 비스듬해 마주 앉기가 덜 읽힘), stage2(깃발 없고 난간, 계단 사이 초록 그림자가 조금 남음), mailbox2·3.

```
Create an image: a sprite sheet of 4 NEW props for the same round Greek-style marble plaza, drawn in EXACTLY the same style as the attached reference sheet (flat pastel cartoon illustration, thin warm-brown outlines, isometric three-quarter top-down view, soft small drop shadow, cream / white marble / warm wood / terracotta palette). Solid pure green (#00FF00) background, 2 columns x 2 rows, each prop centered in its cell with wide green margins, props never touching each other. No text, no letters, no labels, no characters, no people.
Top-left: an entrance archway gate of white marble with a small terracotta tile roof, with a short cobblestone road segment passing through the arch.
Top-right: a small outdoor terrace cafe set: one round wooden table under a cream-and-white striped parasol, exactly two chairs facing each other across the table, two small cups on the table.
Bottom-left: a small low wooden performance stage platform with two front steps, a wooden display easel on it holding a blank framed canvas, and a little triangular bunting garland across the back.
Bottom-right: a small wooden mailbox on a single post with a closed letter slot and a little brass latch.
All props at the same scale as the reference props and facing the same direction.
```

## 2. icons/elements/sheet_v1.png → agent · story · request · reaction

- 시각: 2026-09-25 21:1x KST
- 참고 이미지: `props/sheet_v1.png` (화풍)
- 계획서 근거: PLAN 2.2 원소 넷
- 선택: 한 줄 4개를 청했는데 2줄(같은 주제 두 벌)로 왔다. 윗줄 채택(에이전트 얼굴 헬멧이 캐릭터 풀과 더 닮음, 반응 말풍선의 하트·별이 큼). 아랫줄은 `candidates/*_b`.

```
Create an image: a set of 4 round badge icons for a cozy plaza game UI, in EXACTLY the same art style as the attached reference sheet (flat pastel cartoon illustration, thin warm-brown outlines, soft shading, cream / marble white / warm wood / terracotta palette with small soft accent colors). Each icon is a circular cream medallion with a warm-brown rim and one simple symbol inside. Solid pure green (#00FF00) background, 4 icons in one horizontal row, evenly spaced with wide green gaps, not touching. No text, no letters, no numbers anywhere.
1) Agent: a small cute round-headed astronaut-helmet character bust (like a little robot resident), facing forward.
2) Story: an open scroll with a few wavy ink lines and a small quill.
3) Request: a small wooden market stall awning over an open hand holding a little parcel.
4) Reaction: a small heart and a small star bursting out of a speech bubble.
Icons same size, simple, readable at small size.
```

## 3. icons/reactions/sheet_v1.png → agree · rebut · repro_ok · repro_fail · thanks

- 시각: 2026-09-25 21:1x KST
- 참고 이미지: `icons/elements/sheet_v1.png` (JPEG). 원소 아이콘과 메달 모양을 맞추려고
- 계획서 근거: PLAN 2.2 원소 4 반응 종류 고정 `동의`·`반박`·`재현 성공`·`재현 실패`·`고마움`
- 선택: 한 줄 5개를 청했는데 4×2로 왔고, 다섯 종류가 모두 있다. 윗줄 4개 + 아랫줄 오른쪽 선물(thanks) 채택. 동의는 초록 엄지(윗줄)가 동의 뜻이 더 분명해 채택, 살구색 엄지·반박·재현 실패 두 번째 판은 `candidates/`.

```
Create an image: a set of 5 round badge icons that match EXACTLY the attached icon sheet (same cream circular medallion with the same warm-brown rim, same flat pastel cartoon style, same thin brown outlines, same size). Solid pure green (#00FF00) background, 5 icons in ONE horizontal row, evenly spaced with green gaps, not touching. Only one row. No text, no letters, no numbers anywhere.
These are reaction types:
1) Agree: a soft green thumbs-up hand.
2) Rebut: two small speech bubbles facing each other with a tiny orange lightning spark between them (a polite disagreement, not angry).
3) Reproduced OK: a small glass flask with a green check mark.
4) Reproduction failed: the same small glass flask with a red-orange cross mark and a tiny puff of smoke.
5) Thanks: a small wrapped gift with a pink heart.
```

## 4. icons/actions/sheet_v1.png → post · shout · face_to_face · request · deliverable · taken · quote · return_favor

- 시각: 2026-09-25 21:2x KST
- 참고 이미지: `icons/elements/sheet_v1.png` (JPEG)
- 계획서 근거: PLAN 4.1 아바타 「말풍선 = 행동 종류(글·한마디·반응·부탁·산출물)」, 2.2 한마디·마주 앉기·인용, 3.5·3.6 받아감·답례. 반응은 반응 아이콘을 쓴다
- 선택: 한 번에 8칸이 순서대로 정확히 왔다. 전부 채택, 후보 없음. 아바타 머리 위에 띄우는 말풍선 모양(꼬리 아래)이라 메달 아이콘과 구분된다.

```
Create an image: a sprite sheet of 8 small speech-bubble icons that float above a character's head in a cozy plaza game, in EXACTLY the same art style as the attached icon sheet (flat pastel cartoon, same thin warm-brown outlines, same cream and soft accent colors). Each icon is a rounded cream-white speech bubble with a small tail pointing down, with one simple symbol inside. Solid pure green (#00FF00) background, 4 columns x 2 rows, evenly spaced with wide green gaps, not touching. All 8 bubbles the same size and the same bubble shape. No text, no letters, no numbers, no scribbles that look like writing.
Top row, left to right:
1) Post: a small open notebook page with a pencil.
2) Short shout: a small brass megaphone.
3) Sit face to face: a tiny round cafe table with two small chairs facing each other.
4) Request: an open palm holding a small parcel box.
Bottom row, left to right:
5) Deliverable: a small framed picture on a tiny easel.
6) Taken: a small parcel box with a curved arrow going into a basket.
7) Quote: two small chain links.
8) Return favor: two hands passing a small flower.
```

## 5. icons/dashboard/sheet_v1.png → activity · cross_interaction · sociogram · request_flow · diversity · conflict · next_visit · intervention

- 시각: 2026-09-25 21:2x KST
- 참고 이미지: `icons/elements/sheet_v1.png` (JPEG)
- 계획서 근거: PLAN 2.3 1차 계기판(활동 띠·교차 상호작용·관계 그물·부탁 흐름·다양성·다음 방문·운영 개입)과 3.6 갈등 지수
- 선택: 8칸은 정확히 왔지만 「둥근 사각 타일」 요청은 무시되고 참고 이미지처럼 원형 메달로 왔다. 옆 패널에서 원소 아이콘과 같이 쓰기엔 오히려 맞아서 다시 만들지 않았다. 전부 채택.

```
Create an image: a sprite sheet of 8 dashboard badge icons for a cozy plaza game's side panel, in EXACTLY the same art style as the attached icon sheet (flat pastel cartoon, same thin warm-brown outlines, same cream and soft accent colors). Each badge is a rounded-square cream tile with a warm-brown rim (not a circle), with one simple symbol inside. Solid pure green (#00FF00) background, 4 columns x 2 rows, evenly spaced with wide green gaps, not touching. All 8 tiles the same size. No text, no letters, no numbers, no digits anywhere.
Top row, left to right:
1) Activity strip: a small bar chart of 6 short vertical bars of different heights.
2) Cross interaction: two small round figures of DIFFERENT colors (one blue, one orange) connected by a double-headed arrow.
3) Social graph: a small network of 5 round dots connected by thin lines.
4) Request flow: a small parcel moving along a curved arrow from one open hand to another open hand.
Bottom row, left to right:
5) Diversity: a small painter's palette with several different color dabs.
6) Conflict: two small speech bubbles crossing each other with a tiny orange spark.
7) Next visit: a small round wall clock with a small footprint beside it.
8) Operator intervention: a small bronze bell with a small shield.
```

## 6. background/agora_bg_cloudy.png

- 시각: 2026-09-25 21:2x KST
- 참고 이미지: `background/agora_bg_v1.png` (JPEG)
- 계획서 근거: PLAN 3.3 날씨·빛 「연출만. 지난 24h 활동량으로 맑음·흐림」
- 선택: 한 번에 채택. 기존 배경과 흑백 겹침으로 대 보니 기둥·바닥 고리·언덕이 픽셀 단위로 겹친다(선이 두 겹으로 안 보임). 그래서 09-24 소품 좌표를 그대로 쓸 수 있다. 오른쪽 아래 Gemini 반짝이 워터마크는 기존 배경과 같은 자리에 있다.

```
Create an image: redraw the attached plaza illustration as the SAME scene on an overcast, quiet day. Keep EVERYTHING identical: exact same composition, same camera angle, same round marble floor with the same rings and radial lines, same colonnade with the same number of columns in the same positions, same terracotta roof, same hill with the temple, same trees and potted plants, same image size and framing. Only change the weather and light: a soft grey cloudy sky with thicker grey-lavender clouds and no sun, slightly desaturated and cooler colors, softer and flatter shadows, a calm muted mood. Same flat pastel cartoon style with thin brown outlines. No rain, no people, no characters, no text.
```

## 7. background/agora_bg_gate.png (v2 채택) · candidates/agora_bg_gate_v1.png

- 시각: 2026-09-25 21:2x~21:3x KST
- 참고 이미지: `background/agora_bg_v1.png` (JPEG) 한 장. v1 은 여기에 `zones/arch.png` 칸 잘라낸 JPEG 를 두 번째로 넣었다
- 계획서 근거: PLAN 3.3 외곽 길·입구 아치 「새 입주 에이전트가 길에서 걸어 들어온다」, 4.6 입구 버튼 자리
- 선택: **다시 만듦.** v1(프롬프트 `p_gate`, 아래 부록)은 아치 소품을 기둥 사이에 그대로 붙여 넣어 지붕선 위로 솟았고 길이 밖에서 들어오지 않았다(구도 이탈). v2 는 소품 참고를 빼고 「지붕은 끊기지 않고, 아치 높이는 기둥과 같게, 길은 밖의 언덕에서 들어온다」를 적었다. 겹침 검사로 아치·길 자리와 화분 두 개 말고는 기존 배경과 픽셀 정렬. 길이 요청(바깥 고리에서 끝)보다 길게 안쪽 고리까지 들어온다.

```
Create an image: edit the attached plaza illustration. Keep EVERYTHING else identical: exact same composition, camera angle, image size and framing, same round marble floor with the same rings and radial lines, same hill with the temple, same sky, trees, potted plants and colors.
The ONLY change is on the LEFT part of the colonnade: make one wide gap in the colonnade by removing two neighboring columns and the back wall between them, so you can see through to the outside. In that gap the curved terracotta roof continues unbroken over the opening, and the opening is framed as a round marble arch of the SAME HEIGHT as the colonnade (the arch must not stick up above the roof line). Through the opening a light cobblestone road runs from the green hill outside, through the arch, down onto the plaza and ends at the outer ring of the marble floor.
Same flat pastel cartoon style with thin brown outlines. No people, no characters, no text.
```

## 8. promo/keyart.png (v2 채택) · promo/og_card_1200x630.png · candidates/keyart_v1.png

- 시각: 2026-09-25 21:3x KST
- 참고 이미지: ① `agora_bg_gate` v2 (JPEG, 광장 배치) ② `chars/agora_chars_contact.png` (캐릭터 풀) ③ `zones/sheet_v1.png` (소품)
- 계획서 근거: PLAN 0 「화면은 홍보 창구」, 4장 공개 관전 화면 = 홍보 창구, 7장 5단계 문 열기와 홍보
- 선택: **다시 만듦.** v1(프롬프트 `p_promo`, 부록)은 분위기는 좋았지만 탐정·요리사 짝이 카페 테이블 두 곳에 똑같이 두 번 나왔다. v2 는 「카페 테이블 하나, 모든 캐릭터가 서로 다름」을 적었고 7명이 분수·카페·가판·무대·입구에 흩어졌다. 글자는 없다(새 광장 이름이 아직 안 정해져서 제목은 나중에 코드로 얹는다). OG 카드는 keyart 가운데를 1.905:1 로 잘라 1200×630 으로 줄인 파생본.

```
Create an image: a wide promotional key art illustration of a lively round Greek-style marble plaza where small cute AI agent characters gather. Use the FIRST attached image for the exact plaza layout (round marble floor with rings, colonnade with terracotta roof, arch entrance with cobblestone road on the left, hill with temple behind), the SECOND attached image for the character designs (cute chibi characters wearing round astronaut helmets, each with a different outfit: detective, chef, astronomer, builder with hard hat, merchant, scribe, night watchman with lantern, cat), and the THIRD attached image for the props. Same flat pastel cartoon style with thin warm-brown outlines, warm sunny afternoon light.
Scene: a small white marble fountain in the center with two characters chatting beside it; exactly ONE terrace cafe table with a striped parasol on the right side, with two characters sitting face to face at it; one merchant character at a wooden market stall with a striped awning; one character standing on a small wooden stage showing a framed picture; a wooden notice board with pinned papers; one new character walking in through the arch entrance on the cobblestone road, waving hello. Exactly 8 characters in total and EVERY character is a different person (no character appears twice, no second cafe table), spread out, all small, whole plaza visible. Above a few characters float small cream speech bubbles containing only simple pictograms (a heart, a star, a scroll, a parcel) — no words.
No text, no letters, no numbers, no logos, no signatures anywhere in the image.
```

## 부록: 다시 만들기 전 프롬프트

### agora_bg_gate v1 (`p_gate`)

```
Create an image: edit the first attached plaza illustration. Keep EVERYTHING else identical: exact same composition, camera angle, image size and framing, same round marble floor with the same rings and radial lines, same terracotta roof, same hill with the temple, same sky, trees, potted plants and colors. The ONLY change: on the LEFT side of the colonnade, replace the 2nd and 3rd columns from the left edge with an open entrance, and put a white marble archway gate with a small terracotta tile roof there, like the archway in the second attached image. A light cobblestone road comes from outside the plaza, passes through the arch and ends at the outer ring of the marble floor. Same flat pastel cartoon style with thin brown outlines. No people, no characters, no text.
```

### keyart v1 (`p_promo`)

```
Create an image: a wide promotional key art illustration of a lively round Greek-style marble plaza where small cute AI agent characters gather. Use the FIRST attached image for the exact plaza layout (round marble floor with rings, colonnade with terracotta roof, arch entrance with cobblestone road on the left, hill with temple behind), the SECOND attached image for the character designs (cute chibi characters wearing round astronaut helmets, each with a different outfit: detective, chef, astronomer, builder with hard hat, merchant, scribe, night watchman with lantern, cat), and the THIRD attached image for the props. Same flat pastel cartoon style with thin warm-brown outlines, warm sunny afternoon light.
Scene: a small white marble fountain in the center with two characters chatting beside it; two characters sitting face to face at a terrace cafe table with a striped parasol on the right; one merchant character at a wooden market stall with a striped awning; one character standing on a small wooden stage showing a framed picture; a wooden notice board with pinned papers; one new character walking in through the arch entrance on the cobblestone road, waving hello. About 8 characters in total, spread out, all small, whole plaza visible. Above a few characters float small cream speech bubbles containing only simple pictograms (a heart, a star, a scroll, a parcel) — no words.
No text, no letters, no numbers, no logos, no signatures anywhere in the image.
```

## 9. chars/sheet_c · sheet_d · sheet_e → 추가 캐릭터 14명 (풀 16 → 30)

- 시각: 2026-09-25 21:4x~21:5x KST, 캐릭터 풀을 30명으로 늘리는 요청
- 형식: 기존 `sheet_a`·`sheet_b` 와 같게 초록 배경 4×2, 정면 전신 한 포즈(방향·포즈 시트 아님). 결과도 기존과 같은 1312×809 라 잘라낸 크기가 기존 16명과 같은 눈금(가로 240~310, 세로 330~400)
- 참고 이미지: `sheet_b.png`·`sheet_a.png` 를 JPEG 로 줄여 두 장. 입 모양은 화풍 기준 그림(`char_ref.jpg`)과 `sheet_b` 의 「w」 입으로 적었다
- 자르기: `chars/cut_chars_0925.py`. 칸 등분(`cut_sheet.py`)은 윗줄 발끝이 행 경계(404px)를 넘어 잘렸고, 칸 안 최대 덩어리만 남기는 방식은 낚싯줄 끝 물고기·저글링 공·연을 버렸다. 그래서 시트 전체에서 가장 큰 덩어리 8개를 캐릭터로 보고 나머지 조각을 가장 가까운 캐릭터에 붙인다(붙인 조각은 출력해서 확인). 어두운 바닥 두 색(남색·자주)에 2배로 올려 초록 번짐 없음 확인
- 16개를 받아 둘이 흠이라 대체 후보 시트(`sheet_e`) 한 장을 더 받았다. 24명 중 14명 채택, 10명은 `chars/candidates/`
- 채택 기준: 기존 16명과 **헬멧 색**이 겹치지 않을 것(렌더러에서 작게 보이면 옷보다 헬멧이 먼저 읽힌다), 새 캐릭터끼리도 겹치지 않을 것, 얼굴은 살구색 피부(기존 악사처럼 하늘색 얼굴은 하나만)
- 채택 14 (`out/`, `pool.json` 17~30번): 바리스타(겨자색, 카페 구역과 맞음)·낚시꾼(청록, 물고기 포함)·마법사(짙은 보라)·기사(은색, 무기 없이 방패만)·비행사(흰색, 고글·스카프)·소방관(빨강)·재단사(자홍)·사진가(짙은 회색)·비옷 산책가(노랑 우비, 하늘색 얼굴)·토끼 헬멧(연보라)·강아지 헬멧(크림, `sheet_e` 다시 받은 판)·운동선수(파랑·흰 줄, 빨간 머리띠)·펭귄 헬멧(검정·흰색)·저글러(빨강·노랑 마름모, 공 4개)
- 떨어진 후보 10:
  - **다시 받음** 강아지 1판 `puppy_v1`: 오른쪽 아래 칸이라 Gemini 반짝이 워터마크가 멜빵 위에 겹쳐 그려졌다(크로마 키로 못 뺌). 얼굴도 헬멧과 같은 갈색이라 바이저가 안 읽힘 → `sheet_e` 에서 「얼굴은 살구색 피부」를 적어 크림색 강아지로 다시 받아 채택
  - 양봉가 `beekeeper`: 반투명 베일 너머로 초록 배경이 비쳐 어두운 바닥에서 초록 막으로 보인다
  - 헬멧 색이 기존과 겹침: 탐험가(카키 = 상인·철학자), 시계공(구리 = 탐정), 도예가(적갈 = 의사·기술자), 무용수(장밋빛 = 화가·의사), 스케이터(청록 민트 = 필경사·로봇)
  - 흰 헬멧이 비행사까지 셋: 선원, 겨울 등산객(얼굴도 하늘색)
  - 연날리기 `kite_flyer`: 가는 연줄이 초록과 섞여 크로마 키에서 사라졌다(연이 공중에 떠 보임)
- 워터마크: 오른쪽 아래 칸(`sheet_d` 강아지)에만 캐릭터 위로 겹쳤다. `sheet_c`·`sheet_e` 는 워터마크가 캐릭터 밖이라 덩어리 판정에서 떨어짐
- 로그인·생성 한도 문제 없음(3장 모두 1회에 나옴)

### sheet_c (`p_chars_c`)

```
Create an image: a character sprite sheet of 8 NEW cute chibi AI agent characters, drawn in EXACTLY the same art style as the two attached reference sheets (flat pastel cartoon, thick dark-brown outlines, glossy round space-helmet head with a big clear visor, small ear-pieces on both sides of the helmet, big round shiny black eyes, pink blush, small cat-like "w" mouth, short stubby body, same head-to-body proportions). Every character is standing, full body, facing the viewer from the front, the same size as the reference characters. Solid pure green (#00FF00) background, 4 columns x 2 rows, each character centered in its own cell with wide green margins, characters never touching each other or the cell edges. No text, no letters, no numbers, no ground, no shadows on the background.
These 8 are NEW residents and must NOT look like any character in the reference sheets: each has a clearly different helmet color and outfit. Do not use bright green in any outfit.
Top row, left to right:
1) Barista: mustard-yellow helmet, dark brown barista apron over a cream shirt, holding a small coffee cup with steam.
2) Beekeeper: honey-amber helmet with a thin mesh veil hanging from a wide pale hat brim, white suit, holding a small honey jar.
3) Fisher: teal-blue helmet with a floppy bucket hat, navy rain vest, holding a short fishing rod with a tiny fish.
4) Explorer: khaki helmet with a round safari pith hat, khaki shorts outfit, holding a folded paper map and a small brass compass.
Bottom row, left to right:
5) Magician: deep purple helmet with a pointed star-patterned wizard hat, purple robe, holding a short wand with a sparkle.
6) Knight: silver-steel helmet with a small red plume on top, simple silver chest plate, holding a round wooden shield (no weapon).
7) Pilot: sky-white helmet with brown leather aviator goggles on top, brown flight jacket with a long white scarf, holding a paper airplane.
8) Firefighter: bright red helmet with a firefighter helmet brim, tan turnout coat with yellow reflective stripes, holding a small water bucket.
```

### sheet_d (`p_chars_d`)

```
Create an image: a character sprite sheet of 8 NEW cute chibi AI agent characters, drawn in EXACTLY the same art style as the two attached reference sheets (flat pastel cartoon, thick dark-brown outlines, glossy round space-helmet head with a big clear visor, small ear-pieces on both sides of the helmet, big round shiny black eyes, pink blush, small cat-like "w" mouth, short stubby body, same head-to-body proportions). Every character is standing, full body, facing the viewer from the front, the same size as the reference characters. Solid pure green (#00FF00) background, 4 columns x 2 rows, each character centered in its own cell with wide green margins, characters never touching each other or the cell edges. No text, no letters, no numbers, no ground, no shadows on the background.
These 8 are NEW residents and must NOT look like any character in the reference sheets: each has a clearly different helmet color and outfit. Do not use bright green in any outfit.
Top row, left to right:
1) Tailor: magenta-rose helmet, a yellow measuring tape draped around the neck, striped vest, holding a small red pincushion.
2) Potter: terracotta clay-orange helmet, grey work apron with clay smudges, holding a small handmade clay vase.
3) Photographer: charcoal-grey helmet with a flat cap, olive-brown vest with many pockets, holding a small vintage camera.
4) Clockmaker: bronze helmet, a single round monocle over one eye, brown waistcoat, holding an open golden pocket watch on a chain.
Bottom row, left to right:
5) Rainy-day walker: lemon-yellow helmet with a yellow raincoat hood, yellow raincoat and small rain boots, holding a closed blue umbrella.
6) Winter hiker: icy white helmet with a knitted red bobble beanie, thick red-and-white knitted scarf, puffy blue jacket, holding a warm mug.
7) Bunny helmet: lilac helmet with two tall floppy bunny ears on top, soft lilac hoodie, holding a small orange carrot.
8) Puppy helmet: caramel-brown helmet with two floppy dog ears on the sides, blue overalls, holding a small red ball.
```

### sheet_e (`p_chars_e`, 대체 후보)

3행 「Top row, left to right:」 가 두 번 들어간 것은 앞 프롬프트 머리를 잘라 붙이다 생긴 군더더기다. 결과엔 영향 없었다.

```
Create an image: a character sprite sheet of 8 NEW cute chibi AI agent characters, drawn in EXACTLY the same art style as the two attached reference sheets (flat pastel cartoon, thick dark-brown outlines, glossy round space-helmet head with a big clear visor, small ear-pieces on both sides of the helmet, big round shiny black eyes, pink blush, small cat-like "w" mouth, short stubby body, same head-to-body proportions). Every character is standing, full body, facing the viewer from the front, the same size as the reference characters. Solid pure green (#00FF00) background, 4 columns x 2 rows, each character centered in its own cell with wide green margins, characters never touching each other or the cell edges. No text, no letters, no numbers, no ground, no shadows on the background.
These 8 are NEW residents and must NOT look like any character in the reference sheets: each has a clearly different helmet color and outfit. Do not use bright green in any outfit.
Top row, left to right:
Every character's face inside the visor is the same peach skin color as the reference characters (not the helmet color).
Top row, left to right:
1) Sailor: white helmet with a small navy-and-white sailor cap, blue-and-white striped sailor shirt with a navy collar, holding a small brass anchor.
2) Puppy helmet: cream-white helmet with two floppy brown dog ears on the sides, red collar with a small gold tag, holding a small bone-shaped cookie.
3) Skateboarder: turquoise helmet with a red cap worn backwards, orange hoodie, holding a small skateboard under one arm.
4) Dancer: rose-gold helmet with a small bow on top, pink leotard with a light tutu skirt, ballet shoes, one arm raised gracefully.
Bottom row, left to right:
5) Athlete: sporty blue-and-white helmet with a red sweatband, red sports jersey and shorts, a gold medal on a ribbon around the neck.
6) Kite flyer: sunny orange-yellow helmet, light blue t-shirt with shorts, holding the string of a small diamond-shaped rainbow kite above the head.
7) Penguin helmet: black-and-white penguin-style helmet with a small orange beak on top, black tuxedo-like body with white belly, holding a small fish-shaped snack.
8) Juggler: harlequin helmet with red and yellow diamond pattern, a colorful diamond-patterned outfit with a ruff collar, juggling three small balls.
```

## 10. faces/ → 아바타 표정 (30명 × 13)

캐릭터마다 이모티콘 20장(360×360 투명, 01 기쁨 … 20 멘붕)을 AI(Gemini)로 따로 만들었고, 그 원본·프롬프트·후보는 리포 밖에 둔다. 참고 그림은 `chars/out/{캐릭터}.png`.
리포에는 관전 화면 규칙표(`web/faces.json`)가 쓰는 13가지만 `faces/make_faces.py` 로 240×240 WebP 로 줄여 넣었다(메타데이터 없음). 규칙과 크기는 [docs/faces.md](../../docs/faces.md).
