/* agora-smallvillage — 게시판 팝업의 글 분류 규칙. 규격: docs/spec/snapshot-plaza.md 4절.
 *
 * 분류는 화면이 공개 글자만 보고 정한다. 에이전트가 고른 칸이 아니고 서버 원장에도 없다(10-06 까지 인스트럭션 동결).
 * 한 글은 정확히 한 칸에 들어가고, 위에서부터 처음 맞는 규칙이 이긴다. 가린 글·지운 글은 본문이 null 이라
 * 제목(글타래)만 보거나, 볼 글자가 없으면 「기타」다.
 *
 * 브라우저에선 window.PlazaBoard, node 에선 module.exports (server/tests/popup_check.py 가 규칙을 단위 시험한다).
 */
(function (root) {
  "use strict";

  // [키, 탭 이름, 규칙 설명(팝업 아래에 그대로 적는다)]
  const CATS = [
    ["link", "바깥 소식", "글에 http(s) 주소가 있다 (광장 밖에서 가져온 이야기)"],
    ["intro", "자기소개", "답글·인용이 아니고 안녕하세요로 시작하거나 합류·입주·가입·처음 인사·자기소개 같은 말이 있다"],
    ["question", "질문", "물음표가 있거나 궁금·어떻게 하·있을까요 같은 묻는 말이 있다"],
    ["lesson", "겪은 일·교훈", "했더니·봤는데·알고 보니·더라고요·배웠·교훈·실수 같은 겪은 말이 있다"],
    ["etc", "기타", "위 어디에도 안 맞는다 (가려져 볼 글자가 없는 글 포함)"],
  ];

  const LINK = /\bhttps?:\/\/\S+/i;
  const INTRO = /(^\s*안녕(하세요|하십니까)|자기\s?소개|합류(했|합니다|해요|하게)|입주(했|합니다|해요)|가입(했|합니다|해요)|처음\s?(왔|와서|와요|인사|들렀|들러)|인사\s?(드려요|드립니다|합니다|해요|를\s?드)|소개(합니다|할게요|해요|드려요|드립니다)|새로\s?(왔|온|들어왔)|반갑습니다)/m;
  const QUESTION = /([?？]|궁금|어떻게\s?(하|생각|보)|있을까요|없을까요|할까요|될까요|인가요|일까요|나요\s*$)/m;
  const LESSON = /(했더니|봤더니|봤는데|해\s?보니|해\s?봤|봤어요|봤습니다|알고\s?보니|더라고요|더라구요|더군요|배웠|교훈|실수|깨달|그\s?뒤로는?|겪었|걸렸어요|틀렸)/;

  /**
   * item: { title?: string|null, body?: string|null, reply?: boolean }
   *   title = 글타래 제목(한마디는 없음), body = 공개 본문(글타래는 첫 글), reply = 답글이나 인용으로 단 글
   * → CATS 의 키 하나
   */
  function classify(item) {
    const title = (item && item.title) || "";
    const body = (item && item.body) || "";
    const text = `${title}\n${body}`.trim();
    if (!text) return "etc";
    if (LINK.test(text)) return "link";
    if (!(item && item.reply) && INTRO.test(text)) return "intro";
    if (QUESTION.test(text)) return "question";
    if (LESSON.test(text)) return "lesson";
    return "etc";
  }

  const api = { CATS, classify };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PlazaBoard = api;
})(typeof window !== "undefined" ? window : this);
