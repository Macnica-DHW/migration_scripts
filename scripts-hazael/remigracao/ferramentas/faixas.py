#!/usr/bin/env python3
"""
faixas.py <rel> [<rel>...] — altura RENDERIZADA de cada faixa de fundo. SOMENTE LEITURA.

Faixa fina é sintoma de cor errada (diretriz do Hazael, 21/09/2026): quando
uma tira de fundo aparece e some em ~100px, quase sempre é um grupo pequeno
que ficou com cor diferente dos vizinhos, não uma decisão de layout.

O piso não é chute. Medidas a 1400px nas páginas de referência do global2
(sony e as folhas feitas à mão), a faixa MAIS FINA tem 218px:

    218px  sony-imx927   rgb(235,235,235)      <- o piso da referência
    218px  sony-imx938   rgb(235,235,235)
    278px  sony-imx928   rgb(235,235,235)
    323px  sony-imx939   rgb(247,247,247)
    ...
   2304px  sony          rgb(247,247,247)      <- a mais alta

Nada no global2 fica abaixo de 200px. Por isso PISO = 200.
O defeito que motivou isto: o índice de âncoras da `/ambarella` ficava branco
entre duas faixas `#f7f7f7` e rendia uma tira de 126px.

    set -a; . ../../../.env; set +a
    python3 faixas.py /ambarella /canon
    python3 faixas.py --todas            # varre a árvore inteira
"""
import os
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))

from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright

RAIZ = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
PISO = 200          # px; a referência não tem nada abaixo disso (mínimo 218)
ROXO = "rgb(127, 16, 128)"   # o breadcrumb do template, não é faixa de conteúdo

JS = """() => {
  const els = [...document.querySelectorAll('.cmp-container')]
    .filter(el => (el.getAttribute('style') || '').includes('background-color'))
    .map(el => { const r = el.getBoundingClientRect();
      return {top: Math.round(r.top + scrollY), h: Math.round(r.height),
              bg: getComputedStyle(el).backgroundColor}; });
  els.sort((a, b) => a.top - b.top);
  return els;
}"""


def faixas_da_pagina(pagina, rel):
    """[(cor, altura, n_seções)] — inclui os vãos brancos entre faixas."""
    pagina.goto(f"{CONFIG['base_url']}{RAIZ}{rel}.html?wcmmode=disabled",
                wait_until="networkidle", timeout=90000)
    pagina.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600)"
                    "{scrollTo(0,y);await new Promise(r=>setTimeout(r,50));}scrollTo(0,0);}")
    nos = [e for e in pagina.evaluate(JS) if e["bg"] != ROXO]
    corridas = []
    for e in nos:
        if (corridas and corridas[-1]["bg"] == e["bg"]
                and abs(corridas[-1]["fim"] - e["top"]) <= 2):
            corridas[-1]["fim"] = e["top"] + e["h"]
            corridas[-1]["n"] += 1
        else:
            corridas.append({"bg": e["bg"], "ini": e["top"],
                             "fim": e["top"] + e["h"], "n": 1})
    saida = []
    for i, c in enumerate(corridas):
        if i:
            vao = c["ini"] - corridas[i - 1]["fim"]
            if vao > 2:
                saida.append(("branco", vao, 0))
        saida.append((c["bg"], c["fim"] - c["ini"], c["n"]))
    return saida


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    if args == ["--todas"]:
        import json
        from aem_lib import build_session, get_json
        sessao, auth = build_session(verbose=False)
        url = (CONFIG["base_url"] + "/bin/querybuilder.json?path=" + RAIZ +
               "&type=cq:Page&p.limit=-1&p.hits=selective&p.properties=jcr:path")
        dados, _ = get_json(sessao, url, auth)
        args = [h["jcr:path"][len(RAIZ):] or "/" for h in dados["hits"]]

    cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    if not cookies:
        print("[erro] AEM_COOKIES vazia. Rode:  set -a; . ../../../.env; set +a")
        sys.exit(1)
    host = CONFIG["base_url"].split("//", 1)[1].rstrip("/")
    achados = 0
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                 args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"}
                         for k, v in cookies.items()])
        pag = ctx.new_page()
        for rel in args:
            rel = "/" + rel.strip("/") if rel.strip("/") else ""
            try:
                fs = faixas_da_pagina(pag, rel)
            except Exception as e:
                print(f"[falhou] {rel}: {str(e)[:70]}")
                continue
            finas = [f for f in fs if f[1] < PISO]
            if not fs:
                continue
            marca = "  ***" if finas else ""
            print(f"\n{rel or '/'}{marca}")
            for cor, h, n in fs:
                aviso = f"   <<< FINA (piso {PISO}px)" if h < PISO else ""
                print(f"    {cor:24} {h:>6}px  ({n} seções){aviso}")
            achados += len(finas)
        nav.close()
    print(f"\n{achados} faixa(s) abaixo do piso de {PISO}px."
          + ("" if achados else "  Nenhuma tira."))
    sys.exit(1 if achados else 0)


if __name__ == "__main__":
    main()
