# twi.py <caminho> [...] — geometria de cada textwithimage (bloco, imagem, texto, flex, imageRatio) a 1400 E a 375px. SOMENTE LEITURA.
# Foi o que validou a R36: a 1400 a imagem tem o tamanho do GWI; a 375 ocupa a largura toda (o celular não quebra).
# Rodar de scripts-hazael/ com o AEM_COOKIES no ambiente:  set -a; . ../.env; set +a
import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
JS = """() => [...document.querySelectorAll('.cmp-textwithimage')].map(e => { const i=e.querySelector('img'); const p=e.querySelector('.paragraph')||e.querySelector('[class*=text]'); const r=e.getBoundingClientRect(), ri=i.getBoundingClientRect(), rp=p?p.getBoundingClientRect():{x:0,y:0,width:0,height:0}; const cs=getComputedStyle(e); return {bloco:[Math.round(r.width),Math.round(r.height)], img:[Math.round(ri.x),Math.round(ri.y+scrollY),Math.round(ri.width),Math.round(ri.height)], txt:[Math.round(rp.x),Math.round(rp.y+scrollY),Math.round(rp.width),Math.round(rp.height)], dir:cs.flexDirection, align:cs.alignItems, ratio:e.getAttribute('style')}; })"""
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-dev-shm-usage'])
    for w in (1400, 375):
        c = b.new_context(viewport={'width': w, 'height': 1000})
        c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
        for path in sys.argv[1:]:
            p = c.new_page()
            p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='load', timeout=90000)
            p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0);}")
            p.wait_for_timeout(2500)
            print(f"--- {w}px {path.split('/')[-1][:40]}  scrollW={p.evaluate('document.documentElement.scrollWidth')}")
            for r in p.evaluate(JS): print('   ', r)
            p.close()
        c.close()
    b.close()
