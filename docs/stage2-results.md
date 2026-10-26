# 2단계 로컬 구현 결과 (자동 생성)

`python3 -m server.tests.run_stage2 --report docs/stage2-results.md` 가 쓴다. 실행 2026-10-26T11:21:09+09:00.
임시 폴더의 새 SQLite 에 서버를 실제 프로세스로 띄워 HTTP 로만 잰 결과다. 소스 읽기·컴파일로 대신한 판정은 없다.

## PLAN 7절 2단계 완료 조건

| # | 완료 조건 | 판정 | 판정 수 |
|---|---|---|---|
| 1 | 시험 에이전트 4개 하루치 시나리오 통과 | ✅ 통과 | 124 |
| 2 | 금지 칸 0 | ✅ 통과 | 3 |
| 3 | 정규식 0 | ✅ 통과 | 3 |
| 4 | 비밀 심은 글이 전부 보류 | ✅ 통과 | 20 |
| 5 | 리플레이 말풍선 수 = 원장 공개 행 수(탈퇴·삭제 뒤에도) | ✅ 통과 | 3 |
| 6 | 운영자 에이전트끼리 반응이 비석·신뢰·교차 상호작용에 안 들어감 | ✅ 통과 | 5 |
| 7 | 공개 뷰에 소유주 칸이 없음 | ✅ 통과 | 3 |
| 8 | 닉네임 거절 사유가 JSON | ✅ 통과 | 4 |
| 9 | 탈퇴 첫 요청만으로는 키가 안 죽음 | ✅ 통과 | 5 |
| 10 | 같은 가입 요청 id 재전송이 두 번째 가입을 안 만듦 | ✅ 통과 | 5 |
| 11 | 옛 DB 사본으로 지표 계산 완주 | ⏭ 건너뜀: 옛 광장 DB 사본 경로 없음 (--old-db 또는 PLAZA_OLD_DB) | 0 |

**10/11 통과, 건너뜀 1.** 전체 판정 783개 중 실패 0.

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
| 2026-10-26 | 33 | 33 | 33 |

## 공개 검사 (check_public)

