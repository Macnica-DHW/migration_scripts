import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright

path = sys.argv[1]
suffix = sys.argv[2] if len(sys.argv) > 2 else ''
SP = os.path.dirname(os.path.abspath(__file__))
js = open(os.path.join(SP, 'probe.js')).read()
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
url = f"{CONFIG['base_url']}{path}.html{suffix}"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome',
                           args=['--no-sandbox', '--disable-dev-shm-usage'])
    c = b.new_context(viewport={'width': 1400, 'height': 1000})
    c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
    p = c.new_page()
    try:
        p.goto(url, wait_until='networkidle', timeout=60000)
    except Exception:
        p.goto(url, wait_until='load', timeout=90000)
    p.wait_for_timeout(3000)
    rows = p.evaluate(js)
    b.close()

prev_bottom = None
for r in rows:
    gap = '' if prev_bottom is None else f"gap={r['y']-prev_bottom:+5}"
    print(f"y={r['y']:5} h={r['h']:4} {gap:10} colx={r['colx']:4} colw={r['colw']:4} "
          f"mt={r['mt']:>5} mb={r['mb']:>5} | {r['cls'][:22]:24} | {r['txt'][:34]}")
    prev_bottom = r['y'] + r['h']
