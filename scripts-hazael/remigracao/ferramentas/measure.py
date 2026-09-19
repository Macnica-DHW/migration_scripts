# measure.py <caminho> ["?wcmmode=disabled"] [--largura 375] — geometria renderizada, componente a componente. SOMENTE LEITURA.
# Rola a página inteira ANTES de medir (imagem lazy do GWI desloca os y abaixo dela) e lista também
# textwithimage/image-text (com o tamanho da imagem), list, carousel, índice de âncoras e hr.
# gap  = distância ao componente anterior do MESMO nível;   in = distância ao topo do componente que o contém (↳).
# Rodar de scripts-hazael/ com o AEM_COOKIES no ambiente:  set -a; . ../.env; set +a
import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright

args = sys.argv[1:]
largura = 1400
if '--largura' in args:
    i = args.index('--largura'); largura = int(args[i + 1]); del args[i:i + 2]
path = args[0]
suffix = args[1] if len(args) > 1 else ''
SP = os.path.dirname(os.path.abspath(__file__))
js = open(os.path.join(SP, 'probe.js')).read()
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
url = f"{CONFIG['base_url']}{path}.html{suffix}"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome',
                           args=['--no-sandbox', '--disable-dev-shm-usage'])
    c = b.new_context(viewport={'width': largura, 'height': 1000})
    c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
    p = c.new_page()
    try:
        resp = p.goto(url, wait_until='networkidle', timeout=60000)
    except Exception:
        resp = p.goto(url, wait_until='load', timeout=90000)
    if resp is not None and resp.status >= 400:
        print(f"HTTP {resp.status} em {url}" + ("  — cookie expirado: renovar AEM_COOKIES no .env" if resp.status == 401 else ""))
        sys.exit(1)
    p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0);}")
    p.wait_for_timeout(2500)
    res = p.evaluate(js)
    rows, estouro = res['rows'], res['estouro']
    altura = p.evaluate('document.documentElement.scrollHeight')
    scroll_w = p.evaluate('document.documentElement.scrollWidth')
    b.close()

print(f"# {path.split('/')[-1]}  janela={largura}px  altura={altura}px  scrollW={scroll_w}px"
      "  (os 12px a mais do scrollW são do cabeçalho/rodapé do site, em toda página)")
for e in estouro: print(f"# ESTOURO HORIZONTAL NO CORPO: {e}")
fundo = {}          # nível -> base (y+h) do último componente daquele nível
anterior = None
for r in rows:
    d = r['depth']
    if anterior is not None and d > anterior['depth']:
        gap = f"in={r['y']-anterior['y']:+5} "       # 1º filho: distância ao topo de quem o contém
    elif d in fundo:
        gap = f"gap={r['y']-fundo[d]:+5}"
    else:
        gap = ''
    for k in [k for k in fundo if k > d]: del fundo[k]
    fundo[d] = r['y'] + r['h']
    anterior = r
    nome = ('  ' * d + ('↳ ' if d else '') + r['cls'])[:26]
    print(f"y={r['y']:5} h={r['h']:4} {gap:10} x={r['x']:4} w={r['w']:4} colx={r['colx']:4} colw={r['colw']:4} "
          f"mt={r['mt']:>5} mb={r['mb']:>5} | {nome:26} | {r['txt'][:34]:34} {r['extra']}")
