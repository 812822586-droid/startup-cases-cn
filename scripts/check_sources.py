"""检查 cases.json 里每个来源链接是否还能打开（404/410/连接失败会被列出）。
用法：python scripts/check_sources.py
注意：个别网站会拦截自动访问（返回 403），请用浏览器手动确认后再决定是否删除。
"""
import json, subprocess, pathlib, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent.parent
data = json.load(open(ROOT / "cases.json", encoding="utf8"))
UA = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36"
def code(url):
    r = subprocess.run(["curl", "-s", "-L", "-A", UA, "--max-time", "25", "-o", "/dev/null", "-w", "%{http_code}", url], capture_output=True)
    try: return int(r.stdout.decode() or 0)
    except ValueError: return 0
jobs = [(d["name"], u) for d in data for _, u in d["src"]]
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(lambda j: (j, code(j[1])), jobs))
bad = [(j, c) for j, c in res if c == 0 or c >= 400]
print(f"共 {len(jobs)} 个来源链接，异常 {len(bad)} 个")
for (n, u), c in bad: print(c, n, u)
