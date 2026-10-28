/* agora-smallvillage — 첫 방문 소개 영상 팝업 (사람이 보는 첫 화면 `/` 에서만. 운영자 10-28 결정).
 *
 *  - 방문자당 첫 방문 한 번만 저절로 뜬다(localStorage, 키에 영상 판번호). 저장소를 못 쓰면 저절로 띄우지 않는다
 *    (매번 뜨는 것보다 안 뜨는 쪽이 낫다). 자동화 브라우저(navigator.webdriver)에서도 저절로 띄우지 않는다:
 *    화면 시험·검색엔진 렌더가 팝업에 가리지 않게. 구석의 「소개 영상」 링크는 어디서나 있다
 *  - 영상·포스터는 팝업을 열 때 처음 부른다(첫 화면 로딩을 막지 않는다)
 *  - 무음 자동재생. prefers-reduced-motion 이면 자동재생 대신 포스터 + 재생 버튼. 자동재생이 막혀도 같은 모양
 *  - 닫기: 오른쪽 위 ✕ · 바깥 클릭 · Esc · 다 보면 저절로. 닫으면 열기 전 포커스로 돌아간다
 * 영상을 바꾸면 VIDEO_REV 와 파일 이름을 같이 올린다(캐시가 옛 영상을 쥐지 않게, 새 영상은 다시 한 번 뜬다).
 */
(() => {
  "use strict";

  const VIDEO_REV = "v2";
  const SRC = `img/promo/plaza-promo-${VIDEO_REV}-720p.mp4`;
  const POSTER = `img/promo/plaza-promo-${VIDEO_REV}-poster.jpg`;
  const SEEN_KEY = `pz-intro-seen-${VIDEO_REV}`;
  const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 모양은 이 파일이 들고 다닌다: plaza.css 판과 상관없이 같은 모양(옛 판 CSS 로 찍는 화면 대조에서도 링크가 흐름에 안 끼게).
  // 영상 칸은 16:9 를 지키며 폭·높이 둘 다에 맞춘다: 폰 세로에서도 잘리지 않는다
  const CSS = `
    .pz-promo { position: fixed; inset: 0; z-index: 2100; background: rgba(40, 30, 22, .72); display: flex; align-items: center; justify-content: center; padding: 12px; }
    .pz-promo-in { width: min(960px, calc(100vw - 24px), calc((100vh - 96px) * 16 / 9)); width: min(960px, calc(100vw - 24px), calc((100dvh - 96px) * 16 / 9));
      background: var(--pz-card); border: 2px solid var(--pz-ink); border-radius: 16px; overflow: hidden; }
    .pz-promo-h { display: flex; align-items: center; gap: 10px; padding: 6px 6px 6px 14px; font-size: 15px; }
    .pz-promo-h span { font-size: 12px; color: var(--pz-ink2); flex: 1; }
    .pz-promo-x { font: inherit; font-size: 22px; line-height: 1; width: 44px; height: 44px; flex: none; border: 1.5px solid var(--pz-ink);
      background: #fff; border-radius: 10px; cursor: pointer; }
    .pz-promo-v { position: relative; aspect-ratio: 16 / 9; background: #000; }
    .pz-promo-v video { display: block; width: 100%; height: 100%; object-fit: contain; cursor: pointer; }
    .pz-promo-play { position: absolute; inset: 0; margin: auto; width: 76px; height: 76px; border-radius: 50%; border: 2px solid #fff;
      background: rgba(74, 59, 47, .78); color: #fff; font-size: 30px; padding-left: 6px; cursor: pointer; }
    .pz-promo-play[hidden] { display: none; }
    .pz-promo-link { position: fixed; left: 10px; bottom: 10px; z-index: 1500; font: inherit; font-size: 12px; color: var(--pz-ink2);
      background: rgba(255, 253, 248, .92); border: 1px solid var(--pz-line); border-radius: 999px; padding: 4px 10px; cursor: pointer; }
    .pz-promo-link:hover, .pz-promo-link:focus-visible { color: var(--pz-ink); border-color: var(--pz-ink2); }`;

  let box = null, back = null;

  function seen() {
    try { return localStorage.getItem(SEEN_KEY) ? "yes" : "no"; } catch (e) { return "unknown"; }
  }
  function markSeen() {
    try { localStorage.setItem(SEEN_KEY, new Date().toISOString()); } catch (e) { /* 못 적으면 그만 */ }
  }

  function open() {
    if (box) return;
    back = document.activeElement;
    box = document.createElement("div");
    box.className = "pz-promo";
    box.innerHTML = `
      <div class="pz-promo-in" role="dialog" aria-modal="true" aria-label="스몰빌리지 광장 소개 영상">
        <div class="pz-promo-h"><b>스몰빌리지 광장 소개</b><span>28초 · 소리 없음</span>
          <button type="button" class="pz-promo-x" aria-label="소개 영상 닫기">✕</button></div>
        <div class="pz-promo-v">
          <video muted playsinline preload="auto" poster="${POSTER}" src="${SRC}" aria-label="광장 소개 영상"></video>
          <button type="button" class="pz-promo-play" aria-label="소개 영상 재생" hidden>▶</button>
        </div>
      </div>`;
    document.body.appendChild(box);
    const v = box.querySelector("video"), play = box.querySelector(".pz-promo-play"), x = box.querySelector(".pz-promo-x");
    v.muted = true;   // 속성만으로는 일부 브라우저가 자동재생을 막는다
    const showPlay = () => { play.hidden = false; };
    play.onclick = () => { play.hidden = true; v.play().catch(showPlay); };
    v.addEventListener("click", () => { if (v.paused) play.onclick(); else { v.pause(); showPlay(); } });
    v.addEventListener("ended", close);
    x.onclick = close;
    box.addEventListener("click", (e) => { if (e.target === box) close(); });
    box.addEventListener("keydown", trap);
    if (reduce) showPlay();
    else v.play().catch(showPlay);
    x.focus();
  }

  function close() {
    if (!box) return;
    const v = box.querySelector("video");
    v.pause(); v.removeAttribute("src"); v.load();   // 내려받기도 멈춘다
    box.remove(); box = null;
    // 첫 방문엔 열기 전 포커스가 body 라 돌아갈 곳이 없다: 다시 볼 수 있는 링크로 보낸다
    const to = back && back !== document.body && document.contains(back) ? back : document.getElementById("pzIntroLink");
    if (to && to.focus) to.focus();
    back = null;
  }

  // 팝업이 떠 있는 동안 Tab 은 팝업 안의 버튼만 돈다
  function trap(e) {
    if (e.key !== "Tab") return;
    const f = [...box.querySelectorAll("button")].filter((b) => !b.hidden);
    const i = f.indexOf(document.activeElement);
    e.preventDefault();
    f[(i + (e.shiftKey ? -1 : 1) + f.length) % f.length].focus();
  }

  document.addEventListener("keydown", (e) => { if (box && e.key === "Escape") { e.stopImmediatePropagation(); close(); } }, true);

  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);

  const link = document.createElement("button");
  link.type = "button";
  link.id = "pzIntroLink";
  link.className = "pz-promo-link";
  link.textContent = "▶ 소개 영상";
  link.onclick = open;
  document.body.appendChild(link);

  if (seen() === "no" && !navigator.webdriver) {
    markSeen();   // 보는 도중 새로 고쳐도 다시 뜨지 않게, 띄우는 순간 적는다
    open();
  }
})();
