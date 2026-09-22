#!/usr/bin/env python3
"""
clicar_ancoras.py <caminho da página> [--firefox] — CLICA em cada link `#` do corpo e mede se a página rolou. SOMENTE LEITURA.

O `ancoras.py` só confere que o alvo do `href="#x"` EXISTE. Isto não diz se o clique funciona: em
21/09/2026 o Hazael reportou "those links aren't working" na aba Suppliers/Partners da
`technology/imaging-and-vision` — e o alvo existia. Este script abre a página como o visitante
(`?wcmmode=disabled`, 1400px), passa por cada aba (se houver), clica em cada pill do índice e mede
o `scrollY` antes/depois e a distância ao alvo.

O que se descobriu naquele dia, para não investigar de novo:
  - o handler do site (clientlib-site) é `$('a[href^="#"]').click(...)`: acha o alvo com `$("#id")`
    (getElementById — id NUMÉRICO funciona), anima o scroll em 300ms e devolve `false` (o hash da
    URL NÃO muda; não é sintoma de defeito);
  - DENTRO DO EDITOR (editor.html) nenhum link `#` rola, em página nenhuma: em Edit o clique cai no
    `cq-Overlay`; em Preview o iframe de conteúdo tem a altura da página inteira (`overflow:hidden`),
    não há o que rolar. Conferir sempre com "View as Published" (`?wcmmode=disabled`).

  python3 remigracao/ferramentas/clicar_ancoras.py /content/macnicaglobal2/americas/mai/en/technology/imaging-and-vision
  python3 remigracao/ferramentas/clicar_ancoras.py <caminho> --firefox     # o navegador do Hazael
Sai 1 se algum clique não rolou até o alvo.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts-bruno"))
from aem_lib import CONFIG, parse_cookie_string
from playwright.sync_api import sync_playwright


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    caminho = args[0]
    base = CONFIG["base_url"].rstrip("/")
    if "author-" not in base:                        # o cookie só vai para o author
        sys.exit(f"[erro] base_url inesperada: {base}")
    host = base.split("//", 1)[1]
    cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    if not cookies:
        sys.exit("[erro] AEM_COOKIES vazio — set -a; . ../.env; set +a")
    falhas = 0
    with sync_playwright() as pw:
        if "--firefox" in sys.argv:
            nav = pw.firefox.launch()
        else:
            nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                     args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
        p = ctx.new_page()
        r = p.goto(f"{base}{caminho}.html?wcmmode=disabled", wait_until="networkidle", timeout=120000)
        if r is None or r.status >= 400:
            sys.exit(f"HTTP {r and r.status} em {caminho}" + (" — cookie vencido?" if r and r.status == 401 else ""))
        abas = p.locator("[role=tab]").count()
        rodadas = list(range(abas)) if abas else [None]
        print(f"{caminho.rsplit('/', 1)[-1]}: {abas} abas")
        for i in rodadas:
            if i is not None:
                p.locator("[role=tab]").nth(i).click()
                p.wait_for_timeout(700)
            p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);"
                       "await new Promise(r=>setTimeout(r,100));}scrollTo(0,0);}")
            p.wait_for_timeout(500)
            # só links do CONTEÚDO: o "Page Top" do rodapé do site (#page-top) não é nosso
            links = p.evaluate("""()=>[...document.querySelectorAll('main a[href^="#"], .root a[href^="#"]')]
                .filter(a=>a.offsetParent!==null && a.getAttribute('href').length>1
                        && a.getAttribute('href')!=='#page-top' && !a.closest('header, footer, .page-top'))
                .map(a=>({href:a.getAttribute('href'), texto:a.innerText.trim().slice(0,30)}))""")
            rot = f"aba {i + 1}" if i is not None else "página"
            if not links:
                print(f"  {rot}: sem link '#' visível")
                continue
            for l in links:
                alvo = p.evaluate(f"()=>{{const e=document.getElementById({l['href'][1:]!r}); "
                                  f"return e? Math.round(e.getBoundingClientRect().top+scrollY) : null}}")
                p.evaluate("scrollTo(0,0)")
                p.wait_for_timeout(250)
                a = p.locator(f'a[href="{l["href"]}"]:visible').first
                a.scroll_into_view_if_needed()
                antes = p.evaluate("scrollY")
                a.click()
                p.wait_for_timeout(1200)
                depois = p.evaluate("scrollY")
                # "chegou" = o alvo ficou NA TELA depois do clique (o site desconta o cabeçalho fixo;
                # perto do fim da página a animação para no máximo de ENTÃO — imagem lazy ainda
                # alonga a página depois — e o título fica visível, só não encostado no topo)
                chegou = (alvo is not None and depois != antes
                          and depois - 200 <= alvo <= depois + 1000 - 120)
                falhas += 0 if chegou else 1
                print(f"  {rot}  {'ok ' if chegou else 'NÃO'}  '{l['texto']:30}' {l['href']:14} alvoY={alvo}  scroll {antes}->{depois}")
        nav.close()
    print(f"\n  cliques que não chegaram ao alvo: {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
