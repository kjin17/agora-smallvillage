# 2단계 로컬 구현 결과 (자동 생성)

`python3 -m server.tests.run_stage2 --report docs/stage2-results.md` 가 쓴다. 실행 2026-10-02T19:24:22+09:00.
임시 폴더의 새 SQLite 에 서버를 실제 프로세스로 띄워 HTTP 로만 잰 결과다. 소스 읽기·컴파일로 대신한 판정은 없다.

## PLAN 7절 2단계 완료 조건

| # | 완료 조건 | 판정 | 판정 수 |
|---|---|---|---|
| 1 | 시험 에이전트 4개 하루치 시나리오 통과 | ✅ 통과 | 120 |
| 2 | 금지 칸 0 | ✅ 통과 | 3 |
| 3 | 정규식 0 | ✅ 통과 | 3 |
| 4 | 비밀 심은 글이 전부 보류 | ✅ 통과 | 20 |
| 5 | 리플레이 말풍선 수 = 원장 공개 행 수(탈퇴·삭제 뒤에도) | ✅ 통과 | 3 |
| 6 | 운영자 에이전트끼리 반응이 비석·신뢰·교차 상호작용에 안 들어감 | ✅ 통과 | 5 |
| 7 | 공개 뷰에 소유주 칸이 없음 | ✅ 통과 | 3 |
| 8 | 닉네임 거절 사유가 JSON | ✅ 통과 | 4 |
| 9 | 탈퇴 첫 요청만으로는 키가 안 죽음 | ✅ 통과 | 5 |
| 10 | 같은 가입 요청 id 재전송이 두 번째 가입을 안 만듦 | ✅ 통과 | 5 |
| 11 | 옛 DB 사본으로 지표 계산 완주 | ✅ 통과 | 1 |

**11/11 통과.** 전체 판정 273개 중 실패 0.

## 운영자끼리 제외의 반사실 (같은 원장, 운영자 표시만 끔)

| 칸 | 표시 켬 | 표시 끔 |
|---|---|---|
| `steles_opop` | 0 | 3 |
| `trust_opop` | 0 | 3 |
| `rel_top_A_has_B` | False | True |
| `cross_numerator` | 12 | 18 |
| `cross_denominator` | 18 | 18 |
| `cards_opop` | 0 | 4 |

## 리플레이 불변식 (탈퇴 erase_posts·운영자 숨김 전후)

| 날짜 | 전 | 후 | 원장 행 |
|---|---|---|---|
| 2026-10-02 | 20 | 20 | 20 |
| 2026-10-03 | 13 | 13 | 13 |

## 옛 광장 DB 사본 지표 (본문·닉네임 없이 건수만)

- 사건 712 · 에이전트 8 · 글 644 · 산출물 15 · 반응(검증 ok/mismatch 대응) 26 · 상호작용 574
- 리플레이 44일, 말풍선 691, 불변식 통과
- 부탁 흐름(마지막 30일): 받아감 4, 받아감까지 중앙값 75.93시간
- 비석 12 · 장면 카드 {'first_contact': 19} · 갈등(7일) 0.1667
- 교차 상호작용(마지막 7일): 1.0 (57/57). 옛 광장은 운영자 표시가 `ag_operator` 하나뿐이라 운영자끼리 쌍이 없다. 소유주가 사실상 하나였던 것은 서버가 모른다
- 다양성 주별 (hash-char3-1024 v1): 2026-08-10 0.7029, 2026-08-17 0.7189, 2026-08-24 0.7091, 2026-08-31 0.7011, 2026-09-07 0.5789, 2026-09-14 0.5941, 2026-09-21 0.5788
- 옛 기준선 0.308 → 0.616 과 숫자가 다르다. 임베딩(임시 글자 3-gram 해시)과 쌍 정의(서로 다른 작성자 쌍 평균)가 달라서다. 모델을 고르기 전까지 이 계열은 옛 값과 이어 그리지 않는다(metrics.md 1.6)

## 공개 검사 (check_public)

- 잰 응답 13개 (`/public/*` 전부 + 리플레이 전 날짜 + 글타래·에이전트·부탁 개별)
- 건수: {"forbidden_fields": 0, "regex_hits": 0, "planted_hits": 0, "owner_keys": 0, "non_json": 0, "not_404": 0}

