"""README 샘플 화면(목업) 두 장을 다시 뜬다.

사용: python3 docs/screenshots/src/shoot.py
필요: pip install playwright && playwright install chromium (또는 설치된 Chrome)
출력: docs/screenshots/sample_plaza.png, docs/screenshots/sample_watch.png
"""
import pathlib
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent
SHOTS = [("plaza", 1776, 860), ("watch", 1600, 900)]

with sync_playwright() as p:
    try:
        browser = p.chromium.launch(channel="chrome")
    except Exception:
        browser = p.chromium.launch()
    for view, w, h in SHOTS:
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        page.goto((HERE / "sample.html").as_uri() + f"?view={view}")
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        dst = OUT / f"sample_{view}.png"
        page.screenshot(path=str(dst), full_page=False)
        print(dst.relative_to(OUT.parent.parent), w, h)
        page.close()
    browser.close()
