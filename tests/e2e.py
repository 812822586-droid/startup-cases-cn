"""Playwright headless E2E test + screenshots.
Run: python tests/e2e.py   (needs `pip install playwright` and Chrome/Chromium)
"""
import sys, pathlib, json, http.server, threading, functools, socketserver
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent.parent
H = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
class Q(H.func):
    def log_message(self,*a): pass
srv = socketserver.TCPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT)))
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{port}/index.html"
data = json.load(open(ROOT/"cases.json"))
fails = []
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra)
    if not cond: fails.append(name)
with sync_playwright() as p:
    try: b = p.chromium.launch(headless=True)
    except Exception: b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width":1280,"height":900}, locale="zh-CN")
    pg = ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto(URL); pg.wait_for_selector(".card")
    check("total count shown", pg.inner_text("#totalCount")==str(len(data)), pg.inner_text("#totalCount"))
    check("category count", pg.inner_text("#catCount")==str(len({d['cat'] for d in data})))
    check("first page 24 cards", pg.locator(".card").count()==24)
    check("disclaimer visible", pg.locator("#disclaimer").is_visible() and "幸存者偏差" in pg.inner_text("#disclaimer"))
    pg.screenshot(path=str(ROOT/"screenshots/desktop.png"))
    # load more
    pg.click("#loadMore"); check("load more -> 48", pg.locator(".card").count()==48)
    while not pg.locator("#loadMore").is_hidden(): pg.click("#loadMore")
    check("load all", pg.locator(".card").count()==len(data))
    # search
    pg.fill("#searchInput","plausible"); check("search plausible", pg.locator(".card").count()>=1 and "Plausible" in pg.inner_text(".card-title"))
    pg.fill("#searchInput","不存在的关键词xyz"); check("search empty state", pg.locator(".card").count()==0 and pg.locator("#empty").is_visible())
    pg.fill("#searchInput","")
    # category
    pg.click('.chip[data-cat="游戏与应用"]'); n=pg.locator(".card").count()
    check("category chip", n==len([d for d in data if d['cat']=="游戏与应用"]), str(n))
    pg.click('.chip[data-cat="全部"]')
    # filters
    pg.select_option("#fCode","不需要"); n=pg.locator(".card").count(); check("filter 不需要写代码", n==min(24,len([d for d in data if d["code"]=="不需要"])), str(n))
    pg.click("#resetBtn")
    pg.select_option("#fCost","几乎为零"); n=pg.locator(".card").count(); check("filter cost", n>0)
    pg.click("#resetBtn")
    pg.select_option("#fRev","10 万美元以上"); n=pg.locator(".card").count(); check("filter revenue >=10万", n==len([d for d in data if d['rev'] and d['rev']>=100000]), str(n))
    pg.click("#resetBtn")
    pg.select_option("#fSort","rev"); first=pg.inner_text(".card .card-title")
    top=max([d for d in data if d['rev']], key=lambda d:d['rev'])['name']
    check("sort by revenue desc", first==top, first)
    pg.click("#resetBtn")
    # favorites
    pg.locator(".fav-btn").nth(0).click(); pg.locator(".fav-btn").nth(1).click()
    check("fav count 2", pg.inner_text("#favCount")=="2")
    ls = pg.evaluate("localStorage.getItem('startup-cases-favs-v1')"); check("favs persisted in localStorage", ls and len(json.loads(ls))==2)
    pg.click("#favOnlyBtn"); check("only favorites filter", pg.locator(".card").count()==2)
    pg.reload(); pg.wait_for_selector(".card"); check("favs survive reload", pg.inner_text("#favCount")=="2")
    pg.click("#favOnlyBtn"); check("fav-only toggles", pg.locator(".card").count()==2)
    pg.click("#favOnlyBtn")
    # modal
    pg.locator('[data-open]').first.click(); pg.wait_for_selector("#modal.open")
    check("modal opens", pg.is_visible("#modal.open"))
    txt = pg.inner_text("#modal")
    check("modal has sources + disclaimer", "来源" in txt and "幸存者偏差" in txt and pg.locator("#modalSrc a").count()>=1)
    pg.screenshot(path=str(ROOT/"screenshots/modal.png"))
    pg.keyboard.press("Escape"); check("modal closes on Esc", not pg.is_visible("#modal.open"))
    # modal on a case with revenue
    pg.fill("#searchInput","Transistor"); pg.locator('[data-open]').first.click()
    check("modal shows revenue note", "MRR" in pg.inner_text("#modalKv"))
    pg.screenshot(path=str(ROOT/"screenshots/modal-revenue.png"))
    pg.click("#modalClose"); pg.fill("#searchInput","")
    # dark mode
    pg.click("#themeBtn"); check("dark mode", pg.evaluate("document.documentElement.getAttribute('data-theme')")=="dark")
    pg.evaluate("window.scrollTo(0,0)"); pg.screenshot(path=str(ROOT/"screenshots/desktop-dark.png"))
    pg.click("#themeBtn")
    check("no JS errors", not errs, str(errs[:3]))
    ctx.close()
    # mobile
    m = b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="zh-CN")
    mp = m.new_page(); mp.goto(URL); mp.wait_for_selector(".card")
    sw = mp.evaluate("document.documentElement.scrollWidth"); cw = mp.evaluate("document.documentElement.clientWidth")
    check("mobile no horizontal overflow", sw<=cw+1, f"{sw}>{cw}")
    mp.screenshot(path=str(ROOT/"screenshots/mobile.png"))
    mp.locator('[data-open]').first.click(); mp.wait_for_selector("#modal.open")
    sw2 = mp.evaluate("document.querySelector('#modal .modal').scrollWidth"); cw2 = mp.evaluate("document.querySelector('#modal .modal').clientWidth")
    check("mobile modal no overflow", sw2<=cw2+1)
    mp.screenshot(path=str(ROOT/"screenshots/mobile-modal.png"))
    b.close()
srv.shutdown()
print("\nFAILED:" , fails) if fails else print("\nALL PASSED")
sys.exit(1 if fails else 0)
