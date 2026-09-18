#!/usr/bin/env python3
"""
Compara o TEXTO QUE O VISITANTE VÊ entre origem (GWI) e destino. SOMENTE LEITURA.

POR QUE MAIS UM COMPARADOR
O `aem_diff_conteudo.py` compara o JCR: pega os blocos da origem e pergunta se o
texto chegou em algum lugar do destino. Serve, mas tem dois pontos cegos que a
remigração não pode ter:

  1. **Não vê o que a tela mostra.** Conteúdo pode estar no JCR e não renderizar
     — é o caso do `containerpy`, nó irmão que existe em 111 páginas e nunca
     chega à tela. Para o JCR está tudo lá; para o visitante, sumiu.
  2. **Não vê ordem.** Dois blocos trocados de lugar passam como idênticos.

Este aqui renderiza as duas páginas com `?wcmmode=disabled`, extrai o texto
visível em ordem de documento e compara. É a pergunta que o usuário fez:
"content isn't missing nor added".

COMO COMPARA
Quebra os dois lados em unidades de texto (parágrafo, item de lista, célula,
título), normaliza (sem markup, sem pontuação, espaço colapsado, minúsculas) e
casa por **contenção**, não por igualdade: o destino funde e quebra blocos de
propósito, então exigir igualdade exata acusaria diferença em página correta.

  FALTANDO  unidade da origem que não aparece em lugar nenhum do destino
  SOBRANDO  unidade do destino que não existe na origem
  ORDEM     unidades presentes nos dois, mas em sequência diferente

RUÍDO CONHECIDO, filtrado por padrão (`--sem-filtro` mostra cru)
  - chrome do site (menu, rodapé, breadcrumb, "Page Top", cookie)
  - blocos espaçadores do GWI (só `&nbsp;`): no destino o respiro vem do
    container, então some de propósito e não é perda de conteúdo
  - texto de aba não ativa: só a primeira aba renderiza visível; as outras
    existem no DOM mas com display:none. O script lê o DOM inteiro (innerText
    de nó oculto volta vazio, então usa textContent) para não acusar as abas
    2..N como faltando.
  - botões de carousel ("Previous"/"Next"): chrome do componente, não
    conteúdo. Apareciam como `falta=2` em 26 páginas cujo carousel de 1 slide
    o destino colapsa em textwithimage (sem setas).
  - "opens in a new tab": o destino injeta esse texto (span oculto) em todo
    link target=_blank — `data-cmp-link-accessibility-text` no <body>. É
    removido na normalização dos dois lados.
  - cabeçalho da tabela de download (th "Title"/"Download") e a célula com o
    link "Download": formato decidido pelo time para o `download` do GWI, que
    não tem equivalente textual na origem. Só essas células, só por tag; um
    heading "Download" da origem continua sendo comparado.

  - título de item de lista: o teaser do GWI (relatedsuggestions,
    productlisting) imprime o pageTitle da página-alvo; o `list` do destino
    imprime navTitle → pageTitle → jcr:title, e não tem opção para mudar
    isso. Quando divergem (sitime-oscillators, agilex-5), o item está lá com
    outro rótulo. O par é casado pelo ALVO do link e contado na coluna
    `titulo_lista` — não some, mas não é "faltando".

PONTO CEGO QUE FOI FECHADO
  O título do `download` do GWI é um <a class="cmp-download__property--filename">,
  fora do seletor original — o rótulo do arquivo não contava na origem e a
  célula correspondente no destino saía como "sobrando". Entrou no seletor.

LIMITE HONESTO
Página com muita imagem carrega significado que nenhum comparador de texto vê.
Isto reduz o trabalho do olho humano, não substitui.

COMO RODAR
  python3 aem_fidelidade_render.py \\
      --origem  /content/macnicagwi/.../semiconductors/altera \\
      --destino /content/copia-teste/.../semiconductors-remigration/altera

  # em lote, casando os caminhos por sufixo
  python3 aem_fidelidade_render.py --raiz-origem <gwi> --raiz-destino <dest> \\
      --output fidelidade.csv
"""

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, normalize_name,
                     parse_cookie_string, print_header, write_csv)

# Texto do chrome do site — aparece nas duas pontas e não é conteúdo da página.
RUIDO = [
    "solutions", "products", "services", "about us", "blog", "contact",
    "glossary", "faq", "terms and conditions", "global portal", "page top",
    "privacy policy", "cookie", "all rights reserved", "search", "menu",
    "sign up", "newsletter", "follow us", "site map", "sitemap",
    "copyright", "macnica americas, inc",
]

