#!/usr/bin/env python3
"""conferir_mobile.py [--controle] — os BOTÕES das páginas migradas para o global2, em tela de celular (375px,
emulação mobile) e de tablet (768px). SOMENTE LEITURA — não grava nada, só abre as páginas.

Por botão do corpo (`.link-button__anchor`, download, submit): caixa, nº de linhas do rótulo, se sai da tela,
se é cortado por um ancestral com overflow, e se divide a linha com outro botão (lado a lado no celular).
Por página: estouro horizontal do corpo. `--controle`: mede também páginas da ANION (sony, canon) para separar
"defeito da migração" de "como o CSS do site se comporta".  Saída: dados/golive/mobile.json + resumo por padrão.
"""
import collections, json, sys
from multiprocessing import Pool
from pathlib import Path

AQUI = Path(__file__).resolve().parent
JS = r"""() => {
  const FORA='header, footer, .cmp-experiencefragment--header, .cmp-experiencefragment--footer, .page-top, .grecaptcha-badge';
  const W=document.documentElement.clientWidth, out=[];
  const bts=[...document.querySelectorAll('.link-button__anchor, .cmp-download__action, .cmp-form-button, button[type=submit]')]
    .filter(e=>!e.closest(FORA)).filter(e=>{const c=getComputedStyle(e),r=e.getBoundingClientRect();return c.display!=='none'&&c.visibility!=='hidden'&&r.width>0&&r.height>0;});
  for(const e of bts){
    const r=e.getBoundingClientRect(), cs=getComputedStyle(e);
    const rg=document.createRange(); rg.selectNodeContents(e);
    const tops=new Set([...rg.getClientRects()].filter(q=>q.width>2).map(q=>Math.round(q.top/4)));
    let cortado='';
    for(let a=e.parentElement;a&&a!==document.body;a=a.parentElement){
      const o=getComputedStyle(a).overflowX; if(o==='hidden'||o==='clip'){const ar=a.getBoundingClientRect(); if(r.right>ar.right+1||r.left<ar.left-1){cortado=(typeof a.className==='string'?a.className:'').slice(0,50);break;}}
      if(o==='auto'||o==='scroll') break;
    }
    const emXF=!!e.closest('.cmp-experiencefragment, .experiencefragment'), emAba=!!e.closest('.cmp-tabs'), emTabela=!!e.closest('table');
    out.push({t:(e.innerText||'').trim().replace(/\s+/g,' ').slice(0,44), x:Math.round(r.left), dir:Math.round(r.right), y:Math.round(r.top+scrollY), w:Math.round(r.width), h:Math.round(r.height),
      linhas:tops.size, minw:cs.minWidth, fora:(r.right>W+1||r.left<-1), cortado, emXF, emAba, emTabela,
      pai:Math.round((e.closest('.link-button, .cmp-download, .cmp-form-button')||e.parentElement).getBoundingClientRect().width)});
  }
  // lado a lado: dois botões VISÍVEIS cuja faixa vertical se sobrepõe
  const lado=[]; for(let i=0;i<out.length;i++)for(let j=i+1;j<out.length;j++){const a=out[i],b=out[j]; if(a.y<b.y+b.h-4&&b.y<a.y+a.h-4&&Math.abs(a.x-b.x)>20) lado.push([a.t,b.t]);}
  const est=[]; document.body.querySelectorAll('*').forEach(el=>{ if(el.closest(FORA))return; const r=el.getBoundingClientRect(); if(r.width>0&&r.height>0&&r.right>W+1){
      for(let a=el.parentElement;a&&a!==document.body;a=a.parentElement){const o=getComputedStyle(a).overflowX; if(o==='auto'||o==='scroll'||o==='hidden'||o==='clip')return;}
      est.push(`${el.tagName.toLowerCase()}.${(typeof el.className==='string'?el.className:'').slice(0,40)} dir=${Math.round(r.right)}`);}});
  return {W, scrollW:document.documentElement.scrollWidth, botoes:out, lado, estouro:[...new Set(est)].slice(0,5)};
}"""
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def mede(args):
    base, cookies, host, path = args
    from playwright.sync_api import sync_playwright
    out = {"path": path}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        for nome, vp, mobile in (("375", {"width": 375, "height": 812}, True), ("768", {"width": 768, "height": 1024}, True)):
            c = b.new_context(viewport=vp, is_mobile=mobile, has_touch=True, device_scale_factor=2, user_agent=UA)
            c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
            p = c.new_page()
            try:
                try:
                    r = p.goto(f"{base}{path}.html?wcmmode=disabled", wait_until="networkidle", timeout=60000)
                except Exception:
                    r = p.goto(f"{base}{path}.html?wcmmode=disabled", wait_until="load", timeout=90000)
                p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,80));}scrollTo(0,0);}")
                p.wait_for_timeout(1200)
                out[nome] = {"http": r.status if r else None, **p.evaluate(JS)}
            except Exception as e:
                out[nome] = {"erro": str(e)[:200]}
            c.close()
        b.close()
    return out


def main():
    sys.path.insert(0, str(AQUI))
    from _comum import BASE, DADOS, G, familias
    from staging import paginas
    sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-bruno")
    from aem_lib import parse_cookie_string
    env = dict(l.strip().split("=", 1) for l in open("/home/hazael/projects/migration_scripts/.env") if l.startswith("AEM_COOKIES="))
    cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'"))
    nossas = set(familias())
    todas = paginas(G)
    alvo = [G + r for r in todas if r.strip("/").split("/")[0] in nossas]
    if "--controle" in sys.argv:                       # páginas da Anion, só para comparar o comportamento do CSS
        anion = [G + r for r in todas if r.strip("/").split("/")[0] in ("sony", "canon")]
        alvo += anion[:4] + anion[60:64] + anion[-6:]
    with Pool(6) as pool:
        res = pool.map(mede, [(BASE, cookies, BASE.split("//", 1)[1], p) for p in alvo], chunksize=1)
    json.dump(res, open(DADOS / "mobile.json", "w"))
    print(f"{len(res)} páginas medidas ({sum(1 for r in res if r['path'][len(G):].strip('/').split('/')[0] in nossas)} nossas)")


if __name__ == "__main__":
    main()
