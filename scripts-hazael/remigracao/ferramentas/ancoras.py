# ancoras.py <caminho> [...] — todo href="#x" do índice de âncoras tem alvo na página renderizada? (R22: print nenhum mostra âncora morta)
import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-dev-shm-usage'])
    c = b.new_context(viewport={'width': 1400, 'height': 1000})
    c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
    for path in sys.argv[1:]:
        p = c.new_page()
        try: p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='networkidle', timeout=60000)
        except Exception: p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='load', timeout=90000)
        p.wait_for_timeout(2000)
        r = p.evaluate("""() => [...document.querySelectorAll('[class*=anchor] a[href^="#"], .cmp-pagesectionlisting a[href^="#"]')].map(a => { const id = decodeURIComponent(a.getAttribute('href').slice(1)); const t = document.getElementById(id) || document.querySelector('[name="' + id + '"]'); return [id, t ? Math.round(t.getBoundingClientRect().top + scrollY) : null]; })""")
        print(path.split('/')[-1], '->', r)
        p.close()
    b.close()
