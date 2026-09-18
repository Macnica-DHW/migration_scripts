# vao.py <caminho> "Texto do título" [...] — vão entre um título e o próximo bloco de texto (GWI ou destino), com as margens que o explicam
import sys, os, json
sys.path.insert(0, '/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
path, alvos = sys.argv[1], sys.argv[2:]
JS = r"""
(alvos) => {
  const out = [];
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,b,strong')];
  for (const a of alvos) {
    const h = hs.find(e => e.textContent.trim() === a && e.getBoundingClientRect().height > 0);
    if (!h) { out.push({alvo: a, erro: 'nao achei'}); continue; }
    const hb = (h.closest('h1,h2,h3,h4,h5,h6,p') || h);
    const r = hb.getBoundingClientRect();
    // próximo elemento com texto, em ordem de documento, que não contém nem é contido pelo heading
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    w.currentNode = hb; let n, prox = null;
    while ((n = w.nextNode())) {
      if (hb.contains(n)) continue;
      if (!/^(P|LI|TD|DIV|SPAN)$/.test(n.tagName)) continue;
      const own = [...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim());
      const rr = n.getBoundingClientRect();
      if (own && rr.height > 0) { prox = n; break; }
    }
    const cs = getComputedStyle(hb), pr = prox.getBoundingClientRect(), ps = getComputedStyle(prox);
    const cadeia = []; let e = prox;
    while (e && e !== document.body && cadeia.length < 7) { cadeia.push(e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).trim().split(/\s+/).slice(0,2).join('.') : '')); e = e.parentElement; }
    out.push({alvo: a, tagH: hb.tagName, hTop: Math.round(r.top + scrollY), hH: Math.round(r.height), hFont: cs.fontSize, hLH: cs.lineHeight,
      hPad: cs.paddingTop + '/' + cs.paddingBottom, hMar: cs.marginTop + '/' + cs.marginBottom,
      vao: Math.round(pr.top - r.bottom), pTag: prox.tagName, pMar: ps.marginTop, pPad: ps.paddingTop, pLH: ps.lineHeight, pFont: ps.fontSize,
      mesmoPai: prox.parentElement === hb.parentElement, cadeia: cadeia.join(' < ')});
  }
  return out;
}
"""
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
host = CONFIG['base_url'].split('//', 1)[1].rstrip('/')
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox', '--disable-dev-shm-usage'])
    c = b.new_context(viewport={'width': 1400, 'height': 1000})
    c.add_cookies([{'name': k, 'value': v, 'domain': host, 'path': '/'} for k, v in cookies.items()])
    p = c.new_page()
    url = f"{CONFIG['base_url']}{path}.html?wcmmode=disabled"
    try: p.goto(url, wait_until='networkidle', timeout=60000)
    except Exception: p.goto(url, wait_until='load', timeout=90000)
    p.wait_for_timeout(2500)
    for r in p.evaluate(JS, alvos): print(json.dumps(r, ensure_ascii=False))
    b.close()