JS_EXTRAI = """
() => {
  // Excluir o chrome do site ESTRUTURALMENTE, não por palavra-chave: o
  // mega-menu do GWI sozinho tem centenas de <li> ("Smart Factory",
  // "Broadcast & ProAV"...) e afogava a comparação — 1698 unidades na origem
  // contra 315 no destino, quase tudo navegação.
  const FORA = [
    'header', 'footer', 'nav', 'aside',
    '[class*="header__"]', '[class*="footer__"]', '[class*="breadcrumb"]',
    '[class*="navigation"]', '[class*="megamenu"]', '[class*="mega-menu"]',
    '[class*="globalnav"]', '[class*="global-nav"]', '[class*="gnav"]',
    '[class*="pagetop"]', '[class*="page-top"]', '[class*="cookie"]',
    '[class*="modal"]', '[class*="drawer"]', '[class*="sidebar"]',
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    '[aria-hidden="true"]',
    // setas/indicadores de carousel: "Previous"/"Next" são chrome, não conteúdo
    '[class*="carousel__action"]', '[class*="carousel__indicator"]',
    // botão mobile do índice de âncoras do GWI: criado por JS com o rótulo do
    // item ativo e escondido acima de 1025px — duplicava "Features"
    '.cmp-pagesectionlisting__button',
    // coluna de grid escondida NO BREAKPOINT DEFAULT (cq:responsive
    // behavior=hide): o visitante nunca vê. Por classe, não por display:none,
    // para as abas 2..N continuarem contando. Caso real: metade do XF
    // signup-and-contact do GWI ("Have a question for the Macnica Team?")
    '.aem-GridColumn--default--hide',
    // popups de sucesso/erro do form container (XFs embutidos): só abrem
    // depois do submit. No destino saem com aria-hidden (já excluído); no GWI
    // ficam em .cmp-form-success/.cmp-form-error sem marca nenhuma — contavam
    // como 4 unidades "faltando" na macnica-and-adi com o form já migrado (R27)
    '.cmp-form-success', '.cmp-form-error', '[data-cmp-hook-form$="-popup"]',
    // o rodapé do GWI é um experience fragment sem <footer> e sem classe
    // footer__ — só o id do bloco de copyright o identifica
    '[id*="copyright"]', '[class*="socialmedia"]', '[class*="social-media"]'
  ].join(',');

  const alvo = document.querySelector('main') || document.body;
  const out = [];
  // textContent, não innerText: aba inativa tem display:none e innerText volta
  // vazio — acusaria as abas 2..N como conteúdo perdido.
  // a.anchor-link__list__item__anchor: item do índice de âncoras do DESTINO
  // (um <a> dentro de <div>; no GWI é <li>). Sem ele os rótulos do índice
  // saíam como "faltando" com o componente renderizando certo.
  // a.cmp-download__property--filename: o rótulo do `download` do GWI. Sem
  // ele a origem não contava o arquivo e a célula do destino saía "sobrando".
  const bloco = 'p, li, h1, h2, h3, h4, h5, h6, td, th, figcaption, dt, dd, button, a.link-button__anchor, a.cmp-button, .cmp-button__text, a.cmp-download__property--filename, a.anchor-link__list__item__anchor';
  alvo.querySelectorAll(bloco).forEach(el => {
    if (el.closest(FORA)) return;
    // só folhas: um <li> com <p> dentro não deve contar duas vezes. Mas o
    // filho-bloco só desqualifica o pai se tiver TEXTO: o GWI tem
    // `<h4>Título<p>&nbsp;</p></h4>` (autoria malformada), e descartar o h4
    // por causa de um <p> vazio fazia o título nunca contar na origem.
    const filhosComTexto = Array.from(el.querySelectorAll(bloco)).some(
      f => (f.textContent || '').replace(/[\s\u00a0]+/g, '').length > 0);
    if (filhosComTexto) return;
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    // href do link do item: permite casar item de lista pelo ALVO quando o
    // título diverge (teaser do GWI = pageTitle, list do destino = navTitle)
    const a = el.closest('a') || el.querySelector('a');
    const href = a ? (a.getAttribute('href') || '') : '';
    if (t) out.push({ tag: el.tagName.toLowerCase(), txt: t, href: href });
  });
  // Texto/inline SOLTO na raiz do rich text (`<span>` ou texto puro filho
  // direto de .cmp-text): o seletor acima só vê blocos. O GWI tem parágrafo
  // assim na `canon-li8030sa`; o destino o embrulha em <p> (R33) e a unidade
  // saía como "sobrando" sem existir diferença de conteúdo.
  alvo.querySelectorAll('.cmp-text').forEach(c => {
    if (c.closest(FORA)) return;
    let buf = '';
    const flush = () => {
      const t = buf.replace(/\s+/g, ' ').trim();
      if (t) out.push({ tag: 'solto', txt: t, href: '' });
      buf = '';
    };
    c.childNodes.forEach(n => {
      if (n.nodeType === 3) buf += n.textContent;
      else if (n.nodeType === 1) {
        if (n.matches(bloco) || n.querySelector(bloco)
            || /^(UL|OL|DL|TABLE|DIV|HR|BLOCKQUOTE)$/.test(n.tagName)) flush();
        else buf += n.textContent;
      }
    });
    flush();
  });
  return out;
}
"""