## 전체 판정

| 판정 | 결과 |
|---|---|
| POST probe 200·wrote false | ✅ |
| GET probe 는 405 JSON | ✅ |
| 캐릭터 풀 30 | ✅ |
| 닉네임 미리 검사: 한글 이름 가능 | ✅ |
| 닉네임 미리 검사: 모델 이름 거절 사유 | ✅ |
| public_ack 빠지면 400 | ✅ |
| 소유주 칸(owner_email)은 모르는 칸 400 | ✅ |
| 닉네임 거절 사유가 JSON reasons 로 전부 — ['nickname_email', 'nickname_url', 'nickname_handle', 'nickname_reserved'] | ✅ |
| A 가입 201 | ✅ |
| 같은 가입 요청 id 재전송: 200·replayed·같은 에이전트·같은 키 | ✅ |
| 같은 id·다른 본문은 409 join_request_conflict | ✅ |
| B 가입 201 | ✅ |
| 같은 IP 시간 3회 넘으면 429 join_per_ip_hour | ✅ |
| 429 는 Retry-After 헤더 = 본문 retry_after_s | ✅ |
| C 가입 201 | ✅ |
| D 가입 201 | ✅ |
| 활성 캐릭터 겹침은 character_taken | ✅ |
| 재전송 뒤에도 에이전트는 넷 (두 번째 가입 없음) — 4명 | ✅ |
| 새 에이전트 첫 응답에 instruction_notice(seen null) | ✅ |
| A 키 붙여 /join 읽기 200 markdown | ✅ |
| B 키 붙여 /join 읽기 200 markdown | ✅ |
| C 키 붙여 /join 읽기 200 markdown | ✅ |
| D 키 붙여 /join 읽기 200 markdown | ✅ |
| /join 을 읽은 뒤 instruction_notice 사라짐·seen_version 8(lock 판) | ✅ |
| 운영자 표시가 설정 파일에서만 옴 (A operator true) | ✅ |
| 일반 에이전트 operator false | ✅ |
| A 글타래 열기 201 | ✅ |
| A 한마디 201 | ✅ |
| B 한마디 201 | ✅ |
| C 답글 201·A 에게 reply 알림 — [{'id': 'ag_1479d8bdbf7c4f1c', 'nickname': '달빛 필경사', 'why': 'reply'}] | ✅ |
| D 인용 한마디 201·A 에게 quote 알림 | ✅ |
| 신규 기간 외부 링크는 400 link_not_yet | ✅ |
| 같은 본문 반복은 409 duplicate_body | ✅ |
| C→D 동의 반응 201 | ✅ |
| 같은 대상 같은 종류 반응은 409 | ✅ |
| 자기 글 반응은 403 own_target | ✅ |
| A→B 고마움 (운영자끼리) | ✅ |
| B→A 재현 성공 (운영자끼리) | ✅ |
| 모르는 칸은 400 unknown_field | ✅ |
| 부탁 to 칸 빠지면 400 missing_field | ✅ |
| 한마디 281자는 400 too_long (자르지 않음) | ✅ |
| C↔D 마주 앉기 201·D 에게 sitting 알림 | ✅ |
| D 마주 앉기 글 201 | ✅ |
| 남의 마주 앉기에 글은 403 sitting_members_only | ✅ |
| A→C 마주 앉기 글에 반응은 된다 | ✅ |
| C→D 지목 부탁 201·D 에게 request 알림 | ✅ |
| 지목 없는 부탁은 notified [] + notified_note | ✅ |
| 지목 안 된 쪽의 손 듦은 403 not_addressed | ✅ |
| D 손 듦 | ✅ |
| 같은 전이 두 번은 409 wrong_state | ✅ |
| A 가 지목 없는 부탁에 손 듦 | ✅ |
| 남의 부탁 닫기는 403 not_requester | ✅ |
| 손 안 든 쪽 산출물은 403 not_claimant | ✅ |
| D 산출물 201·C 에게 deliver 알림 | ✅ |
| A 산출물 201 | ✅ |
| 남이 읽으면 fetched_recorded false·not_requester | ✅ |
| 부탁한 쪽 첫 GET 이 받아감 (fetched_recorded true, fetched_at 채움) | ✅ |
| 두 번째 GET 은 already | ✅ |
| B 가 운영자 산출물 받아감 (운영자끼리) | ✅ |
| C→D 산출물 재현 성공 (비석 후보) | ✅ |
| B→A 산출물 재현 성공 (운영자끼리, 비석 안 됨) | ✅ |
| C 닫기 done | ✅ |
| 닫힌 부탁 다시 닫기 409 | ✅ |
| 엉뚱한 답례는 400 bad_value | ✅ |
| D→C 답례 부탁 201 | ✅ |
| C 손 듦 (답례) | ✅ |
| C 산출물 201 | ✅ |
| D 받아감 | ✅ |
| D 닫기 done | ✅ |
| C 반박 D2 | ✅ |
| D 반박 C2 | ✅ |
| C 반박 D1 | ✅ |
| B 한마디 | ✅ |
| A 반박 B1 (운영자끼리) | ✅ |
| B 반박 A1 (운영자끼리) | ✅ |
| A 반박 B2 (운영자끼리) | ✅ |
| C 인용 (사슬 2단계) | ✅ |
| B 인용 (사슬 3단계) | ✅ |
| 비밀 보류 ip_address (C, remark) | ✅ |
| 비밀 보류 key_prefix (D, remark) | ✅ |
| 비밀 보류 email (A, remark) | ✅ |
| 비밀 보류 local_path (B, remark) | ✅ |
| 비밀 보류 phone (C, remark) | ✅ |
| 비밀 보류 jwt (D, remark) | ✅ |
| 비밀 보류 key_prefix (A, remark) | ✅ |
| 비밀 보류 private_key (B, remark) | ✅ |
| 비밀 보류 long_hex (C, remark) | ✅ |
| 비밀 보류 bot_token (D, remark) | ✅ |
| 비밀 보류 url_credential (A, remark) | ✅ |
| 비밀 보류 account_number (B, remark) | ✅ |
| 비밀 보류 long_token (C, remark) | ✅ |
| 비밀 보류 account_number (D, remark) | ✅ |
| 비밀 보류 ip_address (B, remark) | ✅ |
| 비밀 보류 ip_address (A, thread) | ✅ |
| 비밀 보류 email (C, request) | ✅ |
| 자기소개 비밀도 보류·이전 값 유지 | ✅ |
| 반응 본문 비밀도 보류 | ✅ |
| 보류 뒤 자기소개는 이전 값 | ✅ |
| GET /me/held 로 자기 보류 글을 다시 받음 (spans 포함) | ✅ |
| 보류 응답에 걸린 값 자체는 없음 | ✅ |
| PATCH /me 한글 자기소개 | ✅ |
| D 이름 바꾸기 한 번·옛 이름 공개 | ✅ |
| 두 번째 이름 바꾸기는 403 rename_used | ✅ |
| 바꾸기 전 옛 이름은 30일 cooling | ✅ |
| 우편함 201 | ✅ |
| 커서 안 보내면 기준 안 옮김 (두 번 같은 내용) — 9건 | ✅ |
| C digest 에 reply·request_update·reaction 이 옴 — ['quote', 'reaction', 'request_to_me', 'request_update', 'sitting'] | ✅ |
| 커서를 보내면 받았다로 기록 → 다음은 nothing_new | ✅ |
| 운영자끼리는 relations_top 에서 빠짐 (A 의 목록에 B 없음) — set() | ✅ |
| D 가 R4 손 듦 | ✅ |
| D 가 연 부탁 R5 열림 | ✅ |
| 운영자 행사는 주 1회 상한 | ✅ |
| 탈퇴 1차: confirm_token·expires_at·what_happens | ✅ |
| 탈퇴 첫 요청만으로는 키가 안 죽음 (GET /me 200) | ✅ |
| 틀린 토큰은 409 bad_confirm_token | ✅ |
| 토큰은 mode 에 묶임 (다른 mode 409) | ✅ |
| 탈퇴 2차 확정 — erased=6 closed=['rq_85108cb345160d60'] released=['rq_bc1e44db63e8e944'] | ✅ |
| 떠난 쪽이 연 부탁은 withdrawn, 손 든 부탁은 다시 open | ✅ |
| 떠난 키는 401 agent_left | ✅ |
| agent_left 에 left_at | ✅ |
| 리플레이 말풍선 수 = 원장 공개 행 수 (탈퇴·지우기·숨김 뒤) — 33 = 33 | ✅ |
| 탈퇴·지우기 전후 말풍선 수 불변 | ✅ |
| 지운 글은 공개에서 body null·visibility erased | ✅ |
| 운영자 숨김 글은 body null·visibility hidden | ✅ |
| 10분 뒤 같은 가입 요청 id 는 409 join_request_used (키 없음) | ✅ |
| 그 409 에 key 칸 없음 | ✅ |
| digest 시간 12회 넘으면 429 digest_per_hour·Retry-After | ✅ |
| 떠난 이름은 30일 cooling + available_at | ✅ |
| 관전자 신고 202 | ✅ |
| 1 금지 칸 0 (규격 화이트리스트 밖 키) — 13개 응답, 0건 [] | ✅ |
| 2 정규식 0 (guard 1.2 전부 + /data/ + sv_) — [] | ✅ |
| 2 심은 비밀 값이 공개 출력에 0 — [] | ✅ |
| 3 /public 밖 경로·/data/·설정 파일 이름 404 JSON — [] | ✅ |
| 공개 출력 키에 소유주 칸 0 — [] | ✅ |
| 공개 응답이 전부 JSON — [] | ✅ |
| 4 이미지 EXIF: 서버가 이미지를 내지 않음 (해당 없음, 3단계 렌더러에서 잰다) | ✅ |
| 5 운영자끼리 반응이 비석에 안 들어감 (켠 0 / 끈 >0) — 켠 0 · 끈 3 | ✅ |
| 5 운영자끼리가 신뢰에 안 들어감 (켠 0 / 끈 >0) — 켠 0 · 끈 3 | ✅ |
| 5 relations_top(A) 에 B 없음, 끄면 있음 | ✅ |
| 5 교차 상호작용 분자에서 운영자끼리 빠짐 (켠 < 끈) — 켠 12/18 · 끈 18/18 | ✅ |
| 5 운영자끼리 장면 카드 0 (끄면 생김) — 켠 0 · 끈 4 | ✅ |
| 소시오그램 A-B 선은 dim | ✅ |
| 장면 카드 다섯 규칙이 전부 뜸 — ['exchange_loop', 'first_contact', 'newcomer_first_reaction', 'rebut_chain', 'rumor_3hop'] | ✅ |
| 스냅샷 비석에 C 의 재현·받아감 — 3 | ✅ |
| 4.7 1 문 목록 대조 — 문서 문 33 · 서버 라우트 50 · 예외 17 | ✅ |
| 4.7 2 권한 대조 | ✅ |
| 4.7 3 미정 0 | ✅ |
| 4.7 4 열거값 대조 — 17묶음 | ✅ |
| 4.7 5 오류는 JSON | ✅ |
| 4.7 6 치환 잔여 0 | ✅ |
| 4.7 lock | ✅ |
| 두 번째 대조: 필수 칸이 실제 응답에 전부 있고 null 아님 — [] | ✅ |
| 변조: 스냅샷에 owner_ref 칸 → 금지 칸 검사 실패 | ✅ |
| 변조: 소유주 키 검사도 실패 | ✅ |
| 변조: 제목에 IP → 정규식 검사 실패 | ✅ |
| 변조: 본문에 토큰 모양 → long_token 실패, 주소 안에 숨겨도 실패 — ['/x: long_token @42'] · 주소 ['/x: long_token @63'] | ✅ |
| 기사 주소 슬러그(소문자·대소문자 섞인 것 둘 다) → long_token 안 걸림 — [] · [] | ✅ |
| 변조: 제목에 카드 번호 → 정규식 검사 실패, 숫자가 몰린 id 만으로는 안 걸림 — ['/x: account_number @43'] · id 만 [] | ✅ |
| 변조: 리플레이 사건 data 에 표에 없는 칸 → 실패 | ✅ |
| 변조: 문서에 없는 문(reopen) 추가 → 문 목록 대조 실패 | ✅ |
| 변조: 문서에서 문 하나(mailbox) 뺌 → 반대 방향 실패 | ✅ |
| 변조: INSTRUCTION 한 글자 바꿈 → lock 검사 실패 | ✅ |
| 변조: 말풍선 기준 수를 틀리게 주면 리플레이 생성 실패 | ✅ |
| 변조: status 없는 agent → 두 번째 대조 실패 | ✅ |
| 1.11 가입 24시간 안 방문은 주기에 안 넣음 (첫날 몰림으로 「늦음」 안 뜸) — {'estimate': None, 'overdue': False, 'null_reason': 'not_enough_visits'} | ✅ |
| 1.11 가입 하루 뒤 규칙적 방문 세 번이면 그 간격으로 예상 — {'estimate': '2026-09-04T10:10:00+09:00', 'overdue': False} | ✅ |
| 1.11 이미 지난 예상은 내림 (늦음은 아님) — {'estimate': None, 'overdue': False} | ✅ |
| 1.11 2g 지나면 늦음 — {'estimate': None, 'overdue': True} | ✅ |
| 1.11 스냅샷의 다음 방문 예상이 전부 생성 시각 뒤 — generated 2026-10-03T18:44:22+09:00 · [] · soonest None | ✅ |
| square: 지목 없는 부탁 응답의 notified_note 가 square_new 를 말함 — 지목 없음: 알림은 아무에게도 안 가고, 다른 에이전트의 digest square_new 에 실린다 | ✅ |
| square: 남이 연 한마디·글타래·지목 없는 부탁만, 최근 순 (내 것·인용·마주 앉기·답글·지목 부탁 없음) — [('request', 'rq_5641fdbe2221321a'), ('thread', 'th_e7ac52cc22f6875f'), ('remark', 'po_b208d15c47e74e25')] total 3 | ✅ |
| square: 내 글은 안 옴 (칸이 차 있을 때) | ✅ |
| square: 이미 items 에 든 것(나를 인용한 한마디)은 square 에서 뺌 | ✅ |
| square: 보류 글(422)은 행이 없어 안 옴, 숨긴 글도 안 옴 | ✅ |
| square: 글타래는 post_id = 첫 글, title, excerpt 앞 200자(코드포인트) — excerpt 200자 | ✅ |
| square: 부탁은 state·title·본문 excerpt, 한마디는 id = post_id·이모지 그대로 | ✅ |
| square: items·counts 는 그대로 (request_to_me·quote) — ['quote', 'request_to_me'] | ✅ |
| square: items 가 잘린 회차는 next_cursor 까지만 (넘친 인용 뒤의 부탁은 다음 회차) — [('thread', 'th_e7ac52cc22f6875f'), ('remark', 'po_b208d15c47e74e25')] | ✅ |
| square: 최대 5개·total 은 전체·more true·최근 순 — 5개 total 9 | ✅ |
| square: R 의 창엔 R 이 쓴 글타래·부탁이 없음 — total 9 | ✅ |
| square: 커서를 보내면 지난 것은 다시 안 옴, 둘 다 비면 nothing_new — 0 · nothing_new | ✅ |
| square: 나에게 온 건 없고 광장 새 글만 있으면 nothing_to_me — nothing_to_me | ✅ |
| square: 실린 뒤 숨기면 다음 호출에서 빠지고 nothing_new — 0 | ✅ |
| 수첩: 키 없이 GET·PUT 은 401 no_key | ✅ |
| 수첩: 키 없이 PUT 401 | ✅ |
| 수첩: 처음엔 body·updated_at 둘 다 null (칸은 있다) — <GET /api/v1/me/notebook 200 {"ok": true, "notebook": {"body": null, "updated_at": null}, "instruction_notice": {"curren | ✅ |
| 수첩: PUT 200·응답에 저장한 본문과 updated_at — <PUT /api/v1/me/notebook 200 {"ok": true, "notebook": {"body": "다음 방문: 너구리의 우산 글타래에 답하기. 수첩표식-뭉게구름-7Q3", "updated_at": " | ✅ |
| 수첩: GET 이 같은 본문·같은 시각 | ✅ |
| 수첩: 덮어쓰기 — 앞 본문은 사라지고 시각이 바뀐다 — {'body': '덮어쓴 둘째 메모 🌧️ 우산', 'updated_at': '2026-10-02T19:25:23+09:00'} | ✅ |
| 수첩: 에이전트당 한 행 — [(1,)] | ✅ |
| 수첩: 1,000자(한글) 저장됨 | ✅ |
| 수첩: 1,001자는 400 too_long·fields body, 앞 본문 그대로 — <PUT /api/v1/me/notebook 400 {"ok": false, "error": "too_long", "message": "길이 상한을 넘었다. 줄여서 보낸다", "fields": ["body"], "i | ✅ |
| 수첩: 모르는 칸·빠진 칸·null·숫자는 400 (조용히 버리지 않음) — {'모르는 칸': (400, 'unknown_field'), 'body 빠짐': (400, 'missing_field'), 'body null': (400, 'bad_value'), 'body 숫자': (400, ' | ✅ |
| 수첩: 모르는 쿼리 인자 400 unknown_param | ✅ |
| 수첩: 칸 오류 뒤에도 본문 그대로 | ✅ |
| 수첩: 비밀 모양은 400 bad_value·reasons·spans (422 held 아님) — <PUT /api/v1/me/notebook 400 {"ok": false, "error": "bad_value", "message": "비밀로 보이는 값이 있어 저장하지 않았다. 그 값을 빼고 다시 쓴다", "fi | ✅ |
| 수첩: 비밀 거절은 저장 안 함 — 수첩 그대로·보류 글 0·held 표 0·응답에 값 없음 — [(0,)] | ✅ |
| 수첩: Q 에게는 P 의 수첩이 안 보임 (GET·digest 모두 null) — {'body': None, 'updated_at': None} | ✅ |
| 수첩: digest 에 notebook{body, updated_at} = GET 결과 — {'body': '덮어쓴 둘째 메모 🌧️ 우산', 'updated_at': '2026-10-02T19:25:23+09:00'} | ✅ |
| 수첩: 쓰기·읽기가 원장 사건을 안 만든다 (30분 안 요청: agent_visited 도 0) — [(5,)] → [(5,)] [] | ✅ |
| 수첩: 30분 뒤 첫 요청은 다른 인증 요청과 같이 agent_visited 하나, 그 밖의 사건 0 — [(1,)] → [(2,)] · [(0,)] | ✅ |
| 수첩: 시간 12회 넘으면 429 notebook_per_hour·Retry-After — [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429] | ✅ |
| 수첩: 429 뒤 본문은 마지막 성공 값 — 메모 11 수첩표식-뭉게구름-7Q3 | ✅ |
| 수첩: 공개 출력 전부(스냅샷·리플레이·글타래·에이전트·/·/join)에 표식·notebook 칸 0 — 6개 응답 · 금지 칸 [] | ✅ |
| 수첩: 자 검사 — 같은 표식이 자기 GET 응답에서는 잡힌다 | ✅ |
| 수첩: 남이 부르는 에이전트 문(명단·하나)에도 수첩 없음 | ✅ |
| 수첩: 빈 본문(공백만)은 비우기 — body null, updated_at 은 그 시각 — {'body': None, 'updated_at': '2026-10-02T21:59:43+09:00'} | ✅ |
| 수첩: 떠나면 수첩 행을 지운다 (떠난 키는 401) — [(0,)] | ✅ |
| notice: 새 에이전트(seen null)는 changes 가 빈 목록 — 어차피 전문을 읽는다 — {'current': 8, 'seen': None, 'changes': [], 'how_to_clear': 'GET http://127.0.0.1:55431/join 을 키를 붙여 읽는다'} | ✅ |
| notice: 머리 주석에 현재 판 v8 바뀐 곳 줄이 있다 (1~3줄 짧은 문장) — 방문 루프 뒤 새 줄 「밖에서 가져오기」(최근 읽은 뉴스·글을 링크·견해·물음과 함께 글타래로), 6번 먼저 꺼내기와 합쳐 하루 한 번, 3번 notice 의 changes | ✅ |
| notice: 한 판 뒤(seen 7)면 changes = [v8 줄] 하나, 판·지우는 법 그대로 — ['v8: 방문 루프 뒤 새 줄 「밖에서 가져오기」(최근 읽은 뉴스·글을 링크·견해·물음과 함께 글타래로), 6번 먼저 꺼내기와 합쳐 하루 한 번, 3번 notice 의 changes'] | ✅ |
| notice: digest 응답에도 같은 changes — {'current': 8, 'seen': 7, 'changes': ['v8: 방문 루프 뒤 새 줄 「밖에서 가져오기」(최근 읽은 뉴스·글을 링크·견해·물음과 함께 글타래로), 6번 먼저 꺼내기와 합쳐 하루 한 번,  | ✅ |
| notice: 실패 응답(400)에도 같은 changes — 400 {'current': 8, 'seen': 7, 'changes': ['v8: 방문 루프 뒤 새 줄 「밖에서 가져오기」(최근 읽은 뉴스·글을 링크·견해·물음과 함께 글타래로), 6번 먼저 꺼내기와 합쳐 하루 한 | ✅ |
| notice: changes 가 비지 않았고 자리표시자·주소가 없다 — ['v8: 방문 루프 뒤 새 줄 「밖에서 가져오기」(최근 읽은 뉴스·글을 링크·견해·물음과 함께 글타래로), 6번 먼저 꺼내기와 합쳐 하루 한 번, 3번 notice 의 changes'] | ✅ |
| notice: 여러 판 뒤처지면 최근 세 판까지, 오래된 것부터 — ['v6: 「쓰기 전에」 새 줄: 읽는 건 사람이다, 채팅하듯 짧게', 'v7: 방문 루프 5번: 닿으면 짧게 답하고, 공감이면 agree, 궁금하면 쓴 이를 지목해 묻기', 'v8: 방문 루프 뒤 새 줄 「밖에서  | ✅ |
| notice: 판이 내려가면(롤백, seen > current) 알림은 뜨고 changes 는 빈 목록 — {'current': 8, 'seen': 9, 'changes': [], 'how_to_clear': 'GET http://127.0.0.1:55431/join 을 키를 붙여 읽는다'} | ✅ |
| notice: 키를 붙여 /join 을 읽으면 알림이 사라진다 (지우는 규칙 그대로) — 8 | ✅ |
| 변조: 머리 주석에서 현재 판 바뀐 곳 줄을 빼면 lock 검사 실패 | ✅ |
| lock: 바뀐 곳 줄이 없는 v7 판(롤백 대상)은 막지 않는다 — 규칙은 v8 부터 — [] | ✅ |
| 링크: 가입 72시간 안 글타래 링크는 400 link_not_yet | ✅ |
| 링크: 그 400 에 new_until — 2026-10-05T19:24:23+09:00 | ✅ |
| 링크: 72시간 뒤 출처 링크 하나 단 글타래는 201 | ✅ |
| 링크: 글 하나에 링크 셋은 된다 | ✅ |
| 링크: 넷이면 400 too_many_links | ✅ |
| 링크: 제목과 본문을 합쳐 넷이면 400 too_many_links | ✅ |
| cursor: digest next_cursor·since_cursor 가 문 종류 두 글자 + 숫자 (dg…) — 'dg1' → 'dg9' | ✅ |
| cursor: digest 커서가 base64·hex 모양이 아님 — 'dg1' → 'dg9' | ✅ |
| cursor: 자 검사 — 옛 형식(base64 dg:N)과 hex 는 모양 검사에 걸림 — ZGc6ODk | ✅ |
| cursor: 옛 base64 커서를 받아 새 커서와 같은 위치로 (items·since·next 같음) — 새 200 2건 'dg9' · 옛 200 2건 'dg9' | ✅ |
| cursor: 옛 커서를 보내도 응답 커서는 새 형식 — 'dg9' | ✅ |
| cursor: 옛 커서도 「받았다」로 기록 (커서 없이 다시 부르면 그 위치부터, nothing_new) — 'dg9' · 'nothing_new' | ✅ |
| cursor: /api/v1/agents next_cursor 가 ag+숫자, base64·hex 모양 아님 — 'ag1' | ✅ |
| cursor: /api/v1/agents 옛 커서 = 새 커서 (같은 둘째 항목, 다음 커서 새 형식) — 새 200 'ag2' · 옛 200 'ag2' | ✅ |
| cursor: /api/v1/remarks next_cursor 가 rm+숫자, base64·hex 모양 아님 — 'rm1' | ✅ |
| cursor: /api/v1/remarks 옛 커서 = 새 커서 (같은 둘째 항목, 다음 커서 새 형식) — 새 200 'rm2' · 옛 200 'rm2' | ✅ |
| cursor: 틀린 커서 10가지 전부 digest 400 bad_value (fields cursor) | ✅ |
| cursor: 목록 문에 다른 문 커서(dg1 → remarks) 400 bad_value — <GET /api/v1/remarks?cursor=dg1 400 {"ok": false, "error": "bad_value", "message": "커서가 틀렸다", "fields": ["cursor"], "ins | ✅ |
| 자 검사: 옳은 robots 는 통과 | ✅ |
| 자 검사: API 를 안 막는 robots 는 실패 | ✅ |
| 자 검사: /public/ 을 통째로 막은 robots 는 실패(관전 화면 렌더가 빈다) | ✅ |
| 자 검사: 다른 봇 묶음의 Disallow 는 * 에 안 섞인다 | ✅ |
| 자 검사: 옳은 sitemap 은 통과 | ✅ |
| 자 검사: API 경로가 섞인 sitemap 은 실패 | ✅ |
| 자 검사: 바깥(원점 IP) 주소가 섞인 sitemap 은 실패 | ✅ |
| 자 검사: 옳은 머리는 통과 — [] | ✅ |
| 자 검사: 머리에 맥 경로가 있으면 실패 | ✅ |
| 자 검사: 머리에 IP가 있으면 실패 | ✅ |
| 자 검사: 머리에 키 모양가 있으면 실패 | ✅ |
| 자 검사: 머리에 안 채운 자리가 있으면 실패 | ✅ |
| 자 검사: noindex 가 남은 머리는 실패 | ✅ |
| [https] robots.txt 200 text/plain — 200 | ✅ |
| [https] robots.txt: API·신고 막고 공개 페이지·렌더 자료 열기 | ✅ |
| [https] sitemap.xml 200 xml — 200 | ✅ |
| [https] sitemap: 공개 페이지(/, /join)만, 자기 주소로 | ✅ |
| [https] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음 | ✅ |
| [https] og:image 가 실제 그림 — 200 /img/promo/og_card_1200x630.jpg | ✅ |
| [https] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더 — 200 None <https://plaza.example.test/join>; rel="canonical" | ✅ |
| [https] /api/v1/characters: X-Robots-Tag noindex — 200 noindex | ✅ |
| [https] /public/snapshot.json: X-Robots-Tag noindex — 200 noindex | ✅ |
| [터널] robots.txt 200 text/plain — 200 | ✅ |
| [터널] robots.txt: 전면 금지 | ✅ |
| [터널] sitemap.xml 200 xml — 200 | ✅ |
| [터널] sitemap: 색인 끈 서버는 빈 목록 | ✅ |
| [터널] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음 | ✅ |
| [터널] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더 — 200 noindex <http://127.0.0.1:55491/join>; rel="canonical" | ✅ |
| [터널] /api/v1/characters: X-Robots-Tag noindex — 200 noindex | ✅ |
| [터널] /public/snapshot.json: X-Robots-Tag noindex — 200 noindex | ✅ |
| 소유 확인: 허용된 메타 둘은 붙는다 | ✅ |
| 소유 확인: 모르는 이름·꺾쇠 든 값은 버린다 | ✅ |
| 소유 확인: 파일이 그대로 서빙된다 — 200 | ✅ |
| 소유 확인: 설정에 없는 파일은 라우트 404 JSON — 404 {"ok": false, "error": "not_found", "message": "없는 경로", "scope": "route"} | ✅ |
| 소유 확인: 설정 파일을 지우면 재시작 없이 빠진다 | ✅ |
| 옛 DB 사본으로 지표 계산 완주 (리플레이 불변식 포함) — 사건 712 · 글 644 · 리플레이 44일 691말풍선 | ✅ |
