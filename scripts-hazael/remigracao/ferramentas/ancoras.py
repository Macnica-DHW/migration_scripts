# ancoras.py <caminho> [...] — todo href="#x" do CORPO tem alvo na página renderizada? SOMENTE LEITURA.
# Olha o índice de âncoras (R22) E os links "#x" no meio do texto, de botão e de tabela (foi assim que a R39 escapou:
# o link "See the full … lineup here" não está no índice). Print nenhum mostra âncora morta.
# Fora: cabeçalho, rodapé, "#page-top" e href="#" puro. Serve para os dois lados (GWI e destino).
# Rodar de scripts-hazael/ com o AEM_COOKIES no ambiente:  set -a; . ../.env; set +a
import sys, os
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
JS = """() => { const FORA = 'header, footer, .cmp-experiencefragment--header, .cmp-experiencefragment--footer, .page-top';
  return [...document.querySelectorAll('a[href^="#"]')].filter(a => !a.closest(FORA)).map(a => {
    const raw = a.getAttribute('href').slice(1); if (!raw || raw === 'page-top') return null;
    let id = raw; try { id = decodeURIComponent(raw); } catch (e) {}
    const t = document.getElementById(id) || document.querySelector('[name="' + CSS.escape(id) + '"]');
    const indice = !!a.closest('[class*=anchor-link], .anchorlink, .cmp-pagesectionlisting');
    const r = a.getBoundingClientRect();
    return {id, indice, visivel: r.width > 0 && r.height > 0, txt: (a.innerText || '').trim().slice(0, 40),
            alvo: t ? Math.round(t.getBoundingClientRect().top + scrollY) : null, tag: t ? t.tagName.toLowerCase() + '.' + (typeof t.className === 'string' ? t.className : '').slice(0, 30) : null};
  }).filter(Boolean); }"""
mortos = 0
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-dev-shm-usage'])
    c = b.new_context(viewport={'width': 1400, 'height': 1000})
    c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
    for path in sys.argv[1:]:
        p = c.new_page()
        try: resp = p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='networkidle', timeout=60000)
        except Exception: resp = p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='load', timeout=90000)
        if resp is not None and resp.status >= 400:
            print(f"{path.split('/')[-1]}: HTTP {resp.status}" + ("  — cookie expirado" if resp.status == 401 else "")); p.close(); continue
        p.wait_for_timeout(2000)
        r = p.evaluate(JS)
        m = [x for x in r if x['alvo'] is None]
        mortos += len(m)
        print(f"{path.split('/')[-1]}: {len(r)} links '#' no corpo ({sum(x['indice'] for x in r)} no índice), {len(m)} SEM ALVO")
        for x in r:
            onde = 'índice' if x['indice'] else 'corpo '
            print(f"   {'MORTO' if x['alvo'] is None else 'ok   '} {onde} #{x['id']:28} -> {str(x['alvo']):>6} {x['tag'] or '':32} | {x['txt']}" + ('' if x['visivel'] else '  (link oculto)'))
        p.close()
    b.close()
sys.exit(1 if mortos else 0)