def norm(s):
    s = re.sub(r"\s+", " ", s or "").strip().lower()
    s = s.replace(" ", " ")
    # o destino injeta "opens in a new tab" em todo link target=_blank (span
    # oculto adicionado pelo clientlib de acessibilidade dos core components)
    s = s.replace("opens in a new tab", " ")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


def e_ruido(t):
    n = norm(t)
    if len(n) < 3:
        return True
    return any(r in n and len(n) < len(r) + 12 for r in RUIDO)


def e_chrome_tabela_download(u):
    """Células que o FORMATO da tabela de download inventa.

    O `download` do GWI vira tabela Title/Download no destino (decisão do
    time). O cabeçalho e o texto do link não existem na origem por
    construção. Filtra SÓ essas células, e só por tag — um heading "Download"
    ou um parágrafo "Title" continuam sendo comparados.
    """
    n = norm(u.get("txt", ""))
    tag = u.get("tag", "")
    if tag == "th" and n in ("title", "download"):
        return True
    return tag == "td" and n == "download"


def extrair(pagina, base_url, caminho, espera):
    pagina.goto(f"{base_url}{caminho}.html?wcmmode=disabled",
                wait_until="load", timeout=90000)
    pagina.wait_for_timeout(espera)
    return pagina.evaluate(JS_EXTRAI)


def _alvo(u):
    """Último segmento do href, normalizado como o destino nomeia os nós."""
    h = (u.get("href") or "").split("?")[0].split("#")[0]
    h = re.sub(r"\.html$", "", h).rstrip("/")
    return normalize_name(h.rsplit("/", 1)[-1]) if h else ""


