#!/usr/bin/env python3
"""conferir_mobile.py [--controle] | --raiz <caminho> --saida <nome> | --resumo <nome> — os BOTÕES das páginas migradas para o global2, em tela de celular (375px,
emulação mobile) e de tablet (768px). SOMENTE LEITURA — não grava nada, só abre as páginas.

Por botão do corpo (`.link-button__anchor`, download, submit): caixa, nº de linhas do rótulo, se sai da tela,
se é cortado por um ancestral com overflow, e se divide a linha com outro botão (lado a lado no celular).
Por página: estouro horizontal do corpo. `--controle`: mede também páginas da ANION (sony, canon) para separar
"defeito da migração" de "como o CSS do site se comporta".  Saída: dados/golive/mobile.json + resumo por padrão.
`--raiz`: mede TODA página sob uma raiz qualquer (ex.: .../boards-modules/tq-systems) -> dados/golive/mobile_<nome>.json.
`--lista <json>` (com --raiz): mede só as páginas do json [{"path": ...}].
`--resumo <nome>`: só relê o json e imprime os padrões.
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


def resumo(res, raiz):
    rel = lambda r: r["path"][len(raiz):] or "/"
    for vp in ("375", "768"):
        ok = [r for r in res if r.get(vp, {}).get("http") == 200]
        ruins = [(rel(r), r.get(vp, {}).get("http"), r.get(vp, {}).get("erro", "")[:50]) for r in res if r.get(vp, {}).get("http") != 200]
        bts = [(rel(r), b) for r in ok for b in r[vp]["botoes"]]
        W = int(vp)
        print(f"\n--- {vp}px: {len(ok)} páginas lidas, {len(ruins)} falharam {ruins[:3]}; {len(bts)} botões em {len({p for p, _ in bts})} páginas")
        print("   rolagem lateral (scrollW - janela):", collections.Counter(r[vp]["scrollW"] - r[vp]["W"] for r in ok).most_common(5))
        for nome, f in (("SAI DA TELA", lambda b: b["fora"]), ("cortado por ancestral", lambda b: bool(b["cortado"])), ("rótulo em 2+ linhas", lambda b: b["linhas"] > 1),
                        ("encosta na borda direita", lambda b: not b["fora"] and b["dir"] >= W), ("mais largo que o vão do pai", lambda b: b["w"] > b["pai"] + 1)):
            sel = [(p, b) for p, b in bts if f(b)]
            print(f"   {nome:30} {len(sel):4} botões em {len({p for p, _ in sel}):3} páginas" + (f"   ex.: {sel[0][0]} «{sel[0][1]['t']}» x={sel[0][1]['x']}..{sel[0][1]['dir']} w={sel[0][1]['w']} pai={sel[0][1]['pai']} linhas={sel[0][1]['linhas']}" if sel else ""))
        lado = [(rel(r), par) for r in ok for par in r[vp]["lado"]]
        print(f"   {'pares LADO A LADO':30} {len(lado):4} em {len({p for p, _ in lado}):3} páginas" + (f"   ex.: {lado[0]}" if lado else ""))
        print("   onde estão:", dict(collections.Counter("XF" if b["emXF"] else "aba" if b["emAba"] else "tabela" if b["emTabela"] else "corpo" for _, b in bts)))
        print("   (w, vão do pai, min-width):", collections.Counter((b["w"], b["pai"], b["minw"]) for _, b in bts).most_common(6))
        print("   x..direita:", collections.Counter((b["x"], b["dir"]) for _, b in bts).most_common(6))
        print("   estouro do corpo:", collections.Counter(e.split(" dir=")[0] for r in ok for e in r[vp]["estouro"]).most_common(5))


def main():
    sys.path.insert(0, str(AQUI))
    from _comum import BASE, DADOS, G, familias
    from staging import paginas
    sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-bruno")
    from aem_lib import parse_cookie_string
    env = dict(l.strip().split("=", 1) for l in open("/home/hazael/projects/migration_scripts/.env") if l.startswith("AEM_COOKIES="))
    cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'"))
    arg = lambda n: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else None
    if arg("--resumo"):
        d = json.load(open(DADOS / f"mobile_{arg('--resumo')}.json")); return resumo(d["paginas"], d["raiz"])
    if arg("--raiz"):
        raiz = arg("--raiz").rstrip("/"); alvo = [raiz] + [raiz + r for r in paginas(raiz)]
        if arg("--lista"):                  # só as páginas de um json [{"path": ...}] (escopo já filtrado: dono, vivas, sem cópias)
            alvo = [e["path"] for e in json.load(open(arg("--lista")))]
        with Pool(6) as pool:
            res = pool.map(mede, [(BASE, cookies, BASE.split("//", 1)[1], p) for p in alvo], chunksize=1)
        json.dump({"raiz": raiz, "paginas": res}, open(DADOS / f"mobile_{arg('--saida')}.json", "w"))
        print(f"{len(res)} páginas sob {raiz}"); return resumo(res, raiz)
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
