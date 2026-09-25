#!/usr/bin/env python3
"""
prints_antes_depois.py antes|depois PASTA REL... — print da página inteira a 1400px, fora do editor (?wcmmode=disabled),
de cada página (rel a /americas/mai/en), em PASTA/<antes|depois>/<rel com __>.png. SOMENTE LEITURA (só GET no author).

    python3 prints_antes_depois.py antes  dados/golive/prints_B pag1 pag2
    python3 prints_antes_depois.py depois dados/golive/prints_B pag1 pag2
    python3 prints_antes_depois.py comparar dados/golive/prints_B        # altura e caixa dos pixels que mudaram

Complementa o corrigir_links.py quando o conserto PÕE um link onde não havia (título/imagem ganham <a>): o comparador de
HTML ignora as tags <a>, então a prova de que a disposição não mudou é o print.
"""
import os
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, parse_cookie_string  # noqa: E402

M = "/content/macnicaglobal2/americas/mai/en"
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
CHROME = "/usr/bin/google-chrome"


def nome(rel):
    return rel.strip("/").replace("/", "__") + ".png"


def tirar(fase, pasta, rels):
    from playwright.sync_api import sync_playwright
    host = BASE.split("//", 1)[1]
    ck = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    (pasta / fase).mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 1400, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in ck.items()])
        pg = c.new_page()
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE) else r.abort())   # só o author
        for rel in rels:
            pg.goto(f"{BASE}{M}/{rel}.html?wcmmode=disabled", timeout=180000, wait_until="networkidle")
            # o menu do header aparece com fade por JS: sem isto o print pega estados diferentes do menu (24/09)
            pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(4000)
            pg.screenshot(path=str(pasta / fase / nome(rel)), full_page=True)
            print(f"{fase}: /{rel}")
        b.close()


def comparar(pasta):
    from PIL import Image, ImageChops
    ruins = 0
    for a in sorted((pasta / "antes").glob("*.png")):
        d = pasta / "depois" / a.name
        ia, idp = Image.open(a).convert("RGB"), Image.open(d).convert("RGB")
        if ia.size != idp.size:
            print(f"DIFERENTE {a.name}: tamanho {ia.size} -> {idp.size}"); ruins += 1; continue
        caixa = ImageChops.difference(ia, idp).getbbox()
        print(("IGUAL    " if not caixa else "PIXELS   ") + f" {a.name}: {ia.size}" + (f" mudou em {caixa}" if caixa else ""))
        ruins += bool(caixa)
    return ruins


if __name__ == "__main__":
    fase, pasta = sys.argv[1], Path(sys.argv[2])
    if fase == "comparar":
        sys.exit(1 if comparar(pasta) else 0)
    tirar(fase, pasta, sys.argv[3:])
