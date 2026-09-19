# celulas.py <caminho> [...] — por tabela, a 1400 E a 375px: células de token único partidas em 2+ linhas, largura da tabela x do wrapper, scroll. SOMENTE LEITURA.
# Foi o que validou a R41 (altera-arria-10: 31 de 209 quebradas no desktop e 189 no celular -> 0 e 0; a tabela rola no wrapper).
# Rodar de scripts-hazael/ com o AEM_COOKIES no ambiente:  set -a; . ../.env; set +a
import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
JS = """() => [...document.querySelectorAll('.cmp-table')].map(w => { const t=w.querySelector('table'); let q=0,n=0; t.querySelectorAll('td,th').forEach(c => { const x=(c.textContent||'').trim(); if(!x||/\\s/.test(x)) return; n++; const r=document.createRange(); r.selectNodeContents(c); const tops=new Set([...r.getClientRects()].map(k=>Math.round(k.top))); if(tops.size>1) q++; }); return {wrapperW:Math.round(w.getBoundingClientRect().width), tableW:Math.round(t.getBoundingClientRect().width), tableH:Math.round(t.getBoundingClientRect().height), scrollW:w.scrollWidth, tokens:n, quebradas:q}; })"""
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-dev-shm-usage'])
    for w in (1400, 375):
        c = b.new_context(viewport={'width': w, 'height': 1000})
        c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
        for path in sys.argv[1:]:
            p = c.new_page(); p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='load', timeout=90000); p.wait_for_timeout(2500)
            print(f"--- {w}px {path.split('/')[-1][:40]} pageScrollW={p.evaluate('document.documentElement.scrollWidth')}")
            for r in p.evaluate(JS): print('   ', r)
            p.close()
        c.close()
    b.close()
