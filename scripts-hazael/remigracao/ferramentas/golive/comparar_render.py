#!/usr/bin/env python3
"""comparar_render.py <raizA> <raizB> [--saida nome] — a MESMA página nas duas raízes, renderizada a 1400px
(?wcmmode=disabled): geometria componente a componente (probe.js), imagem quebrada, bloco de contato.
`--listas-vazias-ok`: no staging as `list` apontam para páginas do global2 que ainda não existem.
SOMENTE LEITURA. A = referência (a árvore revisada). Lista de páginas = as de B. 4 navegadores em paralelo.
"""
import csv, json, os, sys
from multiprocessing import Pool
from pathlib import Path

AQUI = Path(__file__).resolve().parent
JS = (AQUI.parent / "probe.js").read_text()
IMGS = """() => { const FORA='header, footer, .cmp-experiencefragment--header, .cmp-experiencefragment--footer';
  const v=[...document.images].filter(i=>!i.closest(FORA)&&/^\/(?!\/)/.test(i.getAttribute('src')||''));   // só imagem do site: pixel de analytics (//cms.analytics.yahoo.com…) não conta
  return {total:v.length, quebradas:v.filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.getAttribute('src').slice(-80)),
          botoes:[...document.querySelectorAll('.cmp-experiencefragment .link-button__anchor, .experiencefragment .link-button__anchor')].filter(a=>!a.closest(FORA)).map(a=>a.getAttribute('href'))}; }"""


def mede(args):
    base, cookies, host, raizes, rel = args
    from playwright.sync_api import sync_playwright
    out = {"rel": rel}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        for lado, raiz in zip("AB", raizes):
            c = b.new_context(viewport={"width": 1400, "height": 1000})
            c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
            p = c.new_page()
            try:
                try:
                    r = p.goto(f"{base}{raiz}{rel}.html?wcmmode=disabled", wait_until="networkidle", timeout=60000)
                except Exception:
                    r = p.goto(f"{base}{raiz}{rel}.html?wcmmode=disabled", wait_until="load", timeout=90000)
                p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}scrollTo(0,0);}")
                p.wait_for_timeout(2500)
                res = p.evaluate(JS)
                out[lado] = {"http": r.status if r else None, "altura": p.evaluate("document.documentElement.scrollHeight"),
                             "rows": [(x["cls"], x["x"], x["y"], x["w"], x["h"], x.get("extra", "")) for x in res["rows"]], **p.evaluate(IMGS)}
            except Exception as e:
                out[lado] = {"erro": str(e)[:200]}
            c.close()
        b.close()
    return out


def main():
    sys.path.insert(0, str(AQUI))
    from _comum import BASE, DADOS
    from staging import paginas
    sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-bruno")
    from aem_lib import parse_cookie_string
    a, b = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    nome = sys.argv[sys.argv.index("--saida") + 1] if "--saida" in sys.argv else "render"
    env = dict(l.strip().split("=", 1) for l in open("/home/hazael/projects/migration_scripts/.env") if l.startswith("AEM_COOKIES="))
    cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'"))
    host = BASE.split("//", 1)[1]
    rels = paginas(b)
    if "--familias-nossas" in sys.argv:                 # B = global2: lá há famílias da Anion, que não são desta comparação
        from _comum import familias
        nossas = set(familias())
        rels = [r for r in rels if r.strip("/").split("/")[0] in nossas]
    with Pool(6) as pool:
        res = pool.map(mede, [(BASE, cookies, host, (a, b), r) for r in rels], chunksize=1)
    json.dump(res, open(DADOS / f"{nome}.json", "w"))
    iguais, dif, esperadas = 0, [], []
    for r in res:
        A, B = r.get("A", {}), r.get("B", {})
        prob = []
        if "erro" in A or "erro" in B or A.get("http") != 200 or B.get("http") != 200: prob.append(f"http A={A.get('http')} B={B.get('http')} {A.get('erro','')}{B.get('erro','')}")
        else:
            sem_list = lambda rows: [x for x in rows if not x[0].startswith("cmp-list")]
            so_list = A["rows"] != B["rows"] and [x[0] for x in sem_list(A["rows"])] == [x[0] for x in sem_list(B["rows"])] \
                and any(x[0].startswith("cmp-list") for x in A["rows"]) and "--listas-vazias-ok" in sys.argv
            if so_list:
                esperadas.append(r["rel"])
            elif A["rows"] != B["rows"]:
                n = next((i for i, (x, y) in enumerate(zip(A["rows"], B["rows"])) if x != y), min(len(A["rows"]), len(B["rows"])))
                prob.append(f"geometria difere a partir do bloco {n}/{len(A['rows'])} (altura {A['altura']} x {B['altura']}): A={A['rows'][n] if n < len(A['rows']) else '-'} B={B['rows'][n] if n < len(B['rows']) else '-'}")
            if B["quebradas"]: prob.append(f"{len(B['quebradas'])} imagem(ns) quebrada(s) em B: {B['quebradas'][:2]}")
            if A["total"] != B["total"]: prob.append(f"nº de imagens {A['total']} x {B['total']}")
            if len(A["botoes"]) != len(B["botoes"]): prob.append(f"botões do bloco de contato {len(A['botoes'])} x {len(B['botoes'])}")
        if prob: dif.append((r["rel"], prob))
        else: iguais += 1
    iguais -= len(esperadas)
    print(f"{len(res)} páginas: {iguais} idênticas, {len(esperadas)} só com a `list` vazia (esperado no staging: o alvo ainda não existe), {len(dif)} com diferença")
    print("  list vazia:", esperadas)
    for rel, prob in dif:
        print(f"  {rel}"); [print(f"      {x[:260]}") for x in prob]


if __name__ == "__main__":
    main()
