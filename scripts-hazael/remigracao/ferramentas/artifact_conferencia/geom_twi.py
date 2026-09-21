"""Geometria dos pares texto|imagem e dos botões de âncora. SOMENTE LEITURA."""
import os as _os
PASTA_TRABALHO = _os.environ.get("CONF_SP") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_trabalho")
_os.makedirs(PASTA_TRABALHO, exist_ok=True)

import sys, os, json
sys.path.insert(0,'/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright
path = sys.argv[1]; larguras = [int(x) for x in sys.argv[2].split(",")]
JS = """() => {
  const R = el => { const r = el.getBoundingClientRect(); return {x:Math.round(r.left), y:Math.round(r.top+scrollY), w:Math.round(r.width), h:Math.round(r.height)}; };
  const out = {twi: [], img_soltas: [], ancoras: []};
  document.querySelectorAll('.cmp-textwithimage').forEach(el => {
    const cs = getComputedStyle(el);
    const img = el.querySelector('img');
    const txt = el.querySelector('.cmp-textwithimage__item:not(.cmp-textwithimage__item__image), .cmp-textwithimage__item__text, .cmp-text');
    const imgItem = el.querySelector('.cmp-textwithimage__item__image');
    const h = el.querySelector('h1,h2,h3,h4,h5,b,strong');
    out.twi.push({box:R(el), display:cs.display, align:cs.alignItems, dir:cs.flexDirection,
      cls: el.parentElement.className.slice(0,60),
      titulo: h ? h.textContent.trim().slice(0,30) : '',
      txt: txt ? R(txt) : null,
      imgItem: imgItem ? R(imgItem) : null,
      img: img ? Object.assign(R(img), {nat: img.naturalWidth+'x'+img.naturalHeight, src: (img.currentSrc||img.src).split('/').pop().slice(0,40)}) : null});
  });
  // GWI: pares em colunas — lista imagens e cabeçalhos com caixa, em ordem
  if (!out.twi.length) {
    document.querySelectorAll('main img, .root img').forEach(img => {
      if (img.naturalWidth < 40) return;
      out.img_soltas.push(Object.assign(R(img), {nat: img.naturalWidth+'x'+img.naturalHeight, src:(img.currentSrc||img.src).split('/').pop().slice(0,40),
        col: (() => { let p = img.parentElement; for (let i=0;i<6&&p;i++){ if (/aem-GridColumn--default--\\d+/.test(p.className)) return p.className.match(/aem-GridColumn--default--(\\d+)/)[1]; p=p.parentElement;} return '?'; })()}));
    });
    document.querySelectorAll('main h2, main h3, main h4, .root h2, .root h3, .root h4').forEach(h => {
      out.ancoras.push(Object.assign(R(h), {tag:h.tagName, t:h.textContent.trim().slice(0,30)}));
    });
  }
  // botões de âncora (anchorlink) / índice
  document.querySelectorAll('.cmp-anchorlink a, .anchorlink a, [class*="anchor"] a, .cmp-pagesectionlisting a').forEach(a => {
    out.ancoras.push(Object.assign(R(a), {t:a.textContent.trim().slice(0,45), tag:'A', lines: Math.round(a.getBoundingClientRect().height / parseFloat(getComputedStyle(a).lineHeight||'20'))}));
  });
  return out;
}"""
cookies = parse_cookie_string(os.environ.get("AEM_COOKIES","").strip())
host = CONFIG['base_url'].split('//',1)[1].rstrip('/')
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox','--disable-dev-shm-usage'])
    for L in larguras:
        c = b.new_context(viewport={'width':L,'height':1000})
        c.add_cookies([{'name':k,'value':v,'domain':host,'path':'/'} for k,v in cookies.items()])
        p = c.new_page()
        p.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until='networkidle', timeout=90000)
        p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,80));}scrollTo(0,0);}")
        d = p.evaluate(JS)
        print(f"\n######## {path.split('/products/')[-1]}  @ {L}px ########")
        if d['twi']:
            print(f"  textwithimage: {len(d['twi'])}   (display/align/dir do 1º: {d['twi'][0]['display']} / {d['twi'][0]['align']} / {d['twi'][0]['dir']})")
            for t in d['twi']:
                i = t['img'] or {}; tx = t['txt'] or {}; ii = t['imgItem'] or {}
                print(f"   {t['titulo']:22} caixa y={t['box']['y']:5} h={t['box']['h']:4} | texto y={tx.get('y','-'):>5} h={tx.get('h','-'):>4} x={tx.get('x','-'):>4} w={tx.get('w','-'):>4} | colImg x={ii.get('x','-'):>4} w={ii.get('w','-'):>4} | img y={i.get('y','-'):>5} {i.get('w','-')}x{i.get('h','-')} nat={i.get('nat','-')}")
        if d['img_soltas']:
            print(f"  imagens no corpo (GWI): {len(d['img_soltas'])}")
            for i in d['img_soltas']: print(f"   img y={i['y']:5} x={i['x']:4} {i['w']}x{i['h']} nat={i['nat']} col={i['col']}  {i['src']}")
        if d['ancoras']:
            print("  cabeçalhos / botões de âncora:")
            for a in d['ancoras']: print(f"   {a.get('tag','?'):2} y={a['y']:5} x={a['x']:4} w={a['w']:4} h={a['h']:3}  {a.get('t','')}")
        c.close()
    b.close()
