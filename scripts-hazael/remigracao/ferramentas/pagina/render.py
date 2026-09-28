#!/usr/bin/env python3
"""
render.py <caminho>... [--lado g2|gwi] [--etiqueta antes|depois|...] [--saida DIR] [--nome NOME]
— o que o visitante vê numa página, a 1400px e fora do editor (?wcmmode=disabled). SOMENTE LEITURA (só GET no author).

Salva, para cada página:
  <nome>__<lado>__<etiqueta>.json  texto (blocos na ordem), links (texto, href, target), imagens (arquivo, alt,
                                   largura, altura), iframes (vídeos) e as abas — cada item com o painel de aba
                                   onde está ("1/2" = 2º painel do 1º componente de abas; null = fora de aba);
  <nome>__<lado>__<etiqueta>.png   print da página inteira, como o visitante a vê (a aba ativa só).

Como mede:
  - rola a página inteira antes (imagem lazy do GWI desloca tudo abaixo dela e sai sem foto no print);
  - fora do conteúdo: cabeçalho/rodapé (XFs), breadcrumb, nav;
  - abas: página com abas se confere ABA POR ABA — depois do print, um estilo injetado no DOM local abre todos os
    painéis (.cmp-tabs__tabpanel) e rola de novo; o texto, os links e as imagens de TODOS os painéis entram na
    extração, com o índice do painel. Nada disso vai ao AEM.

Lado gwi: o caminho do global2 com /content/macnicaglobal2/ -> /content/macnicagwi/. Página renomeada (global2
/solutions/... era /technology/... no GWI; europe -> eu): passar o caminho ABSOLUTO do GWI e --nome igual ao do
global2, para os dois renders caírem na mesma pasta com o mesmo nome.

    cd scripts-hazael
    python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei                       # g2, antes
    python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei --lado gwi
    python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei --etiqueta depois
    python3 remigracao/ferramentas/pagina/render.py /content/macnicagwi/americas/mai/en/technology/x \\
            --lado gwi --nome solutions__x

Saída padrão: remigracao/dados/paginas/<nome>/ (fora do git). O cookie (AEM_COOKIES do .env) vai só para o author.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import BASE, HOST, arquivo, caminho_lado, nome  # noqa: E402  (carrega o .env)
from aem_lib import parse_cookie_string  # noqa: E402

LARGURA = 1400
FORA = ('header,footer,nav,.cmp-breadcrumb,.breadcrumb,[class*="header"],[class*="footer"],'
        '.cmp-experiencefragment--header,.cmp-experiencefragment--footer')

ROLAR = """async () => { for (let y = 0; y < document.documentElement.scrollHeight; y += 800) {
  window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } window.scrollTo(0, 0); }"""

# espera cada <img> terminar de carregar (máx. 8 s): imagem lazy sem tamanho declarado mede 0x0 até chegar
ESPERAR_IMAGENS = """async () => { await Promise.all([...document.images].filter(i => !i.complete).map(i =>
  new Promise(r => { i.addEventListener('load', r, {once: true}); i.addEventListener('error', r, {once: true});
                     setTimeout(r, 8000); }))); }"""

# abas ANTES de abrir os painéis: rótulo e qual estava ativa
ABAS = """(fora) => {
  const root = document.querySelector('main') || document.body;
  const tabs = [...root.querySelectorAll('.cmp-tabs')].filter(t => !t.closest(fora));
  const out = [];
  tabs.forEach((t, k) => {
    const meu = x => x.closest('.cmp-tabs') === t;
    const rot = [...t.querySelectorAll('.cmp-tabs__tab')].filter(meu);
    [...t.querySelectorAll('.cmp-tabs__tabpanel')].filter(meu).forEach((p, i) => out.push({
      aba: (k + 1) + '/' + (i + 1),
      rotulo: rot[i] ? (rot[i].innerText || rot[i].textContent || '').replace(/\\s+/g, ' ').trim() : null,
      ativa: p.classList.contains('cmp-tabs__tabpanel--active') || p.getClientRects().length > 0}));
  });
  return out;
}"""

ABRIR_ABAS = """() => { const st = document.createElement('style'); st.id = 'render-abas-abertas';
  st.textContent = '.cmp-tabs__tabpanel{display:block !important;visibility:visible !important}';
  document.head.appendChild(st);
  for (const i of document.querySelectorAll('.cmp-tabs__tabpanel img[loading=lazy]')) i.loading = 'eager'; }"""

EXTRAIR = """(fora) => {
  const root = document.querySelector('main') || document.body;
  const tabs = [...root.querySelectorAll('.cmp-tabs')].filter(t => !t.closest(fora));
  const aba = el => { const p = el.closest('.cmp-tabs__tabpanel'); if (!p) return null;
    const t = p.closest('.cmp-tabs'); const meu = x => x.closest('.cmp-tabs') === t;
    return (tabs.indexOf(t) + 1) + '/' + ([...t.querySelectorAll('.cmp-tabs__tabpanel')].filter(meu).indexOf(p) + 1); };
  const T = el => (el.innerText || el.textContent || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
  const out = [];
  for (const el of root.querySelectorAll('h1,h2,h3,h4,h5,h6,p,li,td,th,.cmp-download,figcaption')) {
    if (el.closest(fora)) continue;
    if ((el.tagName === 'TD' || el.tagName === 'TH' || el.tagName === 'LI') && el.querySelector('p,li,h1,h2,h3,h4')) continue;
    const t = T(el);
    if (t) out.push([el.tagName, t, el.getClientRects().length > 0, aba(el)]);
  }
  const links = [...root.querySelectorAll('a[href]')].filter(a => !a.closest(fora))
    .map(a => [T(a), a.getAttribute('href'), a.target || '', a.getClientRects().length > 0, aba(a)]);
  const imgs = [...root.querySelectorAll('img')].filter(i => !i.closest(fora)).map(i => {
    const r = i.getBoundingClientRect();
    return [(i.currentSrc || i.src || i.getAttribute('data-src') || '').split('?')[0].split('/').pop(), i.alt,
            Math.round(r.width), Math.round(r.height), aba(i)]; });
  const iframes = [...root.querySelectorAll('iframe')].filter(i => !i.closest(fora))
    .map(i => [i.src || i.getAttribute('data-src') || '', aba(i)]);
  const alturas = {};
  tabs.forEach((t, k) => { const meu = x => x.closest('.cmp-tabs') === t;
    [...t.querySelectorAll('.cmp-tabs__tabpanel')].filter(meu).forEach((p, i) =>
      alturas[(k + 1) + '/' + (i + 1)] = Math.round(p.getBoundingClientRect().height)); });
  return {out, links, imgs, iframes, alturas};
}"""


def renderizar(pw_ctx, caminho, lado, etiqueta, saida=None, nome_=None):
    """Renderiza UMA página; devolve (json, png). `pw_ctx` = contexto do Playwright com o cookie do author."""
    P = caminho_lado(caminho, lado)
    n = nome_ or nome(P)
    url = f"{BASE}{P}.html?wcmmode=disabled"
    pg = pw_ctx.new_page()
    try:
        try:
            resp = pg.goto(url, wait_until="networkidle", timeout=60000)
        except Exception:                                      # noqa: BLE001  (o author às vezes não assenta)
            resp = pg.goto(url, wait_until="load", timeout=90000)
        st = resp.status if resp is not None else None
        if not pg.url.startswith(BASE + "/") or "/libs/granite/core/content/login" in pg.url:
            raise SystemExit(f"{P}: o author mandou para {pg.url.split('?')[0][:80]} — cookie expirado? renovar AEM_COOKIES")
        if st is not None and st >= 400:
            dica = {401: "  — cookie expirado: renovar AEM_COOKIES no .env",
                    404: ("  — página renomeada? passar o caminho absoluto do GWI (/solutions era /technology; "
                          "europe -> eu) e --nome" if lado == "gwi" else "")}.get(st, "")
            raise SystemExit(f"HTTP {st} em {url}{dica}")
        final = pg.url.split("?")[0]
        if final != url.split("?")[0]:
            print(f"  [aviso] {P} redirecionou para {final[len(BASE):]}")
        pg.wait_for_timeout(2500)
        pg.evaluate(ROLAR)
        pg.evaluate(ESPERAR_IMAGENS)
        pg.wait_for_timeout(1200)
        altura = pg.evaluate("document.documentElement.scrollHeight")
        abas = pg.evaluate(ABAS, FORA)
        png = arquivo(n, lado, etiqueta, "png", saida)
        png.parent.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(png), full_page=True)          # como o visitante vê (só a aba ativa)
        if abas:                                              # abre todos os painéis e rola de novo (lazy)
            pg.evaluate(ABRIR_ABAS)
            pg.evaluate(ROLAR)
            pg.evaluate(ESPERAR_IMAGENS)
            pg.wait_for_timeout(1200)
        d = pg.evaluate(EXTRAIR, FORA)
        for a in abas:
            a["h"] = d["alturas"].get(a["aba"])
        del d["alturas"]
        d = {"caminho": P, "url": BASE + P, "url_final": final, "http": st, "lado": lado, "etiqueta": etiqueta,
             "quando": datetime.datetime.now().isoformat(timespec="seconds"), "titulo": pg.title(),
             "h": altura, "abas": abas, **d}
    finally:
        pg.close()
    js = arquivo(n, lado, etiqueta, "json", saida)
    js.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ok {n} {lado} {etiqueta}: {len(d['out'])} blocos, {len(d['links'])} links, "
          f"{sum(1 for i in d['imgs'] if i[2] > 1)} imagens, {len(d['iframes'])} iframes, "
          f"{len(abas)} painéis de aba, altura {altura}px -> {js.parent}/")
    return js, png


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+")
    ap.add_argument("--lado", choices=["g2", "gwi"], default="g2")
    ap.add_argument("--etiqueta", default="antes")
    ap.add_argument("--saida", help="pasta dos arquivos (padrão: remigracao/dados/paginas/<nome>/)")
    ap.add_argument("--nome", help="nome dos arquivos (padrão: do caminho) — para casar página renomeada")
    a = ap.parse_args()
    if a.nome and len(a.caminhos) > 1:
        ap.error("--nome vale para um caminho só")
    raw = os.environ.get("AEM_COOKIES", "").strip()
    if not raw:
        sys.exit("AEM_COOKIES vazio — o .env da raiz precisa do login-token")
    from playwright.sync_api import sync_playwright
    falhas = 0
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": LARGURA, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": HOST, "path": "/"} for k, v in parse_cookie_string(raw).items()])
        for c in a.caminhos:
            try:
                renderizar(ctx, c, a.lado, a.etiqueta, a.saida, a.nome)
            except SystemExit as e:
                falhas += 1
                print(f"FALHOU {c} ({a.lado}): {e}", file=sys.stderr)
        nav.close()
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