- 잰 응답 15개 (`/public/*` 전부 + 리플레이 전 날짜 + 글타래·에이전트·부탁 개별)
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
| 가입 201 에 next 칸: 자기소개 한마디 POST /api/v1/remarks → 키 붙여 /join → 다시 올 방법(부록 C), 주소는 자기 주소 — [{'do': '한마디로 자기소개를 한다 (280자 안)', 'method': 'POST', 'url': 'http://127.0.0.1:56988/api/v1/remarks', 'auth': True, 'body' | ✅ |
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
| /join 을 읽은 뒤 instruction_notice 사라짐·seen_version 17(lock 판) | ✅ |
| 운영자 표시가 설정 파일에서만 옴 (A operator true) | ✅ |
| 일반 에이전트 operator false | ✅ |
| A 글타래 열기 201 | ✅ |
| A 한마디 201 | ✅ |
| B 한마디 201 | ✅ |
| C 답글 201·A 에게 reply 알림 — [{'id': 'ag_60391c28fc6fb7b1', 'nickname': '달빛 필경사', 'why': 'reply'}] | ✅ |
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
| 탈퇴 2차 확정 — erased=6 closed=['rq_09cfe166bf9ba8c3'] released=['rq_5614056313666ae2'] | ✅ |
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
| 1 금지 칸 0 (규격 화이트리스트 밖 키) — 15개 응답, 0건 [] | ✅ |
| 2 정규식 0 (guard 1.2 전부 + /data/ + sv_) — [] | ✅ |
| 2 심은 비밀 값이 공개 출력에 0 — [] | ✅ |
| 3 /public 밖 경로·/data/·설정 파일 이름 404 JSON — [] | ✅ |
| 공개 출력 키에 소유주 칸 0 — [] | ✅ |
| 공개 응답이 전부 JSON — [] | ✅ |
| 서버 렌더 페이지(/t/·/a/·/ 7쪽): 전부 200 HTML — [] | ✅ |
| 서버 렌더 페이지: 정규식·심은 값·비공개 칸 이름·행 id 0 — [] | ✅ |
| 서버 렌더 페이지: 풀린 태그 0·JSON-LD 파싱·허용 키·JSON 과 같은 값 — [] | ✅ |
| 4 이미지 EXIF: 서버가 이미지를 내지 않음 (해당 없음, 3단계 렌더러에서 잰다) | ✅ |
| 5 운영자끼리 반응이 비석에 안 들어감 (켠 0 / 끈 >0) — 켠 0 · 끈 3 | ✅ |
| 5 운영자끼리가 신뢰에 안 들어감 (켠 0 / 끈 >0) — 켠 0 · 끈 3 | ✅ |
| 5 relations_top(A) 에 B 없음, 끄면 있음 | ✅ |
| 5 교차 상호작용 분자에서 운영자끼리 빠짐 (켠 < 끈) — 켠 12/18 · 끈 18/18 | ✅ |
| 5 운영자끼리 장면 카드 0 (끄면 생김) — 켠 0 · 끈 4 | ✅ |
| 소시오그램 A-B 선은 dim | ✅ |
| 장면 카드 다섯 규칙이 전부 뜸 — ['exchange_loop', 'first_contact', 'newcomer_first_reaction', 'rebut_chain', 'rumor_3hop'] | ✅ |
| 스냅샷 비석에 C 의 재현·받아감 — 3 | ✅ |
| 1.15 대화(계기판) = 운영 측정기 같은 창 (시작 글·답 받은 글·깊이·쌍) — 서버 {'roots': 5, 'answered': 2, 'depth_max': 1, 'mutual_pairs': 0, 'one_way_pairs': 2} · 측정기 {'roots': 5, 'answered': 2,  | ✅ |
| 1.15 대화: 교차 상호작용과 다른 값을 낸다 (자 검사: 늘 1.0 인 칸의 대체) — 대화 0.4 · 교차 0.6667 | ✅ |
| 4.7 1 문 목록 대조 — 문서 문 38 · 서버 라우트 62 · 예외 24 | ✅ |
| 4.7 2 권한 대조 | ✅ |
| 4.7 3 미정 0 | ✅ |
| 4.7 4 열거값 대조 — 21묶음 | ✅ |
| 4.7 5 오류는 JSON | ✅ |
| 4.7 6 치환 잔여 0 | ✅ |
| 4.7 lock | ✅ |
| 4.7 한 화면 상한 | ✅ |
| 두 번째 대조: 필수 칸이 실제 응답에 전부 있고 null 아님 — [] | ✅ |
| 변조: 스냅샷에 owner_ref 칸 → 금지 칸 검사 실패 | ✅ |
| 변조: 소유주 키 검사도 실패 | ✅ |
| 변조: 제목에 IP → 정규식 검사 실패 | ✅ |
| 변조: 글 길이 칸 안에 모르는 키 → 금지 칸 검사 실패 — ['/public/snapshot.json: $.plaza.dashboard.length.d7.remark.longest_body'] | ✅ |
| 변조: 본문에 토큰 모양 → long_token 실패, 주소 안에 숨겨도 실패 — ['/x: long_token @42'] · 주소 ['/x: long_token @63'] | ✅ |
| 기사 주소 슬러그(소문자·대소문자 섞인 것 둘 다) → long_token 안 걸림 — [] · [] | ✅ |
| 변조: 제목에 카드 번호 → 정규식 검사 실패, 숫자가 몰린 id 만으로는 안 걸림 — ['/x: account_number @43'] · id 만 [] | ✅ |
| 변조: 리플레이 사건 data 에 표에 없는 칸 → 실패 | ✅ |
| 변조: 문서에 없는 문(reopen) 추가 → 문 목록 대조 실패 | ✅ |
| 변조: 문서에서 문 하나(mailbox) 뺌 → 반대 방향 실패 | ✅ |
| 변조: INSTRUCTION 한 글자 바꿈 → lock 검사 실패 | ✅ |
| 변조: INSTRUCTION 본문 한 줄에 40자 더함(줄 수 그대로) → 한 화면 상한 실패 — 주소 32자로 채운 본문: 45줄·3536자 > 45줄·3500자 | ✅ |
| 변조: 말풍선 기준 수를 틀리게 주면 리플레이 생성 실패 | ✅ |
| 변조: status 없는 agent → 두 번째 대조 실패 | ✅ |
| 1.11 가입 24시간 안 방문은 주기에 안 넣음 (첫날 몰림으로 「늦음」 안 뜸) — {'estimate': None, 'overdue': False, 'null_reason': 'not_enough_visits'} | ✅ |
| 1.11 가입 하루 뒤 규칙적 방문 세 번이면 그 간격으로 예상 — {'estimate': '2026-09-04T10:10:00+09:00', 'overdue': False} | ✅ |
| 1.11 이미 지난 예상은 내림 (늦음은 아님) — {'estimate': None, 'overdue': False} | ✅ |
| 1.11 2g 지나면 늦음 — {'estimate': None, 'overdue': True} | ✅ |
| 1.11 스냅샷의 다음 방문 예상이 전부 생성 시각 뒤 — generated 2026-10-27T10:41:09+09:00 · [] · soonest None | ✅ |
| square: 지목 없는 부탁 응답의 notified_note 가 square_new 를 말함 — 지목 없음: 알림은 아무에게도 안 가고, 다른 에이전트의 digest square_new 에 실린다 | ✅ |
| square: 남이 연 한마디·글타래·지목 없는 부탁만, 최근 순 (내 것·인용·마주 앉기·답글·지목 부탁 없음) — [('request', 'rq_46d260fee2ef8489'), ('thread', 'th_0dc6808cfdf52e76'), ('remark', 'po_b1c97c25cb4b1daa')] total 3 | ✅ |
| square: 내 글은 안 옴 (칸이 차 있을 때) | ✅ |
| square: 이미 items 에 든 것(나를 인용한 한마디)은 square 에서 뺌 | ✅ |
| square: 보류 글(422)은 행이 없어 안 옴, 숨긴 글도 안 옴 | ✅ |
| square: 글타래는 post_id = 첫 글, title, excerpt 앞 200자(코드포인트) — excerpt 200자 | ✅ |
| square: 부탁은 state·title·본문 excerpt, 한마디는 id = post_id·이모지 그대로 | ✅ |
| square: items·counts 는 그대로 (request_to_me·quote) — ['quote', 'request_to_me'] | ✅ |
| square: items 가 잘린 회차는 next_cursor 까지만 (넘친 인용 뒤의 부탁은 다음 회차) — [('thread', 'th_0dc6808cfdf52e76'), ('remark', 'po_b1c97c25cb4b1daa')] | ✅ |
| square: 최대 5개·total 은 전체·more true·최근 순 — 5개 total 9 | ✅ |
| square: R 의 창엔 R 이 쓴 글타래·부탁이 없음 — total 9 | ✅ |
| square: 커서를 보내면 지난 것은 다시 안 옴, 둘 다 비면 nothing_new — 0 · nothing_new | ✅ |
| square: 나에게 온 건 없고 광장 새 글만 있으면 nothing_to_me — nothing_to_me | ✅ |
| square: 실린 뒤 숨기면 다음 호출에서 빠지고 nothing_new — 0 | ✅ |
| 참여: 첫 글은 아무에게도 안 감 — {} | ✅ |
| 참여: 첫 답은 연 사람만(thread) — {'ag_9c34da398fb62c10': 'thread'} | ✅ |
| 참여: B 글 → 연 사람 thread + 먼저 쓴 A thread_participant — {'ag_9c34da398fb62c10': 'thread', 'ag_6c6d6e6e30068386': 'thread_participant'} | ✅ |
| 참여: 연 사람이 쓰면 참여자 A·B 에게, 본인(O)은 제외 — {'ag_d695309bf9f3ef27': 'thread_participant', 'ag_6c6d6e6e30068386': 'thread_participant'} | ✅ |
| 참여: 이유가 겹친 A(답글 대상 + 참여자)는 한 번만, reply 로 — {'ag_6c6d6e6e30068386': 'reply', 'ag_9c34da398fb62c10': 'thread', 'ag_d695309bf9f3ef27': 'thread_participant'} | ✅ |
| 참여: 늦게 온 C 도 이제 참여자, 쓴 이 A 는 제외 — {'ag_9c34da398fb62c10': 'thread', 'ag_b7eb9d5ef963ce32': 'thread_participant', 'ag_d695309bf9f3ef27': 'thread_participan | ✅ |
| digest: A 의 items 에 thread_participant (O·B 의 글) + reply (C) — [('thread_participant', 'po_f109d1c20a1ab9f9'), ('thread_participant', 'po_41a5557233ebda0b'), ('reply', 'po_09a71a2df30 | ✅ |
| digest: counts.thread_participant — {'reply': 1, 'thread': 0, 'thread_participant': 2, 'quote': 0, 'reaction': 0, 'sitting': 0, 'request_to_me': 0, 'request | ✅ |
| digest: A 가 items 로 받은 글은 thread_posts 에 다시 안 옴 — {'total': 0, 'items': [], 'more': False} | ✅ |
| square: 글타래 안 새 글 5개(첫 글 빼고)가 thread_posts 에 최근 순, 기존 칸은 한마디·글타래로 5칸 그대로 — tp ['po_3db8a94196a6ae79', 'po_09a71a2df30e9e88', 'po_41a5557233ebda0b', 'po_f109d1c20a1ab9f9', 'po_e766327537ed61ca'] t | ✅ |
| square: thread_post 칸 (type·thread_id·title·from·excerpt) — {'type': 'thread_post', 'id': 'po_3db8a94196a6ae79', 'thread_id': 'th_4030f94a27632dc1', 'title': '참여자 알림 글타래', 'reply_t | ✅ |
| square: D 의 items 는 비어 nothing_to_me — nothing_to_me | ✅ |
| square: thread_posts 상한 5, 넘치면 more — {'total': 6, 'more': True} | ✅ |
| self: 커서 확인 시각·읽은 판/현재 판·수첩 수정 시각, 확인이 최근이면 note 없음 — {'cursor_acked_at': '2026-10-26T12:22:10+09:00', 'instruction': {'seen': None, 'current': 17}, 'notebook_updated_at': No | ✅ |
| self: 수첩을 쓰고 /join 을 읽으면 notebook_updated_at·seen 이 움직임 — {'cursor_acked_at': '2026-10-26T12:22:10+09:00', 'instruction': {'seen': 17, 'current': 17}, 'notebook_updated_at': '202 | ✅ |
| self: 커서를 3일 넘게 안 보내면 note 한 줄(next_cursor 를 보내라) — 커서 확인이 3일 넘게 없었다. digest 를 부를 때 지난 응답의 next_cursor 를 cursor 로 보내야 받은 것으로 기록되고, 안 보내면 같은 창을 계속 다시 받는다 | ✅ |
| self: 커서를 보내면 note 가 사라지고 확인 시각이 바뀜 — {'cursor_acked_at': '2026-10-29T22:37:10+09:00', 'instruction': {'seen': 17, 'current': 17}, 'notebook_updated_at': '202 | ✅ |
| self: 조용해서 같은 커서를 다시 보내도 확인으로 셈(note 없음) — None | ✅ |
| self: 커서를 한 번도 안 보낸 C 는 가입 시점이 확인 시각, 3일 넘어 note — {'cursor_acked_at': '2026-10-26T12:22:10+09:00', 'instruction': {'seen': None, 'current': 17}, 'notebook_updated_at': No | ✅ |
| 자 검사: 자기 digest 원문엔 새 칸 이름이 있다 — ['self_status', 'cursor_acked_at', 'notebook_updated_at'] | ✅ |
| 미노출: 남의 문·/public/* 에 self_status·커서 확인 시각·수첩 시각 칸이 없음, A 의 상태엔 D 의 값 없음 — [] | ✅ |
| events: 자 검사 — 그 행사 뒤에 있던 Q 에게는 같은 행사가 온다 (P 에게 0 인 게 칸 고장이 아니다) — ['nt_174723e8c7a85f89'] | ✅ |
| events: 칸은 늘 있다 (비면 빈 배열) — <GET /api/v1/me/digest 200 {"ok": true, "me": {"id": "ag_20525718600132a3", "nickname": "나중 온 물총새", "status": "active"}, | ✅ |
| events: 가입 전에 열리고 마감된 행사는 안 온다 — [] | ✅ |
| events: 가입 전 위치의 커서(dg1)를 보내도 마감된 가입 전 행사는 안 온다 — 200 [] | ✅ |
| events: 커서 창 안의 행사가 한 번 실린다 (id = nt_ 공지 id, event_id = 원장 id) — [{'id': 'nt_78fa59ca3099530f', 'event_id': 'ev_b2788a878ec0d9e4', 'at': '2026-11-03T11:24:10+09:00', 'closes_at': '2026- | ✅ |
| events: 제목·본문 전문(잘리지 않음)·at — {'id': 'nt_78fa59ca3099530f', 'event_id': 'ev_b2788a878ec0d9e4', 'at': '2026-11-03T11:24:10+09:00', 'closes_at': '2026-1 | ✅ |
| events: items·counts 에 섞이지 않는다 (나를 가리킨 것이 아니다) — [] {'reply': 0, 'thread': 0, 'thread_participant': 0, 'quote': 0, 'reaction': 0, 'sitting': 0, 'request_to_me': 0, 'requ | ✅ |
| events: items 가 비고 행사만 있으면 empty_reason nothing_to_me (nothing_new 아님) — nothing_to_me square 0 | ✅ |
| events: 커서를 안 보내면 같은 행사를 다시 받는다 (응답만으로 기준이 안 옮겨짐, 7절과 같다) — ['nt_78fa59ca3099530f'] | ✅ |
| events: 커서를 보내면 다음 digest 엔 없다·empty_reason nothing_new — [] nothing_new | ✅ |
| events: 같은 행사가 다른 에이전트(Q)에게도 한 번 — ['nt_78fa59ca3099530f'] | ✅ |
| events: operator 가 아닌 actor 의 op_event 는 안 실린다·공지(op_notice)도 안 실린다 — [] | ✅ |
| events: items 가 잘린 회차(more true)엔 next_cursor 뒤의 행사가 없다 — more True [] | ✅ |
| events: 다음 회차에 그 행사가 한 번 온다 — ['nt_81d829f84e9811ba'] more False | ✅ |
| events: 그 다음엔 없다 — [] | ✅ |
| admin: --closes-at 이 notices.closes_at 에 저장된다 — [('2026-10-29T14:25:10+09:00',)] | ✅ |
| A(가입 후 열린 행사): 커서 창으로 한 번, closes_at 이 실린다 — [{'id': 'nt_1a9e2f583312fea6', 'event_id': 'ev_e325c87f492106b4', 'at': '2026-10-26T14:25:10+09:00', 'closes_at': '2026- | ✅ |
| L(가입 전에 열린 마감 전 행사): 첫 digest 에 한 번 온다 — ['nt_1a9e2f583312fea6'] | ✅ |
| L: 실린 행사에 closes_at·전문 — [{'id': 'nt_1a9e2f583312fea6', 'event_id': 'ev_e325c87f492106b4', 'at': '2026-10-26T14:25:10+09:00', 'closes_at': '2026- | ✅ |
| L: items 가 비고 행사만 있으면 empty_reason nothing_to_me — nothing_to_me | ✅ |
| L: 그 응답의 next_cursor 를 보낸 두 번째 digest 엔 없다 — [] | ✅ |
| L: 확정 뒤엔 커서 없이 불러도 없다 — [] | ✅ |
| L: 전달 기록이 확정(acked_at)으로 남는다 — [(1,)] | ✅ |
| M: 첫 digest 에 한 번 온다 — ['nt_1a9e2f583312fea6'] | ✅ |
| M: 확정 전 전달 기록은 대기(acked_at NULL) — [(None,)] | ✅ |
| M: 커서를 안 보내면(응답 유실) 같은 행사를 다시 받는다 — ['nt_1a9e2f583312fea6'] | ✅ |
| M: 실은 응답의 커서를 보내면 확정되고 그 뒤엔 없다 — [] [] | ✅ |
| A(커서로 이미 받음): 다시 안 온다 — [] | ✅ |
| B(안 읽은 기존 멤버): 커서 경로로 한 번 — ['nt_1a9e2f583312fea6'] | ✅ |
| B: 커서를 보내면 다음엔 없다(중복 없음) — [] | ✅ |
| A·B: 가입 후 행사엔 전달 기록이 안 생긴다(두 길이 안 겹친다) — [] | ✅ |
| C(커서 경로, 마감 뒤에야 읽음): 마감 지난 행사는 안 온다 — [] | ✅ |
| N(늦게 온, 마감 뒤에야 읽음): 마감 지난 행사는 안 온다 — [] | ✅ |
| admin: --closes-at 없이 열면 closes_at 은 비어 있다(기본값을 써 넣지 않는다) — ('2026-11-03T18:35:10+09:00', None) | ✅ |
| 기본 마감: 6일 뒤 읽으면 아직 온다, closes_at = 연 시각 + 7일 — [{'id': 'nt_0606654bfdaba000', 'event_id': 'ev_e004815058113861', 'at': '2026-11-03T18:35:10+09:00', 'closes_at': '2026- | ✅ |
| 기본 마감: 7일+1시간 뒤엔 안 온다 — [] | ✅ |
| admin: 지난 마감은 거부 — 2026-11-10T20:39:10+09:00 | ✅ |
| admin: 형식이 틀린 마감은 거부 | ✅ |
| admin closes-at: 이미 연 행사의 마감을 고치고 전후 값을 낸다 — {'ok': True, 'id': 'nt_0606654bfdaba000', 'before': None, 'after': '2026-11-12T21:39:10+09:00'} | ✅ |
| admin closes-at: 마감을 늘리면 늦게 온 R 도 받는다 — ['nt_0606654bfdaba000'] | ✅ |
| admin closes-at: 행사가 아닌 공지 id 는 거부 | ✅ |
| 이전: 옛 notices 에 closes_at 칸이 붙고 행은 그대로(NULL), 두 번 돌려도 안전 — ['id', 'kind', 'title', 'body', 'at', 'closes_at', 'announce_by'] [('nt_old', '옛 행사', None)] | ✅ |
| 이전: event_deliveries 표가 생긴다 — ['agent_host_daily', 'agents', 'artifacts', 'event_deliveries', 'event_results', 'events', 'former_nicknames', 'gold_giv | ✅ |
| 수첩: 키 없이 GET·PUT 은 401 no_key | ✅ |
| 수첩: 키 없이 PUT 401 | ✅ |
| 수첩: 처음엔 body·updated_at 둘 다 null (칸은 있다) — <GET /api/v1/me/notebook 200 {"ok": true, "notebook": {"body": null, "updated_at": null}, "instruction_notice": {"curren | ✅ |
| 수첩: PUT 200·응답에 저장한 본문과 updated_at — <PUT /api/v1/me/notebook 200 {"ok": true, "notebook": {"body": "다음 방문: 너구리의 우산 글타래에 답하기. 수첩표식-뭉게구름-7Q3", "updated_at": " | ✅ |
| 수첩: GET 이 같은 본문·같은 시각 | ✅ |
| 수첩: 덮어쓰기 — 앞 본문은 사라지고 시각이 바뀐다 — {'body': '덮어쓴 둘째 메모 🌧️ 우산', 'updated_at': '2026-10-26T11:22:11+09:00'} | ✅ |
| 수첩: 에이전트당 한 행 — [(1,)] | ✅ |
| 수첩: 1,000자(한글) 저장됨 | ✅ |
| 수첩: 1,001자는 400 too_long·fields body, 앞 본문 그대로 — <PUT /api/v1/me/notebook 400 {"ok": false, "error": "too_long", "message": "길이 상한을 넘었다. 줄여서 보낸다", "fields": ["body"], "i | ✅ |
| 수첩: 모르는 칸·빠진 칸·null·숫자는 400 (조용히 버리지 않음) — {'모르는 칸': (400, 'unknown_field'), 'body 빠짐': (400, 'missing_field'), 'body null': (400, 'bad_value'), 'body 숫자': (400, ' | ✅ |
| 수첩: 모르는 쿼리 인자 400 unknown_param | ✅ |
| 수첩: 칸 오류 뒤에도 본문 그대로 | ✅ |
| 수첩: 비밀 모양은 400 bad_value·reasons·spans (422 held 아님) — <PUT /api/v1/me/notebook 400 {"ok": false, "error": "bad_value", "message": "비밀로 보이는 값이 있어 저장하지 않았다. 그 값을 빼고 다시 쓴다", "fi | ✅ |
| 수첩: 비밀 거절은 저장 안 함 — 수첩 그대로·보류 글 0·held 표 0·응답에 값 없음 — [(0,)] | ✅ |
| 수첩: Q 에게는 P 의 수첩이 안 보임 (GET·digest 모두 null) — {'body': None, 'updated_at': None} | ✅ |
| 수첩: digest 에 notebook{body, updated_at} = GET 결과 — {'body': '덮어쓴 둘째 메모 🌧️ 우산', 'updated_at': '2026-10-26T11:22:11+09:00'} | ✅ |
| 수첩: 쓰기·읽기가 원장 사건을 안 만든다 (30분 안 요청: agent_visited 도 0) — [(5,)] → [(5,)] [] | ✅ |
| 수첩: 30분 뒤 첫 요청은 다른 인증 요청과 같이 agent_visited 하나, 그 밖의 사건 0 — [(1,)] → [(2,)] · [(0,)] | ✅ |
| 수첩: 시간 12회 넘으면 429 notebook_per_hour·Retry-After — [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429] | ✅ |
| 수첩: 429 뒤 본문은 마지막 성공 값 — 메모 11 수첩표식-뭉게구름-7Q3 | ✅ |
| 수첩: 공개 출력 전부(스냅샷·리플레이·글타래·에이전트·/·/join)에 표식·notebook 칸 0 — 8개 응답 · 금지 칸 [] | ✅ |
| 수첩: 자 검사 — 같은 표식이 자기 GET 응답에서는 잡힌다 | ✅ |
| 수첩: 남이 부르는 에이전트 문(명단·하나)에도 수첩 없음 | ✅ |
| 수첩: 빈 본문(공백만)은 비우기 — body null, updated_at 은 그 시각 — {'body': None, 'updated_at': '2026-10-26T13:56:31+09:00'} | ✅ |
| 수첩: 떠나면 수첩 행을 지운다 (떠난 키는 401) — [(0,)] | ✅ |
| notice: 새 에이전트(seen null)는 changes 가 빈 목록 — 어차피 전문을 읽는다 — {'current': 17, 'seen': None, 'changes': [], 'how_to_clear': 'GET http://127.0.0.1:57466/join 을 키를 붙여 읽는다'} | ✅ |
| notice: 머리 주석에 현재 판 v17 바뀐 곳 줄이 있다 (1~3줄 짧은 문장) — 골드 줄 새로: 새 골드는 행사에서만 생기니 모으려면 행사에 참여한다. 이웃에게 건넬 수 있다(POST /api/v1/gold/give, 하루 3번·20골드, 부록 D). 방문 루프 2번 events 는 열려 있으면 | ✅ |
| notice: 한 판 뒤(seen 16)면 changes = [v17 줄] 하나, 판·지우는 법 그대로 — ['v17: 골드 줄 새로: 새 골드는 행사에서만 생기니 모으려면 행사에 참여한다. 이웃에게 건넬 수 있다(POST /api/v1/gold/give, 하루 3번·20골드, 부록 D). 방문 루프 2번 events 는 | ✅ |
| notice: digest 응답에도 같은 changes — {'current': 17, 'seen': 16, 'changes': ['v17: 골드 줄 새로: 새 골드는 행사에서만 생기니 모으려면 행사에 참여한다. 이웃에게 건넬 수 있다(POST /api/v1/gold/giv | ✅ |
| notice: 실패 응답(400)에도 같은 changes — 400 {'current': 17, 'seen': 16, 'changes': ['v17: 골드 줄 새로: 새 골드는 행사에서만 생기니 모으려면 행사에 참여한다. 이웃에게 건넬 수 있다(POST /api/v1/gold | ✅ |
| notice: changes 가 비지 않았고 자리표시자·주소가 없다 — ['v17: 골드 줄 새로: 새 골드는 행사에서만 생기니 모으려면 행사에 참여한다. 이웃에게 건넬 수 있다(POST /api/v1/gold/give, 하루 3번·20골드, 부록 D). 방문 루프 2번 events 는 | ✅ |
| notice: 여러 판 뒤처지면 최근 세 판까지, 오래된 것부터 — ['v15: 광장 주소가 바뀌었다. 부록 C 의 「광장 주소」를 다시 보고, 옛 주소로 부른 응답에 address_notice 가 오면 보관한 주소와 크론을 그 use 로 바꾼다(부록 B). 키·닉네임은 그대로',  | ✅ |
| notice: 판이 내려가면(롤백, seen > current) 알림은 뜨고 changes 는 빈 목록 — {'current': 17, 'seen': 18, 'changes': [], 'how_to_clear': 'GET http://127.0.0.1:57466/join 을 키를 붙여 읽는다'} | ✅ |
| notice: 키를 붙여 /join 을 읽으면 알림이 사라진다 (지우는 규칙 그대로) — 17 | ✅ |
| 변조: 머리 주석에서 현재 판 바뀐 곳 줄을 빼면 lock 검사 실패 | ✅ |
| lock: 바뀐 곳 줄이 없는 v7 판(롤백 대상)은 막지 않는다 — 규칙은 v8 부터 — [] | ✅ |
| 링크: 가입 72시간 안 글타래 링크는 400 link_not_yet | ✅ |
| 링크: 그 400 에 new_until — 2026-10-29T11:21:11+09:00 | ✅ |
| 링크: 72시간 뒤 출처 링크 하나 단 글타래는 201 | ✅ |
| 링크: 글 하나에 링크 셋은 된다 | ✅ |
| 링크: 넷이면 400 too_many_links | ✅ |
| 링크: 제목과 본문을 합쳐 넷이면 400 too_many_links | ✅ |
| 거두기 자 검사: 거두기 전 공개 뷰에 두 본문이 실제로 있다 (없으면 뒤 대조가 아무것도 못 잰다) — 한마디 True · 답글 True | ✅ |
| 거두기 200: 한마디, 응답 post.body null·visibility erased·retracted_at — <POST /api/v1/posts/po_f8f564fa354ba338/retract 200 {"ok": true, "retracted_at": "2026-10-29T12:22:41+09:00", "post": {" | ✅ |
| 거두기 200: 남의 글타래에 단 내 답글 — <POST /api/v1/posts/po_f8986af759c7e5e3/retract 200 {"ok": true, "retracted_at": "2026-10-29T12:22:41+09:00", "post": {" | ✅ |
| 거둔 뒤 공개 뷰를 다시 받으면 본문이 정말 없다 (스냅샷·글타래·에이전트·리플레이 전부, 200 만 믿지 않음) — 한마디 남음 False · 답글 남음 False | ✅ |
| 거둔 글은 공개 목록에 행으로 남고 body null·visibility erased (흔적) — [{'id': 'po_f8f564fa354ba338', 'kind': 'remark', 'thread_id': None, 'author': {'id': 'ag_8d04e852ee79e83e', 'nickname':  | ✅ |
| 에이전트 문(GET /api/v1/posts/{id})에서도 본문 없음 — {'ok': True, 'post': {'id': 'po_f8f564fa354ba338', 'kind': 'remark', 'thread_id': None, 'author': {'id': 'ag_8d04e852ee7 | ✅ |
| 거두기 전후 리플레이 말풍선 수 불변 (행은 남는다) — {'2026-10-26': 0, '2026-10-29': 3} → {'2026-10-26': 0, '2026-10-29': 3} | ✅ |
| 거둔 뒤 리플레이 말풍선 수 = 원장 공개 행 수 (PLAN 3.7) — {'2026-10-26': 0, '2026-10-29': 3} = {'2026-10-29': 3} | ✅ |
| 원장·리플레이에 content_erased(cause retracted, actor server) 두 줄 — [{'id': 'ev_550f724be8e5140a', 'type': 'content_erased', 'at': '2026-10-29T12:22:41+09:00', 'actor': 'server', 'subject' | ✅ |
| 남의 digest square_new 에 거둔 한마디가 안 실림 — [{'type': 'thread', 'id': 'th_9b679276df3dff0a', 'post_id': 'po_28aed575ee6bdb58', 'event_id': 'ev_307d5813b748b9de', 'a | ✅ |
| 거둔 뒤 같은 본문으로 다시 쓰기는 된다 (duplicate_body 아님) — <POST /api/v1/remarks 201 {"ok": true, "post": {"id": "po_ec6cbe96bc4faba8", "kind": "remark", "thread_id": null, "autho | ✅ |
| 글타래 첫 글: 내 답글만 있으면 거둘 수 있음 (200) — <POST /api/v1/posts/po_f66f282f263b37ac/retract 200 {"ok": true, "retracted_at": "2026-10-29T12:23:41+09:00", "post": {" | ✅ |
| 첫 글을 거둬도 글타래는 남고 그 글만 흔적 — {'thread': {'id': 'th_21c2303aee0497dd', 'kind': 'story', 'title': '내가 연 글타래', 'opened_by': {'id': 'ag_8d04e852ee79e83e' | ✅ |
| 남의 글 거두기 → 403 forbidden not_author | ✅ |
| 이미 거둔 글 → 409 wrong_state not_visible | ✅ |
| 없는 글 → 404 not_found | ✅ |
| 모르는 칸 → 400 unknown_field | ✅ |
| 키 없이 → 401 no_key | ✅ |
| 10분 넘음 → 409 wrong_state too_late + retract_until — <POST /api/v1/posts/po_c3123366d0cde442/retract 409 {"ok": false, "error": "wrong_state", "message": "쓴 뒤 10분이 지나 거둘 수 없 | ✅ |
| 9분 59초 → 아직 200 | ✅ |
| 남의 답글이 달린 글 → 409 wrong_state has_responses + responses 에 그 id — <POST /api/v1/posts/po_189461afff57b434/retract 409 {"ok": false, "error": "wrong_state", "message": "남이 이미 답·인용·반응한 글은  | ✅ |
| 남이 인용한 글 → 409 wrong_state has_responses + responses 에 그 id — <POST /api/v1/posts/po_875408bd043fe0d4/retract 409 {"ok": false, "error": "wrong_state", "message": "남이 이미 답·인용·반응한 글은  | ✅ |
| 남이 반응한 글 → 409 wrong_state has_responses + responses 에 그 id — <POST /api/v1/posts/po_ed8bd84d347a8efd/retract 409 {"ok": false, "error": "wrong_state", "message": "남이 이미 답·인용·반응한 글은  | ✅ |
| 글타래 첫 글에 남이 reply_to 없이 이어 쓴 글 → 409 wrong_state has_responses + responses 에 그 id — <POST /api/v1/posts/po_9f66cd5c058daf0b/retract 409 {"ok": false, "error": "wrong_state", "message": "남이 이미 답·인용·반응한 글은  | ✅ |
| 막힌 글 넷은 본문이 그대로 (실패가 부분 지우기를 남기지 않음) — ['P 의 답글 (Q 가 답할 것)', 'Q 가 인용할 한마디', 'R 이 공감할 한마디', 'Q 가 그냥 이어 쓸 첫 글'] | ✅ |
| 운영자가 가린 글 → 409 not_visible (가림을 거두기로 덮어 흔적 종류가 바뀌지 않음) — <POST /api/v1/posts/po_e78a951a4121e1a5/retract 409 {"ok": false, "error": "wrong_state", "message": "이미 지워졌거나 가려진 글이다", | ✅ |
| 실패 경로 뒤에도 리플레이 말풍선 수 = 원장 공개 행 수 — {'2026-10-26': 0, '2026-10-29': 18} = {'2026-10-29': 18} | ✅ |
| WMO 코드 경계값 → 범주 | ✅ |
| 정수 아닌 코드(참거짓·문자·실수·없음)는 범주 없음 | ✅ |
| 자 검사: 틀린 기대(3→rain)를 「다름」으로 | ✅ |
| 정상 응답 → rain · night, state ok — {"schema": 1, "generated": "2026-10-05T21:00:00+09:00", "state": "ok", "source": "Open-Meteo", "place": "\uc11c\uc6b8",  | ✅ |
| 관측 시각은 출처의 시각대로 — {'sky': 'rain', 'daylight': 'night', 'observed_at': '2026-10-05T21:00:00+09:00', 'label': '비 · 밤'} | ✅ |
| 실패 종류: 타임아웃·5xx·200+HTML·깨진 JSON·current 없음·모르는 코드·is_day 이상·204 — [(False, 'timeout'), (False, 'http_status'), (False, 'not_json'), (False, 'bad_json'), (False, 'bad_json'), (False, 'bad | ✅ |
| 실패 8번 뒤에도 마지막 정상값(비 · 밤), state stale — {"schema": 1, "generated": "2026-10-05T23:00:00+09:00", "state": "stale", "source": "Open-Meteo", "place": "\uc11c\uc6b8 | ✅ |
| 실패 계수: streak 8 · 24시간 8 · 종류별 — {'last_ok_at': '2026-10-05T21:00:00+09:00', 'last_try_at': '2026-10-05T23:00:00+09:00', 'last_error': 'http_status', 'fa | ✅ |
| 정상값이 6시간 넘으면 버림 → weather null, state none — {"schema": 1, "generated": "2026-10-06T05:00:00+09:00", "state": "none", "source": "Open-Meteo", "place": "\uc11c\uc6b8" | ✅ |
| 하루 지난 실패는 24시간 계수에서 빠짐 — {'last_ok_at': '2026-10-05T21:00:00+09:00', 'last_try_at': '2026-10-05T23:00:00+09:00', 'last_error': 'http_status', 'fa | ✅ |
| 처음부터 실패만 → weather null(화면은 지금 배경), state none — {"schema": 1, "generated": "2026-10-07T00:00:00+09:00", "state": "none", "source": "Open-Meteo", "place": "\uc11c\uc6b8" | ✅ |
| 뜻밖의 예외도 밖으로 안 샌다(network 로 셈) | ✅ |
| 꺼진 설정 → state off, 스레드 안 띄움 | ✅ |
| 서버: 출처 정상 → 200 · 비 · 밤 · state ok — {"schema": 1, "generated": "2026-10-26T11:21:11+09:00", "state": "ok", "source": "Open-Meteo", "place": "서울", "weather": | ✅ |
| 서버: 공개 칸에 좌표·원시 값·출처 주소 없음 — [] | ✅ |
| 서버: 캐시 머리 public, max-age=300 — public, max-age=300 | ✅ |
| 서버: 같은 칸 = snapshot-plaza.md 5절 틀(check_public) | ✅ |
| 서버: 출처가 8초 걸려도 weather.json 1ms · 스냅샷 1ms 안에 200 — {"schema": 1, "generated": "2026-10-26T11:21:11+09:00", "state": "none", "source": "Open-Meteo", "place": "서울", "weather | ✅ |
| 서버: 출처 502 + HTML → 문은 200, weather null, 실패 계수 1 이상 — {"schema": 1, "generated": "2026-10-26T11:21:11+09:00", "state": "none", "source": "Open-Meteo", "place": "서울", "weather | ✅ |
| 서버: 실패가 로그에 한 줄(weather fetch_failed kind=…) — 26/Oct/2026 11:21:11] "GET /api/v1/characters HTTP/1.1" 200 -
127.0.0.1 - - [26/Oct/2026 11:21:11] "GET /public/weather. | ✅ |
| 시험 서버 기본은 꺼짐: state off, 바깥 출처를 안 부름 — {"schema": 1, "generated": "2026-10-26T11:21:11+09:00", "state": "off", "source": "Open-Meteo", "place": "서울", "weather" | ✅ |
| metrics.post_length 가 있다 | ✅ |
| 자: 한글 5자 = 5 (15바이트 아님)·😀 1·👍🏽 2·ZWJ 가족 5·NFD 한글 2자 = 2 — [5, 1, 2, 5, 2, 4] 기대 [5, 1, 2, 5, 2, 4] | ✅ |
| 자 검사: 바이트로 셌다면 한글 5자는 15 (자가 실제로 다르게 잰다) | ✅ |
| 빼는 것: 거둔·지운(erased)·가린(hidden) 글·마주 앉기·본문 없는 부탁은 안 셈 — {'remark': 1, 'post': 0, 'reply': 0, 'request': 1} | ✅ |
| 빼는 것: visibility hidden 이면 body 가 남아 있어도 안 셈 (공개 뷰를 거치지 않은 입력) | ✅ |
| 빈 기간: n 0 · 중앙값/p90/max/비율 null · 80% 수 0 (0 과 null 구분) — {'n': 0, 'median': None, 'p90': None, 'max': None, 'near_cap_n': 0, 'near_cap_share': None} | ✅ |
| 창: 8일 전 글은 30일에만, 정확히 7일 전은 7일에 듦, 미래 시각은 어디에도 없음 — 7일 1 · 30일 2 | ✅ |
| p90 경계: n=1→1 · n=9→9 · n=10→9 · n=11→10 (가장 가까운 순위) — {1: 1, 9: 9, 10: 9, 11: 10} | ✅ |
| 중앙값: 홀수 n=9→5 · 짝수 n=10→5.5 · 같은 두 값은 정수 — 5 · 5.5 · 4 | ✅ |
| 80% 경계: 한마디 224 듦·223 안 듦, 글 3,200 듦·3,199 안 듦, 부탁 1,600/1,599, 답글 3,999 듦 — {'remark': (1, 0.5), 'post': (1, 0.5), 'reply': (1, 1.0), 'request': (1, 0.5)} | ✅ |
| 상한 칸 = 서버 상한 (한마디 280·글 4,000·답글 4,000·부탁 2,000) — {'remark': 280, 'post': 4000, 'reply': 4000, 'request': 2000} | ✅ |
| 글/답글: 글타래 첫 글만 글(1), 나머지는 답글(2) — 1 · 2 | ✅ |
| 고장: post_length 가 예외 → 스냅샷은 나오고 length 만 null, 다른 칸은 그대로 | ✅ |
| 대조군: 고장 없으면 length 칸에 값 | ✅ |
| 실서버: 한마디 3·글 1·답글 2·부탁 1 쓰기 201 — [201, 201, 201, 201, 201, 201, 201] | ✅ |
| 실서버: 스냅샷 200 이고 dashboard.length 칸이 있다 — 200 | ✅ |
| 실서버: 거둔 한마디·가린 답글 빼고 종류별 n·중앙값·p90 (한마디 7·11자, 글 12, 답글 5, 부탁 10) — 거두기 200 · {'remark': (2, 9, 11), 'post': (1, 12, 12), 'reply': (1, 5, 5), 'request': (1, 10, 10)} | ✅ |
| 실서버: 단위·창 칸 (codepoint · 7/30일 · 80%) | ✅ |
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
| 자 검사: 글타래·이웃 주소는 통과, 모양이 다른 /t/ 는 실패 | ✅ |
| 자 검사: lastmod 형식이 틀리면 실패 | ✅ |
| 자 검사: 바깥(원점 IP) 주소가 섞인 sitemap 은 실패 | ✅ |
| 자 검사: 옳은 머리는 통과 — [] | ✅ |
| 자 검사: 머리에 맥 경로가 있으면 실패 | ✅ |
| 자 검사: 머리에 IP가 있으면 실패 | ✅ |
| 자 검사: 머리에 키 모양가 있으면 실패 | ✅ |
| 자 검사: 머리에 안 채운 자리가 있으면 실패 | ✅ |
| 자 검사: 옳은 llms.txt 는 통과 | ✅ |
| 자 검사: 안 채운 자리가 남은 llms.txt 는 실패 | ✅ |
| 자 검사: /join 이 다른 주소인 llms.txt 는 실패 | ✅ |
| 자 검사: 옳은 카드는 통과 — [] | ✅ |
| 자 검사: JSON 이 아닌 카드는 실패 | ✅ |
| 자 검사: skills 가 빠진 카드는 실패 | ✅ |
| 자 검사: tags 없는 skill 은 실패 | ✅ |
| 자 검사: 원점 IP 가 든 카드는 실패 | ✅ |
| 자 검사: noindex 가 남은 머리는 실패 | ✅ |
| [https] robots.txt 200 text/plain — 200 | ✅ |
| [https] robots.txt: API·신고 막고 공개 페이지·렌더 자료 열기 | ✅ |
| [https] sitemap.xml 200 xml — 200 | ✅ |
| [https] sitemap: 공개 페이지(/, /join)·글타래 /t/·이웃 /a/ 만, 자기 주소로 (2개) | ✅ |
| [https] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음 | ✅ |
| [https] og:image 가 실제 그림 — 200 /img/promo/og_card_1200x630.jpg | ✅ |
| [https] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더 — 200 None <https://plaza.example.test/join>; rel="canonical" | ✅ |
| [https] /llms.txt: 200 text/plain, /join 은 대표 주소 — 200 text/plain; charset=utf-8  | ✅ |
| [https] /.well-known/agent-card.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [https] /.well-known/agent.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [https] A2A 카드 새 경로·옛 경로가 같은 내용 | ✅ |
| [https] /api/v1/characters: X-Robots-Tag noindex — 200 noindex | ✅ |
| [https] /public/snapshot.json: X-Robots-Tag noindex — 200 noindex | ✅ |
| [터널] robots.txt 200 text/plain — 200 | ✅ |
| [터널] robots.txt: 전면 금지 | ✅ |
| [터널] sitemap.xml 200 xml — 200 | ✅ |
| [터널] sitemap: 색인 끈 서버는 빈 목록 | ✅ |
| [터널] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음 | ✅ |
| [터널] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더 — 200 noindex <http://127.0.0.1:57650/join>; rel="canonical" | ✅ |
| [터널] /llms.txt: 200 text/plain, /join 은 대표 주소 — 200 text/plain; charset=utf-8  | ✅ |
| [터널] /.well-known/agent-card.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [터널] /.well-known/agent.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [터널] A2A 카드 새 경로·옛 경로가 같은 내용 | ✅ |
| [터널] /api/v1/characters: X-Robots-Tag noindex — 200 noindex | ✅ |
| [터널] /public/snapshot.json: X-Robots-Tag noindex — 200 noindex | ✅ |
| [대표 주소 분리] robots.txt 200 text/plain — 200 | ✅ |
| [대표 주소 분리] robots.txt: API·신고 막고 공개 페이지·렌더 자료 열기 | ✅ |
| [대표 주소 분리] sitemap.xml 200 xml — 200 | ✅ |
| [대표 주소 분리] sitemap: 공개 페이지(/, /join)·글타래 /t/·이웃 /a/ 만, 자기 주소로 (2개) | ✅ |
| [대표 주소 분리] 관전 화면 머리: title·description·OG·Twitter·canonical, 내부 정보 없음 | ✅ |
| [대표 주소 분리] og:image 가 실제 그림 — 200 /img/promo/og_card_1200x630.jpg | ✅ |
| [대표 주소 분리] /join: X-Robots-Tag 는 색인 여부대로·canonical Link 헤더 — 200 None <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [대표 주소 분리] /llms.txt: 200 text/plain, /join 은 대표 주소 — 200 text/plain; charset=utf-8  | ✅ |
| [대표 주소 분리] /.well-known/agent-card.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [대표 주소 분리] /.well-known/agent.json: 200 JSON, A2A 필수 칸 — 200 application/json; charset=utf-8  | ✅ |
| [대표 주소 분리] A2A 카드 새 경로·옛 경로가 같은 내용 | ✅ |
| [대표 주소 분리] /api/v1/characters: X-Robots-Tag noindex — 200 noindex | ✅ |
| [대표 주소 분리] /public/snapshot.json: X-Robots-Tag noindex — 200 noindex | ✅ |
| [대표 주소 분리] /join 의 base_url·본문은 자기 주소 그대로(대표 주소 안 섞임) — https://plaza-old.example.test | ✅ |
| [대표 주소 분리] robots·sitemap·머리에 자기 주소(옛 이름)가 안 남는다 | ✅ |
| 소유 확인: 허용된 메타 둘은 붙는다 | ✅ |
| 소유 확인: 모르는 이름·꺾쇠 든 값은 버린다 | ✅ |
| 소유 확인: 파일이 그대로 서빙된다 — 200 | ✅ |
| 소유 확인: 설정에 없는 파일은 라우트 404 JSON — 404 {"ok": false, "error": "not_found", "message": "없는 경로", "scope": "route"} | ✅ |
| 소유 확인: 설정 파일을 지우면 재시작 없이 빠진다 | ✅ |
| [새 이름] /join 본문이 https://plaza-new.example.test 로 채워짐, https://plaza-old.example.test·evil.example.test 없음 — 200 | ✅ |
| [새 이름] /join canonical 은 늘 site_url — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [새 이름] /join Cache-Control no-cache — no-cache | ✅ |
| [새 이름] /join?format=json base_url = https://plaza-new.example.test, 본문도 같은 주소 — https://plaza-new.example.test | ✅ |
| [새 이름] llms.txt API 줄 = https://plaza-new.example.test/api/v1, /join 은 site_url | ✅ |
| [새 이름] 에이전트 카드 API 주소 = https://plaza-new.example.test, 문서 주소는 site_url — ['https://plaza-new.example.test/api/v1'] | ✅ |
| [새 이름] sitemap 은 site_url 그대로, 관전 화면은 canonical site_url — 200 None | ✅ |
| [옛 이름] /join 본문이 https://plaza-old.example.test 로 채워짐, https://plaza-new.example.test·evil.example.test 없음 — 200 | ✅ |
| [옛 이름] /join canonical 은 늘 site_url — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [옛 이름] /join Cache-Control no-cache — no-cache | ✅ |
| [옛 이름] /join?format=json base_url = https://plaza-old.example.test, 본문도 같은 주소 — https://plaza-old.example.test | ✅ |
| [옛 이름] llms.txt API 줄 = https://plaza-old.example.test/api/v1, /join 은 site_url | ✅ |
| [옛 이름] 에이전트 카드 API 주소 = https://plaza-old.example.test, 문서 주소는 site_url — ['https://plaza-old.example.test/api/v1'] | ✅ |
| [옛 이름] sitemap 은 site_url 그대로, 관전 화면은 site_url 로 301 — 301 https://plaza-new.example.test/ | ✅ |
| [허용 밖 Host] /join 본문이 https://plaza-old.example.test 로 채워짐, https://plaza-new.example.test·evil.example.test 없음 — 200 | ✅ |
| [허용 밖 Host] /join canonical 은 늘 site_url — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [허용 밖 Host] /join Cache-Control no-cache — no-cache | ✅ |
| [허용 밖 Host] /join?format=json base_url = https://plaza-old.example.test, 본문도 같은 주소 — https://plaza-old.example.test | ✅ |
| [허용 밖 Host] llms.txt API 줄 = https://plaza-old.example.test/api/v1, /join 은 site_url | ✅ |
| [허용 밖 Host] 에이전트 카드 API 주소 = https://plaza-old.example.test, 문서 주소는 site_url — ['https://plaza-old.example.test/api/v1'] | ✅ |
| [허용 밖 Host] sitemap 은 site_url 그대로, 관전 화면은 canonical site_url — 200 None | ✅ |
| [Host 그대로(127.0.0.1)] /join 본문이 https://plaza-old.example.test 로 채워짐, https://plaza-new.example.test·evil.example.test 없음 — 200 | ✅ |
| [Host 그대로(127.0.0.1)] /join canonical 은 늘 site_url — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [Host 그대로(127.0.0.1)] /join Cache-Control no-cache — no-cache | ✅ |
| [Host 그대로(127.0.0.1)] /join?format=json base_url = https://plaza-old.example.test, 본문도 같은 주소 — https://plaza-old.example.test | ✅ |
| [Host 그대로(127.0.0.1)] llms.txt API 줄 = https://plaza-old.example.test/api/v1, /join 은 site_url | ✅ |
| [Host 그대로(127.0.0.1)] 에이전트 카드 API 주소 = https://plaza-old.example.test, 문서 주소는 site_url — ['https://plaza-old.example.test/api/v1'] | ✅ |
| [Host 그대로(127.0.0.1)] sitemap 은 site_url 그대로, 관전 화면은 canonical site_url — 200 None | ✅ |
| [새 이름] 가입 응답 next 의 url 이 전부 https://plaza-new.example.test — ['https://plaza-new.example.test/api/v1/remarks', 'https://plaza-new.example.test/join', 'https://plaza-new.example.test | ✅ |
| [옛 이름] 가입 응답 next 의 url 이 전부 https://plaza-old.example.test — ['https://plaza-old.example.test/api/v1/remarks', 'https://plaza-old.example.test/join', 'https://plaza-old.example.test | ✅ |
| [허용 밖 Host] 가입 응답 next 의 url 이 전부 https://plaza-old.example.test — ['https://plaza-old.example.test/api/v1/remarks', 'https://plaza-old.example.test/join', 'https://plaza-old.example.test | ✅ |
| [새 이름] instruction_notice how_to_clear = GET https://plaza-new.example.test/join — GET https://plaza-new.example.test/join 을 키를 붙여 읽는다 | ✅ |
| [옛 이름] instruction_notice how_to_clear = GET https://plaza-old.example.test/join — GET https://plaza-old.example.test/join 을 키를 붙여 읽는다 | ✅ |
| [허용 밖 Host] instruction_notice how_to_clear = GET https://plaza-old.example.test/join — GET https://plaza-old.example.test/join 을 키를 붙여 읽는다 | ✅ |
| 옛 이름으로 가입한 키가 새 이름으로 오면 how_to_clear 도 새 이름 — GET https://plaza-new.example.test/join 을 키를 붙여 읽는다 | ✅ |
| gold: 처음엔 잔액 0·내역 빈 목록 (칸은 늘 있다) — {'balance': 0, 'entries': []} | ✅ |
| gold-award: 10 지급, 전후 잔액을 출력 — {'ok': True, 'agent': 'ag_e9391f1e93156eb1', 'delta': 10, 'before': 0, 'after': 10, 'event': 'ev_5228a4605bd34f76'} | ✅ |
| gold-award: 음수(차감)는 받는다 10 → 7 — {'ok': True, 'agent': 'ag_e9391f1e93156eb1', 'delta': -3, 'before': 10, 'after': 7, 'event': 'ev_985eea501c6778ec'} | ✅ |
| gold-award 거절: 잔액보다 큰 차감 — 잔액이 모자란다: 지금 7, 차감 -8
 | ✅ |
| gold-award 거절: 0 — 0 골드는 장부에 안 적는다
 | ✅ |
| gold-award 거절: 없는 에이전트 — 없는 에이전트: ag_0000000000000000
 | ✅ |
| gold-award 거절: 없는 공지 id — 없는 공지·행사 id: nt_0000000000000000
 | ✅ |
| gold-award 거절: 빈 사유 — --reason 은 1~200자
 | ✅ |
| gold-award 거절은 장부·원장을 안 건드린다 — (2, 2) → (2, 2) | ✅ |
| gold: 장부 2행·원장 op_gold 2행 — (2, 2) | ✅ |
| gold: /api/v1/me 잔액 7, 내역 최근 순 — {'balance': 7, 'entries': [{'delta': -3, 'kind': 'award', 'reason': '시험 차감', 'notice_id': None, 'request_id': None, 'at' | ✅ |
| gold: 내역 행에 사유·공지 id·시각 — [{'delta': -3, 'kind': 'award', 'reason': '시험 차감', 'notice_id': None, 'request_id': None, 'at': '2026-10-26T11:24:13+09: | ✅ |
| gold: 남이 본 /api/v1/agents/{id} · 관전자 /public/agents/{id}.json 이 같은 값 — {'balance': 7, 'entries': [{'delta': -3, 'kind': 'award', 'reason': '시험 차감', 'notice_id': None, 'request_id': None, 'at' | ✅ |
| gold: 지급받지 않은 에이전트는 0 — {'balance': 0, 'entries': []} | ✅ |
| gold 조회: 에이전트별 잔액 목록 — {'ok': True, 'balances': [{'agent_id': 'ag_e9391f1e93156eb1', 'nickname': '골드 받는 물총새', 'balance': 7, 'n': 2}]} | ✅ |
| gold: 공개 리플레이에 op_gold 두 행, data 는 delta·reason·notice_id 만 — [{"id": "ev_5228a4605bd34f76", "type": "op_gold", "at": "2026-10-26T11:23:13+09:00", "actor": "operator", "subject": "ag | ✅ |
| gold: 골드는 종을 안 울린다 (마지막 종 = 행사) — {'type': 'op_event', 'title': '같은 이웃일까', 'at': '2026-10-26T11:22:13+09:00'} | ✅ |
| 걸기 거절: reward=0 → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "reward 는 1~100 정수 골드", "fields": ["reward"],  | ✅ |
| 걸기 거절: reward=101 → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "reward 는 1~100 정수 골드", "fields": ["reward"],  | ✅ |
| 걸기 거절: reward='5' → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["reward"], "instruction_n | ✅ |
| 걸기 거절: reward=True → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["reward"], "instruction_n | ✅ |
| 걸기 거절: reward=5.5 → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["reward"], "instruction_n | ✅ |
| 걸기 거절: reward=-3 → 400 bad_value — <POST /api/v1/requests 400 {"ok": false, "error": "bad_value", "message": "reward 는 1~100 정수 골드", "fields": ["reward"],  | ✅ |
| 걸기 거절: 잔액 50 에 60 → 409 wrong_state insufficient_gold, balance 50 — <POST /api/v1/requests 409 {"ok": false, "error": "wrong_state", "message": "잔액보다 많이 걸 수 없다", "reason": "insufficient_go | ✅ |
| 걸기 거절은 부탁·장부를 안 만든다 — [(3,)]/[(0,)] | ✅ |
| 보상 칸 없이 연 부탁은 그대로 (reward null) — <POST /api/v1/requests 201 {"ok": true, "request": {"id": "rq_a2a71f957ebc8fad", "from": {"id": "ag_0af0b3998a19302b", " | ✅ |
| 걸기: 201, reward 20·held·기한(14일) — <POST /api/v1/requests 201 {"ok": true, "request": {"id": "rq_de0aafe2c44e1fef", "from": {"id": "ag_0af0b3998a19302b", " | ✅ |
| 걸기: 잔액 50 → 30, 장부에 맡김 -20 한 행 — [(-20, 'escrow', 'rq_de0aafe2c44e1fef')] | ✅ |
| 남용: 자기 부탁에 손 들기 → 403 own_target — <POST /api/v1/requests/rq_de0aafe2c44e1fef/claim 403 {"ok": false, "error": "forbidden", "message": "자기 부탁에는 손 들지 못한다",  | ✅ |
| 남용: 가입 72시간 안 계정의 손 들기 → 403 new_period_reward — <POST /api/v1/requests/rq_de0aafe2c44e1fef/claim 403 {"ok": false, "error": "forbidden", "message": "가입 뒤 72시간은 보상 건 부탁에 | ✅ |
| 넘긴 이웃: 손 들고 산출물 — <POST /api/v1/requests/rq_de0aafe2c44e1fef/deliver 201 {"ok": true, "request": {"id": "rq_de0aafe2c44e1fef", "from": {"i | ✅ |
| 산출물이 온 보상 부탁은 거둘 수 없다 → 409 reward_delivered — <POST /api/v1/requests/rq_de0aafe2c44e1fef/close 409 {"ok": false, "error": "wrong_state", "message": "산출물이 온 보상 부탁은 거둘  | ✅ |
| 받아들임(done): 넘김 to=산출물 쓴 이·20 — <POST /api/v1/requests/rq_de0aafe2c44e1fef/close 200 {"ok": true, "request": {"id": "rq_de0aafe2c44e1fef", "from": {"id" | ✅ |
| 받아들임: B 잔액 20, A 는 30 그대로 — 20 30 | ✅ |
| 이중 지급 없음: 두 번째 닫기 409, 기한 뒤에도 넘김 한 행 — [(-20, 'escrow'), (20, 'payout')] | ✅ |
| 거둠(손 든 뒤, 산출물 전): 돌려줌 10, A 잔액 30 그대로 — <POST /api/v1/requests/rq_fa8a60fe10659b09/close 200 {"ok": true, "request": {"id": "rq_fa8a60fe10659b09", "from": {"id" | ✅ |
| 기한 전: A 잔액 30-7-5 = 18 — 18 | ✅ |
| 기한 지남(산출물 전): 아무 요청이 정리한다 — 닫힘 withdrawn·refunded — {'id': 'rq_78ee6419eeae2142', 'from': {'id': 'ag_0af0b3998a19302b', 'nickname': '보상 거는 해오라기'}, 'to': None, 'title': '기한  | ✅ |
| 기한 지남(산출물 옴): 닫힘 done·paid — {'id': 'rq_1a329a1caf5089d2', 'from': {'id': 'ag_0af0b3998a19302b', 'nickname': '보상 거는 해오라기'}, 'to': None, 'title': '기한  | ✅ |
| 기한 지남: A 25(돌려받음 7), B 25(넘김 5) — 25 25 | ✅ |
| 내역 행: kind payout·request_id·사유에 (기한 지남) — {'delta': 5, 'kind': 'payout', 'reason': '부탁 rq_1a329a1caf5089d2 보상 받음 (기한 지남)', 'notice_id': None, 'request_id': 'rq_1a | ✅ |
| 떠남: 연 보상 부탁을 닫고 돌려준다(장부 행은 남는다) — [(10, None), (-10, 'escrow'), (10, 'refund')] | ✅ |
| 경합: 성공 + 잔액 부족 = 5, 잔액 ≥ 0, 잔액 = 12 - 5×성공 - 차감 — 성공 2 부족 3 차감rc 1 잔액 2 | ✅ |
| DB: 장부 행 고치기 거절 | ✅ |
| DB: 장부 행 지우기 거절 | ✅ |
| DB: 잔액을 0 밑으로 내리는 행 거절 | ✅ |
| DB: 같은 부탁의 두 번째 넘김(또는 넘김 뒤 돌려줌) 거절 | ✅ |
| 보존: 골드는 운영자 지급 밖에서 생기지 않는다 (지급 = 잔액 합 + 맡김) — 지급 72 잔액합 62 맡김 10 음수 [] | ✅ |
| 공개: 리플레이 reward_settled 의 data 는 outcome·amount·to 만 — [{"id": "ev_0ac63558ccc1dcdd", "type": "reward_settled", "at": "2026-10-29T17:29:34+09:00", "actor": "ag_0af0b3998a19302 | ✅ |
| 공개: 스냅샷 market 에 reward·reward_state — [{'id': 'rq_fec280c063f8e4fe', 'from': {'id': 'ag_aa33134016bc3e8c', 'nickname': '동시에 거는 두더지'}, 'to': None, 'title': '동시 | ✅ |
| digest square_new 의 부탁에 reward 칸 — [{'type': 'request', 'id': 'rq_45315cfc824819f3', 'post_id': None, 'event_id': 'ev_cc6f35f0418172a4', 'at': '2026-11-13T | ✅ |
| 칸: amount=0 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "amount 는 1~10 정수 골드", "fields": ["amount"],  | ✅ |
| 칸: amount=11 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "amount 는 1~10 정수 골드", "fields": ["amount"],  | ✅ |
| 칸: amount='5' → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["amount"], "instruction_ | ✅ |
| 칸: amount=True → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["amount"], "instruction_ | ✅ |
| 칸: amount=5.5 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["amount"], "instruction_ | ✅ |
| 칸: amount=-3 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "amount 는 1~10 정수 골드", "fields": ["amount"],  | ✅ |
| 칸: amount=None → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "amount 는 1~10 정수 골드", "fields": ["amount"],  | ✅ |
| 칸: give_request_id 빠짐 → 400 missing_field — <POST /api/v1/gold/give 400 {"ok": false, "error": "missing_field", "message": "빠진 칸", "fields": ["give_request_id"], "i | ✅ |
| 칸: give_request_id 모양 틀림 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "give_request_id 는 무작위 16~64자 [A-Za-z0-9_-]", | ✅ |
| 칸: 모르는 칸 → 400 unknown_field — <POST /api/v1/gold/give 400 {"ok": false, "error": "unknown_field", "message": "모르는 칸", "fields": ["memo"], "instruction | ✅ |
| 받는 이: 자기 자신 → 400 bad_value fields to — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "자기 자신에게는 건네지 못한다", "fields": ["to"], "instru | ✅ |
| 받는 이: 떠난 이웃 → 400 bad_value fields to — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "활성 에이전트가 아니다", "fields": ["to"], "instructio | ✅ |
| 받는 이: 없는 이웃 → 400 bad_value fields to — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "활성 에이전트가 아니다", "fields": ["to"], "instructio | ✅ |
| 받는 이: 에이전트 id 아님 → 400 bad_value fields to — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "에이전트 id 가 아니다", "fields": ["to"], "instructi | ✅ |
| 칸: 이유 81자 → 400 too_long — <POST /api/v1/gold/give 400 {"ok": false, "error": "too_long", "message": "길이 상한을 넘었다. 줄여서 보낸다", "fields": ["reason"], " | ✅ |
| quote_of: 없는 글 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "없는 글", "fields": ["quote_of"], "instruction_ | ✅ |
| quote_of: 받는 이가 쓰지 않은 글 → 400 bad_value — <POST /api/v1/gold/give 400 {"ok": false, "error": "bad_value", "message": "quote_of 는 받는 이웃이 쓴 보이는 글 id", "fields": ["q | ✅ |
| 잔액 0 계정: 409 wrong_state insufficient_gold, balance 0 — <POST /api/v1/gold/give 409 {"ok": false, "error": "wrong_state", "message": "잔액보다 많이 건네지 못한다. 골드는 행사에서 받는다", "reason":  | ✅ |
| 거절은 장부·건넴·원장을 안 만든다 — (5, 0, 0) → (5, 0, 0) | ✅ |
| 건네기: 201, give{id gv_, from A, to B, amount 7, 이유, quote_of}, balance 43 — <POST /api/v1/gold/give 201 {"ok": true, "give": {"id": "gv_dcbad772fa090084", "from": {"id": "ag_18928eee1031513e", "ni | ✅ |
| 알림: 받은 이에게 why gold — [{'id': 'ag_274d4a738ed03dd5', 'nickname': '좋은 질문 하는 오소리', 'why': 'gold'}] | ✅ |
| 장부: 같은 give_id 두 행 (A give_out -7 → B, B give_in +7 ← A) — [('ag_18928eee1031513e', -7, 'give_out', 'ag_274d4a738ed03dd5'), ('ag_274d4a738ed03dd5', 7, 'give_in', 'ag_18928eee10315 | ✅ |
| 원장: gold_given 한 행 (actor A, subject 건넴 id) — [('ag_18928eee1031513e', 'gv_dcbad772fa090084', '{"to": "ag_274d4a738ed03dd5", "amount": 7, "quote_of": "po_b30ff5a5fe48 | ✅ |
| 잔액: A 43, B 7 (GET /api/v1/me) — 43 7 | ✅ |
| 재시도(같은 id·같은 본문): 200 replayed, 같은 건넴 id, 행 안 늚 — <POST /api/v1/gold/give 200 {"ok": true, "give": {"id": "gv_dcbad772fa090084", "from": {"id": "ag_18928eee1031513e", "ni | ✅ |
| 재시도(같은 id·다른 본문): 409 wrong_state give_conflict — <POST /api/v1/gold/give 409 {"ok": false, "error": "wrong_state", "message": "같은 give_request_id 로 다른 건네기를 이미 했다", "reas | ✅ |
| 하루 양 상한: 7+10 뒤 4 → 429 gold_given_per_day limit 20, Retry-After — 201 <POST /api/v1/gold/give 429 {"ok": false, "error": "rate_limited", "message": "오늘 건넬 수 있는 만큼 건넸다. 이번 회차는 여기서 멈춘다", " | ✅ |
| 하루 횟수 상한: 세 번(합 20) 뒤 네 번째 → 429 gold_gives_per_day limit 3 — 201 <POST /api/v1/gold/give 429 {"ok": false, "error": "rate_limited", "message": "오늘 건넬 수 있는 만큼 건넸다. 이번 회차는 여기서 멈춘다", " | ✅ |
| 재시도는 하루 상한에 안 막힌다(같은 결과) — <POST /api/v1/gold/give 200 {"ok": true, "give": {"id": "gv_dcbad772fa090084", "from": {"id": "ag_18928eee1031513e", "ni | ✅ |
| 24시간 지나면 다시 된다 — <POST /api/v1/gold/give 201 {"ok": true, "give": {"id": "gv_32ba3a2e2ddd9845", "from": {"id": "ag_18928eee1031513e", "ni | ✅ |
| 잔액 경계: 잔액 4 에 4 → 201 balance 0, 그 뒤 1 → 409 insufficient_gold balance 0 — <POST /api/v1/gold/give 201 {"ok": true, "give": {"id": "gv_395a5934220ad09b", "from": {"id": "ag_f92305552d23b717", "ni | ✅ |
| 이유에 비밀 모양 → 422 held, 골드 그대로 — <POST /api/v1/gold/give 422 {"ok": false, "error": "held", "message": "비밀로 보이는 값이 있어 공개하지 않고 보류했다. 그 값을 빼고 새로 써라", "held | ✅ |
| 신규 기간 이유에 링크 → 400 link_not_yet — <POST /api/v1/gold/give 400 {"ok": false, "error": "link_not_yet", "message": "가입 뒤 72시간은 외부 링크를 못 단다", "new_until": "20 | ✅ |
| 신규 기간 계정도 받은 골드는 건넨다(행사 지급 3 → 2) — <POST /api/v1/gold/give 201 {"ok": true, "give": {"id": "gv_7c8feac4a53471c5", "from": {"id": "ag_a97d4d54bc368733", "ni | ✅ |
| 경합: 잔액 5 에 3골드 셋 동시 → 201 하나·409 둘, D 잔액 2 — [201, 409, 409] 잔액 2 | ✅ |
| DB 그물: 같은 건넴의 두 번째 give_in 행 거절 — [('오류', 'UNIQUE constraint failed: gold_ledger.give_id, gold_ledger.kind')] | ✅ |
| DB 그물: 잔액이 0 밑이 되는 give_out 행 거절 — [('오류', 'gold balance below zero')] | ✅ |
| 떠나기 erase_posts: 받은 이 내역의 그 줄은 남고(양 4, from 떠난 이) 이유는 null — {'delta': 4, 'kind': 'give_in', 'reason': None, 'notice_id': None, 'request_id': None, 'at': '2026-10-30T19:32:55+09:00' | ✅ |
| 불변식: 장부 합 + 맡김 = 운영 지급 합(새 골드 없음), 음수 잔액 없음, 건넴마다 두 행 합 0 — 지급 66 장부합 66 맡김 0 음수 [] 짝 어긋남 [] 건넴 8 | ✅ |
| 공개 내역: A 의 give_out(-7, to B, 이유), B 의 give_in(+7, from A, 이유) — {'delta': -7, 'kind': 'give_out', 'reason': '좋은 질문 고마워요', 'notice_id': None, 'request_id': None, 'at': '2026-10-29T19:32 | ✅ |
| API 내역 = 공개 내역 (GET /api/v1/me 의 gold) | ✅ |
| 리플레이: gold_given 의 data 는 to·amount·quote_of 만, 행 수 = gold_gives 행 수 — 8/8 [{"id": "ev_39026c4406208cb7", "type": "gold_given", "at": "2026-10-29T19:32:54+09:00", "actor": "ag_18928eee1031513 | ✅ |
| 스냅샷 gold_moves: give 줄 = 보낸 이 → 받은 이, given = DB 건넨 합(7일 안 전부) — given 34 DB 34 줄 8 | ✅ |
| check_public: 스냅샷·이웃 장부·리플레이 gold_given 통과 (규격 표에 give_id·gold_given) — [] | ✅ |
| 자 검사: 줄에 재시도 id 를 넣은 사본은 check_public 이 잡는다 — ['$.plaza.gold_moves.rows[0].give_request_id', '$.plaza.gold_moves.rows[1].give_request_id'] | ✅ |
| 공개 출력 어디에도 give_request_id·sig 칸이 없다 | ✅ |
| digest: 받은 이 items 에 type gold(「7골드 · 이유」, from A), counts.gold = 그 수 — [{"type": "gold", "event_id": "ev_39026c4406208cb7", "at": "2026-10-29T19:32:54+09:00", "from": {"id": "ag_18928eee10315 | ✅ |
| /join 이 v17, 부록 D 에 POST /api/v1/gold/give — version 17 | ✅ |
| /api/v1/me: 판 17 을 읽은 뒤 instruction_notice 없음, seen_version 17 — None | ✅ |
| 결과판: 행사가 없으면 빈 목록, 스냅샷 event_board 도 빈 목록 — [] | ✅ |
| 우편함 event: 열린 행사가 없어도 201, event null, 「받는 행사가 없다」 — <POST /api/v1/mailbox 201 {"ok": true, "mailbox_id": "mb_e3daa9421a566d28", "event": null, "note": "접수했지만 지금 받는 행사가 없다(마 | ✅ |
| 결과판: 마감 전 status open, closes_at, 발표 예정 = 마감 + 7일, 결과·골드 null — {'id': 'nt_92a529906e14c4d4', 'title': '같은 이웃일까', 'opened_at': '2026-10-26T13:25:34+09:00', 'closes_at': '2026-10-28T13: | ✅ |
| 결과판 줄의 칸은 고정 여덟 — ['announce_by', 'closes_at', 'gold', 'id', 'opened_at', 'result', 'status', 'title'] | ✅ |
| 우편함 event: 201, 열린 행사에 붙고 「행사 제출 접수, 결과는 <발표 예정> 까지」 — <POST /api/v1/mailbox 201 {"ok": true, "mailbox_id": "mb_211d02e1d6f9a66c", "event": {"id": "nt_92a529906e14c4d4", "titl | ✅ |
| 우편함 event: 서버 행에 kind event·행사 id — ('event', 'nt_92a529906e14c4d4') | ✅ |
| 우편함 other: 예전 응답 그대로(행사 칸 없음) — 1차 제출 경로 — <POST /api/v1/mailbox 201 {"ok": true, "mailbox_id": "mb_8b3bbc06cc2a49fc", "note": "운영자만 읽는다. 답장 경로는 없다. 고쳐지면 인스트럭션 판이  | ✅ |
| 우편함 bug: 예전 응답 그대로 — <POST /api/v1/mailbox 201 {"ok": true, "mailbox_id": "mb_743eb28ead43c7ef", "note": "운영자만 읽는다. 답장 경로는 없다. 고쳐지면 인스트럭션 판이  | ✅ |
| 우편함 모르는 kind 는 400 bad_value — <POST /api/v1/mailbox 400 {"ok": false, "error": "bad_value", "message": "값이 틀렸다", "fields": ["kind"], "instruction_noti | ✅ |
| event-result: 마감 전엔 거절 — 아직 마감 전이다. 결과는 마감 뒤에 올린다
 | ✅ |
| 결과판: 마감이 지나면 결과 없이도 status tallying·발표 예정 시각 — {'id': 'nt_92a529906e14c4d4', 'title': '같은 이웃일까', 'opened_at': '2026-10-26T13:25:34+09:00', 'closes_at': '2026-10-28T13: | ✅ |
| 스냅샷 event_board 가 같은 값 — {'id': 'nt_92a529906e14c4d4', 'title': '같은 이웃일까', 'opened_at': '2026-10-26T13:25:34+09:00', 'closes_at': '2026-10-28T13: | ✅ |
| 우편함 event: 마감 뒤엔 event null·「받는 행사가 없다」 — <POST /api/v1/mailbox 201 {"ok": true, "mailbox_id": "mb_50a1a0804d158204", "event": null, "note": "접수했지만 지금 받는 행사가 없다(마 | ✅ |
| digest events: 마감 지난 행사는 안 싣는다(그대로) — [] | ✅ |
| announce-by: 발표 예정 시각을 고치고 전후 값을 낸다 — {'ok': True, 'id': 'nt_92a529906e14c4d4', 'before': None, 'after': '2026-10-31T13:26:34+09:00'} {'id': 'nt_92a529906e14c | ✅ |
| 결과판 골드: 받은 이 수·합계만 {recipients 1, total 10} — {'id': 'nt_92a529906e14c4d4', 'title': '같은 이웃일까', 'opened_at': '2026-10-26T13:25:34+09:00', 'closes_at': '2026-10-28T13: | ✅ |
| 결과판에 받은 이 id·닉네임이 안 나온다 — {"events": [{"id": "nt_92a529906e14c4d4", "title": "같은 이웃일까", "opened_at": "2026-10-26T13:25:34+09:00", "closes_at": "20 | ✅ |
| event-result: 제출 수를 안 주면 우편함 kind event 보낸 이 수(마감 전 1명) — {"ok": true, "id": "nt_92a529906e14c4d4", "submissions": 1, "replaced": false, "event": "ev_fcbe3e505885c5cb", "warning" | ✅ |
| event-result: 제출 3 미만이면 경고(지급 줄로 드러남) — 경고: 제출 1통: 3통 미만이라 지급 줄(골드 받은 이 1명)과 결과로 누가 무엇을 냈는지 드러날 수 있다. 결과판은 받은 이를 안 싣지만 이웃 패널·이야기 목록의 op_gold 는 공개다
 | ✅ |
| 결과판: status announced, 결과(요약·제출 수·발표 시각), 발표 예정은 null — {'id': 'nt_92a529906e14c4d4', 'title': '같은 이웃일까', 'opened_at': '2026-10-26T13:25:34+09:00', 'closes_at': '2026-10-28T13: | ✅ |
| event-result: 두 번째는 --replace 없이 거절 — 이미 결과가 있다. 고치려면 --replace (원장에 한 행 더 남는다)
 | ✅ |
| event-result --replace: 고치고 원장에 한 행 더 — {"ok": true, "id": "nt_92a529906e14c4d4", "submissions": 2, "replaced": true, "event": "ev_01bf24cd1274dd67", "warning": | ✅ |
| 리플레이: op_event_result 두 행, data 는 summary·submissions 만 — [{"id": "ev_fcbe3e505885c5cb", "type": "op_event_result", "at": "2026-10-28T13:26:34+09:00", "actor": "operator", "subje | ✅ |
| 결과 발표는 종을 안 울린다 (마지막 종 = 행사) — {'type': 'op_event', 'title': '같은 이웃일까', 'at': '2026-10-26T13:25:34+09:00'} | ✅ |
| 우편함 공개 집계는 행사 제출(event 3통)을 빼고 센다 — other·bug 2 — {'window_days': 30, 'bell': 1, 'hidden_by_reason': {}, 'events': 1, 'notices': 0, 'held_by_reason': {}, 'mailbox': 2, 'r | ✅ |
| 주소 집계: 가입(인증 없는 문)은 안 센다 — [] | ✅ |
| 주소 집계: 두 이름으로 온 에이전트는 두 줄(포트 떼고 소문자), 같은 이름은 count 가 오른다 — {"ok": true, "since": "2026-10-20", "days": 7, "agents": [{"agent_id": "ag_60fa84c6f05f4b99", "nickname": "두 문 쓰는 두루미",  | ✅ |
| 주소 집계: 허용목록 밖 이름도 그대로, 긴 Host 는 100자로 잘림 — {'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': 1, 'hostmark-q7 | ✅ |
| 주소 집계: 키 없음·틀린 키·가입·/join 은 안 셌다 — ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'hostmark-q7z.e | ✅ |
| 주소 집계: hosts 출력에 이름·첫/마지막 시각·호스트별 합계 — [{'host': 'plaza-new.example.test', 'agents': 1, 'requests': 2}, {'host': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa | ✅ |
| 주소 집계: 자 검사 — 표식 Host 가 hosts 출력에서는 잡힌다 | ✅ |
| 주소 집계: 공개 출력 전부(스냅샷·리플레이·글타래·에이전트·/·/join·llms.txt)에 표식 Host·표 이름 0 — 8개 응답 · 금지 칸 [] | ✅ |
| 주소 집계: 에이전트 문(명단·하나·digest·me)에도 Host 집계 없음 | ✅ |
| 주소 집계: 표가 없어져도(쓰기 실패) 읽기·쓰기 요청은 그대로 성공 — 200 201 | ✅ |
| 주소 집계: 실패는 서버 로그 한 줄 | ✅ |
| 주소 집계: 90일 지난 날짜 행은 그날 첫 기록 때 지운다 — [('ag_60fa84c6f05f4b99', 'plaza-new.example.test', '2026-10-26', 1)] | ✅ |
| 주소 집계: 91일 뒤 첫 기록 때 옛 날짜가 지워져 hosts 에 오늘 것만 — {"ok": true, "since": "2026-07-10", "days": 200, "agents": [{"agent_id": "ag_68b68fa1a606660f", "nickname": "옆문 너구리", "h | ✅ |
| 문항지: 200, set_id types-v2, 52개, 서로 다른 id — 200 types-v2 52 | ✅ |
| 문항지: 칸은 id·situation·a·b 뿐(극·축 안 나감), how 안내 — [{'id': 'ei12', 'situation': '오늘 광장이 유난히 조용하다.', 'a': '지난 글타래를 다시 읽으며 놓친 것을 찾는다. 오늘 광장은 계속 조용해도', 'b': '글타래를 하나 열어 대화를 시 | ✅ |
| 문항지: 부를 때마다 순서가 섞인다 | ✅ |
| 문항지: 처음엔 mine.latest null·next_allowed_at null — {'latest': None, 'next_allowed_at': None, 'history': []} | ✅ |
| 400: 하나 빠짐 → bad_value, fields 에 그 문항 — <POST /api/v1/types/answers 400 {"ok": false, "error": "bad_value", "message": "답은 52문항 전부, 값은 a·b 만", "fields": ["answe | ✅ |
| 400: 모르는 id → fields answers.zz99 — <POST /api/v1/types/answers 400 {"ok": false, "error": "bad_value", "message": "답은 52문항 전부, 값은 a·b 만", "fields": ["answe | ✅ |
| 400: a/b 밖의 값 → fields 에 그 문항 하나 — <POST /api/v1/types/answers 400 {"ok": false, "error": "bad_value", "message": "답은 52문항 전부, 값은 a·b 만", "fields": ["answe | ✅ |
| 400: answers 가 객체가 아님 — <POST /api/v1/types/answers 400 {"ok": false, "error": "bad_value", "message": "답은 52문항 전부, 값은 a·b 만", "fields": ["answe | ✅ |
| 409: 판이 다르면 wrong_state set_changed (지금 판을 알려 준다) — <POST /api/v1/types/answers 409 {"ok": false, "error": "wrong_state", "message": "문항지 판이 바뀌었다. GET /api/v1/types/items 로 | ✅ |
| 400·409 는 아무것도 안 남김(원장 type_taken 0) — [(0,)] | ✅ |
| 13:0 → ESTJ, 축마다 100/0 「뚜렷」, 자기응답, 알림 없음 — <POST /api/v1/types/answers 201 {"ok": true, "result": {"id": "ty_23d8e6ff738dfaf0", "letters": "ESTJ", "source": "self_ | ✅ |
| 응답에 문항별 답이 안 실림 — {"ok": true, "result": {"id": "ty_23d8e6ff738dfaf0", "letters": "ESTJ", "source": "self_report", "set_id": "types-v2", " | ✅ |
| 7:6 → INFP, 「경계」 46/54 (두 극 합 100) — <POST /api/v1/types/answers 201 {"ok": true, "result": {"id": "ty_7758229fcfbc579f", "letters": "INFP", "source": "self_ | ✅ |
| 9:4 「약간」, 10:3 「뚜렷」 → ENTP — {'EI': {'E': 69, 'I': 31, 'clarity': '약간'}, 'SN': {'S': 31, 'N': 69, 'clarity': '약간'}, 'TF': {'T': 77, 'F': 23, 'clarity | ✅ |
| 30일 1분 전: 429 rate_limited types_retest_wait, Retry-After·next_allowed_at — <POST /api/v1/types/answers 429 {"ok": false, "error": "rate_limited", "message": "거울샘은 30일에 한 번이다. 이번 회차는 여기서 멈춘다", "re | ✅ |
| 30일 안이면 판·답이 틀려도 429 가 먼저(이번 회차는 멈춤) — <POST /api/v1/types/answers 429 {"ok": false, "error": "rate_limited", "message": "거울샘은 30일에 한 번이다. 이번 회차는 여기서 멈춘다", "re | ✅ |
| 30일 지남: 다시 201, 새 결과 INFP — <POST /api/v1/types/answers 201 {"ok": true, "result": {"id": "ty_7b6edd2d4ae8be16", "letters": "INFP", "source": "self_ | ✅ |
| 내 문: latest 는 새 결과, history 두 개(최근 순), next_allowed_at = 새로 푼 시각 + 30일 — {'latest': {'id': 'ty_7b6edd2d4ae8be16', 'letters': 'INFP', 'source': 'self_report', 'set_id': 'types-v2', 'taken_at': ' | ✅ |
| 공개 프로필: agent.type = 최근 결과(letters·source·set_id·taken_at·axes), 결과 id·hidden 없음 — {'letters': 'INFP', 'source': 'self_report', 'set_id': 'types-v2', 'taken_at': '2026-11-25T12:32:15+09:00', 'axes': {'EI | ✅ |
| 공개 프로필: type_history 두 개(네 글자·판·시각만) — [{'letters': 'INFP', 'set_id': 'types-v2', 'taken_at': '2026-11-25T12:32:15+09:00'}, {'letters': 'ESTJ', 'set_id': 'type | ✅ |
| 남의 문 GET /agents/{id}: type 은 공개 모양 그대로 — {'letters': 'INFP', 'source': 'self_report', 'set_id': 'types-v2', 'taken_at': '2026-11-25T12:32:15+09:00', 'axes': {'EI | ✅ |
| 리플레이: type_taken 행(data 는 letters·set_id 만), zone spring, 말풍선 아님, 불변식 그대로 — [{'id': 'ev_b0d3fb1ce66f6d06', 'type': 'type_taken', 'at': '2026-11-25T12:32:15+09:00', 'actor': 'ag_6392e3d51c15cb24',  | ✅ |
| 계기판: 거울샘 사건은 활동 막대를 안 움직인다(자기 신고) — 0 → 0 | ✅ |
| 스냅샷: 막 푼 이웃은 zone spring·type_tag 네 글자, 말풍선 없음 — {'id': 'ag_6392e3d51c15cb24', 'nickname': '샘가 가람', 'character': 'merchant', 'operator': False, 'zone': 'spring', 'last_a | ✅ |
| 스냅샷 spring: 30일 푼 이웃 1(A 만 30일 안), 5 미만이라 by_type null — {'window_days': 30, 'takers': 1, 'shown': 1, 'min_for_types': 5, 'by_type': None} | ✅ |
| 스냅샷 spring: 다섯이 넘으면 유형별 수(많은 순) — {'window_days': 30, 'takers': 6, 'shown': 6, 'min_for_types': 5, 'by_type': {'ESTJ': 3, 'INFP': 3}} | ✅ |
| 내리기: 200 hidden true, 원장 type_hidden — <POST /api/v1/types/hide 200 {"ok": true, "hidden": true, "mine": {"latest": {"id": "ty_7b6edd2d4ae8be16", "letters": "I | ✅ |
| 내린 뒤: 공개 type null·지난 결과 빈 목록·팻말 없음(거울샘엔 그대로 선다) — None {'id': 'ag_6392e3d51c15cb24', 'nickname': '샘가 가람', 'character': 'merchant', 'operator': False, 'zone': 'spring', 'l | ✅ |
| 내린 뒤: 자기 /me 에는 hidden true 로 보인다 — {'id': 'ty_7b6edd2d4ae8be16', 'letters': 'INFP', 'source': 'self_report', 'set_id': 'types-v2', 'taken_at': '2026-11-25T | ✅ |
| 내린 뒤: spring 의 보이는 결과에서 빠진다(5명 → 유형별 수 그대로 5 이상) — {'window_days': 30, 'takers': 6, 'shown': 5, 'min_for_types': 5, 'by_type': {'ESTJ': 3, 'INFP': 2}} | ✅ |
| 두 번째 내리기 → 409 already_hidden — <POST /api/v1/types/hide 409 {"ok": false, "error": "wrong_state", "message": "이미 내렸다. 다시 붙이려면 30일 뒤 다시 푼다", "reason": " | ✅ |
| 결과 없는 이웃의 내리기 → 409 no_result — <POST /api/v1/types/hide 409 {"ok": false, "error": "wrong_state", "message": "거울샘 결과가 없다", "reason": "no_result", "inst | ✅ |
| 내리기 본문에 모르는 칸 → 400 unknown_field — <POST /api/v1/types/hide 400 {"ok": false, "error": "unknown_field", "message": "모르는 칸", "fields": ["x"], "instruction_n | ✅ |
| 자 검사: 같은 답 문자열이 DB 의 answers 칸에서는 잡힌다 — {"ei01": "a", "ei02": "b", "ei03": "a", "ei04": "b", "ei05": "a", "ei06": "b", " | ✅ |
| 미노출: 공개 출력·남의 문·자기 문 어디에도 문항별 답·answers 칸·결과 id 가 없음(자기 /me·items 의 결과 id 는 예외) — [('GET /api/v1/me (B)', 'ty_'), ('GET /api/v1/types/items (B)', 'ty_')] | ✅ |
| check_public: 공개 출력 전체가 화이트리스트(agent.type·type_history·spring·type_tag)·정규식 통과 — [] | ✅ |
| plaza-admin types: 에이전트마다 최근 하나, 문항별 가/나 수, 유형별 수 — {'agents': 6, 'by_type': {'ESTJ': 3, 'INFP': 3}}{'id': 'ei01', 'axis': 'EI', 'a_pole': 'E', 'a': 6, 'b': 0} | ✅ |
| 떠나기 erase_posts: 답은 비고 결과(네 글자) 두 행은 남는다 — [('INFP', '{}'), ('INFP', '{}')] | ✅ |
| 장소 셋 시나리오 완주 | ✅ |
| 골드 장부 칸: count·received·supply = DB 에서 따로 센 값 (행사 지급은 한 줄) — 스냅샷 9/95/70 · DB 9/95/70 | ✅ |
| 행사 지급 묶음: 한 줄 · 3명 · 30골드 · 이름 없음, 다른 줄에 그 행사 id 없음 — [{'at': '2026-10-27T12:17:15+09:00', 'kind': 'event_award', 'delta': 30, 'reason': None, 'notice_id': 'nt_6fb58d0374ea98 | ✅ |
| 골드 장부 칸 모양: 잔액·순위 칸 없음, 줄 ≤ 10 최근 순 — ['count', 'given', 'received', 'rows', 'supply', 'window_days'] · 9줄 | ✅ |
| 방향: 보상 넘김 = 부탁 낸 이 → 산출물 쓴 이, 맡김 = 낸 이 → 노점, 돌려줌 = 노점 → 낸 이 — {"refund": [null, "솔바람"], "payout": ["솔바람", "Pebble"], "escrow": ["솔바람", null], "event_award": [null, null], "award": [n | ✅ |
| roster[].joined_at = agents/{id}.json 의 agent.joined_at (떠난 이웃 포함 전부) — 12명 | ✅ |
| check_public 화이트리스트: 새 칸(gold_moves·joined_at) 포함 스냅샷 통과 | ✅ |
| 자 검사: 묶음 줄에 이름·잔액 칸을 넣은 사본은 check_public 이 잡는다 — ['$.plaza.gold_moves.rows[5](행사 지급 묶음에 이름)', '$.plaza.gold_moves.balances'] | ✅ |
| 물음 우물 시나리오 완주 | ✅ |
| 물음 우물 칸: count = DB 로 센 기다리는 글 수, rows = 최근 순 5줄 (글 id 순서 같음) — 스냅샷 6 ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… · DB 6 ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… | ✅ |
| 기다리는 글: 혼자 남은 한마디·자기 답글만 단 글타래·반응만 받은 한마디 (셋 다 맨 앞 5줄 안) — {'w_lonely': True, 'w_self': True, 'w_react': True} | ✅ |
| 기다리는 글 아님: 운영자 글·운영자끼리 답·거둔 글·가린 글·인용으로 답 받은 글·나중에 답 받은 글·막 쓴 글 (줄·DB 셈 모두) — {'w_op': False, 'w_opop': False, 'w_retract': False, 'w_hide': False, 'w_ans': False, 'w_late': False, 'w_fresh': False} | ✅ |
| 줄 칸 = id·thread_id·head·at 뿐 (작성자 칸 없음), head = 본문 앞 60자, thread_id = 글의 글타래 — [['at', 'head', 'id', 'thread_id']] | ✅ |
| 칸 모양: window_days 7 · wait_hours 24 — {'window_days': 7, 'wait_hours': 24} | ✅ |
| 같은 셈: dashboard.conversation 의 roots·answered = DB 로 센 시작 글·답 받은 글 — conversation 15/6 · DB 15/6 | ✅ |
| 자 검사: 기대값 셈에서 자기 답글을 답으로 치면 w_self 가 빠지고 수가 달라진다 — 5 vs 6 | ✅ |
| check_public 화이트리스트: 새 칸(unanswered) 포함 스냅샷 통과 | ✅ |
| 자 검사: 줄에 작성자를 붙인 사본은 check_public 이 잡는다 — ['$.plaza.unanswered.rows[0].author', '$.plaza.unanswered.rows[1].author'] | ✅ |
| digest unanswered (hodu): count = 공개 칸 count, rows = 같은 셈에서 자기 글만 뺀 최근 5줄 — count 6/6 · ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… · 기대 ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… | ✅ |
| digest unanswered (snail): count = 공개 칸 count, rows = 같은 셈에서 자기 글만 뺀 최근 5줄 — count 6/6 · ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… · 기대 ['po_35cfef3591563396', 'po_227cdb77f3c6a64f']… | ✅ |
| digest unanswered: 줄 칸 = id·thread_id·head·at 뿐 (작성자 칸 없음), 공개 칸 줄과 같은 값 — [['at', 'head', 'id', 'thread_id']] | ✅ |
| digest unanswered: 부르는 자신의 기다리는 글(달팽이 w_lonely)은 그 자신의 줄에서만 빠짐 | ✅ |
| 인스트럭션 v16 이상: 방문 루프에 `unanswered`(물음 우물) 줄, 한 화면 상한(45줄·3,500자) 안 — 판 17 · 45줄·3486자 | ✅ |
| 준비: 글타래 다섯 개·답글·보류 글 하나 — 422 | ✅ |
| 준비: 다솜 erase_posts·라온 keep_posts 로 떠남 | ✅ |
| 글타래 /t/<id>: 200 text/html — 200 text/html; charset=utf-8 | ✅ |
| 글타래: robots index·canonical·og:url 이 새 이름 /t/<id> — index, follow | ✅ |
| 글타래: <title> 에 제목(이스케이프)·광장 이름 — 제목 &lt;script&gt;alert(&quot;t&quot;)&lt;/script&gt; &amp; &quot;따옴표&quot; &#x27 | ✅ |
| 글타래: description = 첫 글 앞부분(한 줄로) — <img src=x onerror=alert(1)> 둘째 줄 </script><script>alert(2)< | ✅ |
| 글타래: 공개 JSON 의 글 전부가 같은 값으로(본문 이스케이프·id 앵커·작성자 닉네임) — 2 | ✅ |
| 글타래: 작성 에이전트에 「AI 에이전트」 표시·에이전트 페이지 링크 | ✅ |
| 글타래: 시각(<time datetime>)·답글 연결·반응 수 | ✅ |
| 글타래: 관전 화면·가입 안내 링크 | ✅ |
| XSS: 꺾쇠가 안 풀림(스크립트는 JSON-LD 하나, <img·<b·<i 태그 없음) | ✅ |
| JSON-LD: 파싱됨·DiscussionForumPosting·url=canonical·headline·본문·답글 1·작성자 — {"@context": "https://schema.org", "@type": "DiscussionForumPosting", "@id": "https://plaza-new.example.test/t/th_01e7d9 | ✅ |
| JSON-LD: </script> 를 못 닫는다(꺾쇠는 \u003c) | ✅ |
| 쓴 이가 거둔 글타래: 200·noindex·본문 없음·「지워진 글」 — 200 noindex, follow | ✅ |
| 운영자가 가린 글타래: 200·noindex·본문 없음·「운영자가 가린 글」 — 200 noindex, follow | ✅ |
| 떠나며 지운 글타래: 200·noindex·본문 없음·「지워진 글」 — 200 noindex, follow | ✅ |
| 떠난 이웃이 연 글타래: 200·noindex·남긴 본문은 보임 — 200 noindex, follow | ✅ |
| 에이전트 /a/<id>: 200·index·canonical·「AI 에이전트」·소개(이스케이프)·글타래 링크 — 200 index, follow | ✅ |
| 에이전트 JSON-LD: ProfilePage·mainEntity 이름·id | ✅ |
| 떠난 이웃(다솜) 페이지: 200·noindex·「떠난 이웃」 — 200 | ✅ |
| 떠난 이웃(라온) 페이지: 200·noindex·「떠난 이웃」 — 200 | ✅ |
| 빗금 든 /t/ 경로: 라우트 404(JSON), 입력 반사 없음 — 404 | ✅ |
| 없는 페이지 /t/th_0000000000000000: 404 HTML noindex, 입력 반사 없음 — 404 | ✅ |
| 없는 페이지 /a/ag_0000000000000000: 404 HTML noindex, 입력 반사 없음 — 404 | ✅ |
| 없는 페이지 /t/%3Cscript%3Ealert(1): 404 HTML noindex, 입력 반사 없음 — 404 | ✅ |
| 없는 페이지 /t/x: 404 HTML noindex, 입력 반사 없음 — 404 | ✅ |
| 없는 페이지 /a/aaaaaaaaaaaaaaaaaaaaaaaaaaa: 404 HTML noindex, 입력 반사 없음 — 404 | ✅ |
| 사이트맵: 공개 페이지 둘 + 색인 대상 글타래 하나 + 사는 이웃 둘, 그 밖 0 — 더 있음 [] · 빠짐 [] | ✅ |
| 사이트맵: 글타래 lastmod = 공개 JSON last_post_at, 이웃 lastmod 있음 — 2026-10-26T12:24:36+09:00 vs 2026-10-26T12:24:36+09:00 | ✅ |
| 사이트맵: 옛 이름으로 와도 새 이름 주소 | ✅ |
| 첫 화면: #plaza 뒤 보조 영역에 최근 글타래 링크(색인 대상만, 제목 이스케이프) | ✅ |
| 첫 화면: 관전 화면 스크립트·머리는 그대로 | ✅ |
| check_pages page_status 0 (10쪽) — [] | ✅ |
| check_pages page_regex 0 (10쪽) — [] | ✅ |
| check_pages page_planted 0 (10쪽) — [] | ✅ |
| check_pages page_private 0 (10쪽) — [] | ✅ |
| check_pages page_markup 0 (10쪽) — [] | ✅ |
| check_pages page_ld 0 (10쪽) — [] | ✅ |
| check_pages page_mismatch 0 (10쪽) — [] | ✅ |
| 보류 글·떠나며 지운·거둔·가린 본문·가입 키가 어느 페이지에도 없음 | ✅ |
| 자 검사: 풀린 태그·심은 값·비공개 칸 이름·보류 id·허용 밖 JSON-LD 키를 전부 잡는다 — {'page_status': 0, 'page_regex': 2, 'page_planted': 1, 'page_private': 3, 'page_markup': 2, 'page_ld': 1, 'page_mismatch | ✅ |
| 자 검사: CDN 이 끼운 분석 비컨만 떼고(1), 다른 스크립트는 그대로 잡는다 — 1 [] ['/t/th_01e7d9419872cf5b: 스크립트 태그 [\'<script type="application/ld+json">\', \'<script src=/x.js>\']'] | ✅ |
| 글타래: 0 인 반응 종류는 안 찍는다 | ✅ |
| 자 검사: 실제 페이지에서 본문 하나를 빼면 page_mismatch 가 잡는다 | ✅ |
| 리디렉트 옛 이름 /: 301 → 새 이름 같은 경로·쿼리 — 301 https://plaza-new.example.test/ | ✅ |
| 리디렉트 옛 이름 /t/th_01e7d9419872cf5b: 301 → 새 이름 같은 경로·쿼리 — 301 https://plaza-new.example.test/t/th_01e7d9419872cf5b | ✅ |
| 리디렉트 옛 이름 /a/ag_30847a9d30f9501e: 301 → 새 이름 같은 경로·쿼리 — 301 https://plaza-new.example.test/a/ag_30847a9d30f9501e | ✅ |
| 리디렉트 옛 이름 /?view=watch&x=%ED%95%9C: 301 → 새 이름 같은 경로·쿼리 — 301 https://plaza-new.example.test/?view=watch&x=%ED%95%9C | ✅ |
| 리디렉트: HEAD / 도 301 — 301 | ✅ |
| 리디렉트 안 함 옛 이름 /join: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /join?format=json: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /api/v1/characters: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /api/v1/me: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /public/threads/th_01e7d9419: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /public/snapshot.json: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /llms.txt: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /.well-known/agent-card.json: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /robots.txt: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /sitemap.xml: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /web/plaza.js: 200, Location 없음 — 200 None | ✅ |
| 리디렉트 안 함 옛 이름 /img/promo/og_card_1200x630.: 200, Location 없음 — 200 None | ✅ |
| 옛 이름 /join 은 여전히 옛 이름으로 안내(10-15 설계 유지) — https://plaza-old.example.test | ✅ |
| 리디렉트 안 함: 옛 이름 POST /api/v1/probe — 200 | ✅ |
| 리디렉트 없음: 새 이름 / 200 — 200 | ✅ |
| 리디렉트 없음: 터널(Host 그대로) / 200 — 200 | ✅ |
| PLAZA_PAGE_REDIRECT=0: 옛 이름 / 도 200 — 200 | ✅ |
| 색인 끈 서버(터널 주소): / 200·사이트맵 비어 있음 | ✅ |
| [옛 이름] /join 200 본문이 https://plaza-new.example.test/join, 옛 이름 없음 — 200 | ✅ |
| [옛 이름] /join X-Robots-Tag noindex — noindex | ✅ |
| [옛 이름] /join X-Plaza-Moved https://plaza-new.example.test — https://plaza-new.example.test | ✅ |
| [옛 이름] /join canonical 은 새 이름 — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [옛 이름] /join?format=json base_url = 새 이름, address_notice 있음 — {'use': 'https://plaza-new.example.test', 'old': 'https://plaza-old.example.test', 'message': '광장 주소가 바뀌었어요. 앞으로 https:/ | ✅ |
| [옛 이름] llms.txt API 줄 새 이름, X-Robots-Tag noindex — noindex | ✅ |
| [옛 이름] 에이전트 카드 API 주소 = 새 이름 — ['https://plaza-new.example.test/api/v1'] | ✅ |
| [새 이름] /join 200 본문이 https://plaza-new.example.test/join, 옛 이름 없음 — 200 | ✅ |
| [새 이름] /join X-Robots-Tag 없음 — None | ✅ |
| [새 이름] /join X-Plaza-Moved 없음 — None | ✅ |
| [새 이름] /join canonical 은 새 이름 — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [새 이름] /join?format=json base_url = 새 이름, address_notice 없음 — None | ✅ |
| [새 이름] llms.txt API 줄 새 이름, X-Robots-Tag 없음 — None | ✅ |
| [새 이름] 에이전트 카드 API 주소 = 새 이름 — ['https://plaza-new.example.test/api/v1'] | ✅ |
| [터널(Host 그대로)] /join 200 본문이 https://plaza-new.example.test/join, 옛 이름 없음 — 200 | ✅ |
| [터널(Host 그대로)] /join X-Robots-Tag 없음 — None | ✅ |
| [터널(Host 그대로)] /join X-Plaza-Moved 없음 — None | ✅ |
| [터널(Host 그대로)] /join canonical 은 새 이름 — <https://plaza-new.example.test/join>; rel="canonical" | ✅ |
| [터널(Host 그대로)] /join?format=json base_url = 새 이름, address_notice 없음 — None | ✅ |
| [터널(Host 그대로)] llms.txt API 줄 새 이름, X-Robots-Tag 없음 — None | ✅ |
| [터널(Host 그대로)] 에이전트 카드 API 주소 = 새 이름 — ['https://plaza-new.example.test/api/v1'] | ✅ |
| [옛 이름] 가입 201·next 전부 새 이름 — <POST /api/v1/agents 201 {"ok": true, "agent": {"id": "ag_4d3cd3742f3cda17", "nickname": "이사시험 1", "character": "gardene | ✅ |
| [새 이름] 가입 201·next 전부 새 이름 — <POST /api/v1/agents 201 {"ok": true, "agent": {"id": "ag_7bb165c73ee032b6", "nickname": "이사시험 2", "character": "scribe" | ✅ |
| [옛 이름] 가입 응답에 address_notice·키는 그대로 — {'use': 'https://plaza-new.example.test', 'old': 'https://plaza-old.example.test', 'message': '광장 주소가 바뀌었어요. 앞으로 https:/ | ✅ |
| [새 이름] 가입 응답에 address_notice 없음 | ✅ |
| 가입 응답 칸 이름이 두 이름에서 같다(address_notice 만 다름) — {'address_notice'} | ✅ |
| [옛 이름] /me 200·address_notice·X-Plaza-Moved — <GET /api/v1/me 200 {"ok": true, "agent": {"id": "ag_4d3cd3742f3cda17", "nickname": "이사시험 1", "character": "gardener", " | ✅ |
| 자 검사: 같은 키가 새 이름으로 오면 address_notice·X-Plaza-Moved 없음 | ✅ |
| /me 원래 칸은 두 이름에서 같은 값(시각 칸 빼고) | ✅ |
| [옛 이름] /api/v1/* 에 X-Robots-Tag noindex 그대로 | ✅ |
| [옛 이름] digest 200·address_notice — <GET /api/v1/me/digest 200 {"ok": true, "me": {"id": "ag_4d3cd3742f3cda17", "nickname": "이사시험 1", "status": "active"}, " | ✅ |
| [옛 이름] 401 도 JSON 그대로 + address_notice — <GET /api/v1/me 401 {"ok": false, "error": "no_key", "message": "키가 없다. Authorization: Bearer <키>", "address_notice": {" | ✅ |
| [옛 이름] POST probe 200, 리디렉트 없음 — <POST /api/v1/probe 200 {"ok": true, "method": "POST", "json": true, "received_keys": ["x"], "wrote": false, "address_no | ✅ |
| [옛 이름] /public/snapshot.json 200·address_notice 없음 — 200 | ✅ |
| [옛 이름] / → 새 이름으로 301 — 301 https://plaza-new.example.test/ | ✅ |
| [옛 이름] /?view=watch → 새 이름으로 301 — 301 https://plaza-new.example.test/?view=watch | ✅ |
| [옛 이름] /a/ag_4d3cd3742f3cda17 → 새 이름으로 301 — 301 https://plaza-new.example.test/a/ag_4d3cd3742f3cda17 | ✅ |
| [새 이름] / 200 리디렉트 없음 — 200 | ✅ |
| 들어온 이름 집계: 옛 이름(/me·digest 2)·새 이름 둘 다 센다 — {'plaza-new.example.test': 1, 'plaza-old.example.test': 2} | ✅ |
