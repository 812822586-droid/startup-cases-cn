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
    # 商业结构 chips (added 2026-11-10)
    bizs = ["信息差","流程差","职业差","其他"]
    check("biz chip row has 5 chips", pg.locator("#bizBar .chip").count()==5)
    check("all cases have biz/cust/diff/diffn", all(d.get(k) for d in data for k in ("biz","cust","diff","diffn")))
    check("biz values valid", {d["biz"] for d in data}<=set(bizs))
    for bz in bizs:
        pg.click(f'#bizBar .chip[data-biz="{bz}"]')
        exp = len([d for d in data if d["biz"]==bz])
        shown = pg.inner_text("#shownMeta")
        check(f"biz chip {bz}", shown.endswith(f"/ {exp} 个"), shown)
        check(f"biz chip {bz} chip count", f"{exp}" in pg.inner_text(f'#bizBar .chip[data-biz="{bz}"]'))
    pg.click('#bizBar .chip[data-biz="职业差"]')
    check("biz help text shown", "职业" in pg.inner_text("#bizHelp") and pg.locator("#bizHelp").is_visible())
    # biz + category combine
    pg.click('.chip[data-cat="软件/SaaS"]')
    exp = len([d for d in data if d["biz"]=="职业差" and d["cat"]=="软件/SaaS"])
    check("biz + category combine", pg.inner_text("#shownMeta").endswith(f"/ {exp} 个"), pg.inner_text("#shownMeta"))
    pg.click('.chip[data-cat="全部"]')
    # difficulty filter
    pg.click('#bizBar .chip[data-biz="全部"]')
    for lv in ("低","中","高"):
        pg.select_option("#fDiff", lv); exp = len([d for d in data if d["diff"]==lv])
        check(f"filter 国内复制难度={lv}", pg.inner_text("#shownMeta").endswith(f"/ {exp} 个"), pg.inner_text("#shownMeta"))
    pg.select_option("#fDiff","低"); pg.click('#bizBar .chip[data-biz="流程差"]')
    exp = len([d for d in data if d["diff"]=="低" and d["biz"]=="流程差"])
    check("biz + difficulty combine", pg.inner_text("#shownMeta").endswith(f"/ {exp} 个"), pg.inner_text("#shownMeta"))
    # new cases: searchable, modal shows biz / cust / difficulty
    pg.click("#resetBtn")
    check("reset clears biz + diff", pg.inner_text("#shownMeta").endswith(f"/ {len(data)} 个") and pg.input_value("#fDiff")=="")
    newc = [d for d in data if int(d["id"][1:])>=112]
    check("10 new cases present", len(newc)==10, str(len(newc)))
    pg.fill("#searchInput","FeedbackPanda"); check("search new case", pg.locator(".card").count()==1)
    pg.locator('[data-open]').first.click(); pg.wait_for_selector("#modal.open")
    mt = pg.inner_text("#modalKv")
    check("modal shows 商业结构/客户群/国内复制难度", "商业结构" in mt and "职业差" in mt and "客户群" in mt and "国内复制难度" in mt, mt[-160:])
    check("modal diff reason visible", pg.locator("#modalDiff").is_visible() and "—" in pg.inner_text("#modalDiff"))
    pg.screenshot(path=str(ROOT/"screenshots/modal-biz.png"))
    pg.keyboard.press("Escape"); pg.fill("#searchInput","")
    pg.fill("#searchInput","信息差"); check("search by biz keyword", pg.locator(".card").count()>=1)
    pg.fill("#searchInput","")
    # every case has at least one source link
    check("every case has a source", all(d["src"] for d in data))
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