def comparar(orig, dest, filtrar=True):
    """(faltando, sobrando, fora_de_ordem, titulos_lista) por contenção.

    `titulos_lista`: pares (origem, destino) de item de lista com o MESMO alvo
    e rótulo diferente — pageTitle no teaser do GWI × navTitle no list do
    destino. O link está lá; conta à parte para não virar "faltando" nem
    sumir do relatório.
    """
    o = [u for u in orig if not (filtrar and (e_ruido(u["txt"])
                                                or e_chrome_tabela_download(u)))]
    d = [u for u in dest if not (filtrar and (e_ruido(u["txt"])
                                                or e_chrome_tabela_download(u)))]
    on = [norm(u["txt"]) for u in o]
    dn = [norm(u["txt"]) for u in d]
    dblob = " || ".join(dn)
    oblob = " || ".join(on)

    faltando = [u for u, n in zip(o, on) if n and n not in dblob]
    sobrando = [u for u, n in zip(d, dn) if n and n not in oblob]

    titulos_lista = []
    if filtrar:
        # candidatos: TODO `li` com link do destino, não só os "sobrando" — o
        # rótulo curto do destino ("SiTime Oscillators") costuma estar contido
        # em algum texto da origem e por isso nunca sobra.
        alvos_dest = {}
        for v in d:
            if v.get("tag") == "li" and _alvo(v):
                alvos_dest.setdefault(_alvo(v), []).append(v)
        resto = []
        for u in faltando:
            a = _alvo(u)
            if u.get("tag") in ("h2", "h3", "h4", "li") and a and alvos_dest.get(a):
                v = alvos_dest[a].pop(0)
                titulos_lista.append((u, v))
                sobrando = [x for x in sobrando if x is not v]
            else:
                resto.append(u)
        faltando = resto

    # ordem: entre as unidades que existem dos dois lados, a sequência bate?
    pares = []
    for i, n in enumerate(on):
        if not n:
            continue
        j = next((k for k, m in enumerate(dn) if n in m or m in n), None)
        if j is not None:
            pares.append((i, j))
    fora = 0
    for a in range(1, len(pares)):
        if pares[a][1] < pares[a - 1][1]:
            fora += 1
    return faltando, sobrando, fora, titulos_lista


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem")
    ap.add_argument("--destino")
    ap.add_argument("--raiz-origem")
    ap.add_argument("--raiz-destino")
    ap.add_argument("--sem-filtro", action="store_true")
    ap.add_argument("--pular-contendo", nargs="*", default=[],
                    help="trechos do caminho de ORIGEM a ignorar (ex: /sony /deepx)")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--espera", type=int, default=2500)
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default="fidelidade_render.csv")
    ap.add_argument("--detalhe", type=int, default=6,
                    help="quantas unidades listar por página no terminal")
    args = ap.parse_args()

    if not (args.origem and args.destino) and not (args.raiz_origem and args.raiz_destino):
        print("[erro] use --origem/--destino ou --raiz-origem/--raiz-destino",
              file=sys.stderr)
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    if not cookies:
        print("[erro] AEM_COOKIES vazio no .env", file=sys.stderr)
        sys.exit(1)
    host = args.base_url.split("//", 1)[1].rstrip("/")

    print_header("fidelidade de conteúdo (texto renderizado)")

    pares = []
    if args.origem:
        pares.append((args.origem.rstrip("/"), args.destino.rstrip("/")))
    else:
        session, auth = build_session(verbose=False)
        ro = args.raiz_origem.rstrip("/")
        rd = args.raiz_destino.rstrip("/")
        for p in crawl_tree(session, args.base_url, ro, auth,
                            only_pages=True, quiet=True):
            if any(x in p for x in args.pular_contendo):
                continue
            # O destino normaliza o nome do nó (minúscula, hífen colapsado):
            # 'TEST-FIXED-LIST-...' vira 'test-fixed-list-...' e
            # 'sulfur-som---carrier-board' vira 'sulfur-som-carrier-board'.
            # Juntar o sufixo cru acusava a página inteira como perdida
            # (destino=0 unidades) quando ela existia, só com outro nome.
            rel = p[len(ro):].strip("/")
            destino = rd if not rel else rd + "/" + "/".join(
                normalize_name(x) for x in rel.split("/"))
            pares.append((p, destino))
        if args.limite:
            pares = pares[:args.limite]
    print(f"  pares a comparar : {len(pares)}")
    print(f"  filtro de ruído  : {'não' if args.sem_filtro else 'sim'}\n")

    linhas = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=args.chrome,
                                 args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"}
                         for k, v in cookies.items()])
        pag = ctx.new_page()
        for i, (po, pd) in enumerate(pares, 1):
            try:
                uo = extrair(pag, args.base_url, po, args.espera)
                ud = extrair(pag, args.base_url, pd, args.espera)
            except Exception as e:
                print(f"  [falha] {pd}: {str(e)[:90]}")
                linhas.append({"destino": pd, "origem": po, "unidades_origem": "",
                               "unidades_destino": "", "faltando": "", "sobrando": "",
                               "fora_de_ordem": "", "titulo_lista": "",
                               "erro": str(e)[:120]})
                continue
            falt, sobr, fora, tit = comparar(uo, ud, filtrar=not args.sem_filtro)
            status = "OK" if not falt and not sobr else "DIVERGE"
            print(f"  [{status:7}] {pd.split('/')[-1][:42]:44} "
                  f"origem={len(uo):4} destino={len(ud):4} "
                  f"faltando={len(falt):3} sobrando={len(sobr):3} ordem={fora:3}")
            for u in falt[:args.detalhe]:
                print(f"       FALTA    <{u['tag']}> {u['txt'][:88]}")
            for u in sobr[:args.detalhe]:
                print(f"       SOBRA    <{u['tag']}> {u['txt'][:88]}")
            for u, v in tit[:args.detalhe]:
                print(f"       TÍTULO   lista: GWI '{u['txt'][:40]}' -> destino '{v['txt'][:40]}'")
            linhas.append({
                "destino": pd, "origem": po,
                "unidades_origem": len(uo), "unidades_destino": len(ud),
                "faltando": len(falt), "sobrando": len(sobr),
                "fora_de_ordem": fora,
                "titulo_lista": len(tit),
                "erro": "",
                "amostra_faltando": " | ".join(u["txt"][:70] for u in falt[:5]),
                "amostra_sobrando": " | ".join(u["txt"][:70] for u in sobr[:5]),
                "amostra_titulo_lista": " | ".join(
                    f"{u['txt'][:40]} -> {v['txt'][:40]}" for u, v in tit[:5]),
            })
        nav.close()

    write_csv(args.output,
              ["destino", "origem", "unidades_origem", "unidades_destino",
               "faltando", "sobrando", "fora_de_ordem", "titulo_lista", "erro",
               "amostra_faltando", "amostra_sobrando", "amostra_titulo_lista"], linhas)
    ok = sum(1 for l in linhas if l.get("faltando") == 0 and l.get("sobrando") == 0)
    print(f"\n  páginas sem divergência : {ok}/{len(linhas)}")
    print(f"  CSV                     : {args.output}")


if __name__ == "__main__":
    main()
