#!/usr/bin/env python3
"""
corrigir_links.py [--grupos A B C] [--executar] — conserto PONTUAL dos links do relatório global2 x GWI
(dados/mapas/global2_links_vs_gwi_2026-09-24.html). Dry-run por padrão: só GET, mostra antes/depois de cada propriedade.

Pedido do Hazael (24/09/2026): "fix the links in a punctual manner — I don't want to risk breaking the pages nor
changing their layout". Por isso a lista abaixo é FECHADA e revisada à mão (nada é descoberto sozinho), e cada
conserto mexe em UMA propriedade de UM nó que já existe:

  href   troca só o valor do href de um <a> que já existe (casado por href antigo + texto do link; tem de ser único)
  prop   grava linkURL num button/image/title que já existe (o valor atual tem de ser o esperado, ou ausente)
  wrap   põe um <a> em volta de um trecho que já está no texto (o trecho tem de aparecer uma vez só)
  ext    troca, num texto, cada href interno sem .html pelo mesmo caminho com .html (grupo D)

Nenhum nó é criado, movido ou apagado; nenhuma outra propriedade muda. Título com link no global2 renderiza igual ao
sem link (medido em atd-europe/sony-gnss: mesma cor, peso, tamanho, sem sublinhado, mesma altura).

Grupos: D = link de TEXTO interno sem .html (barra final ou sem extensão): no author o clique dá 302 -> 403; o conserto
só acrescenta .html ao href (tira a barra final), um POST por propriedade, páginas protegidas fora; A = href errado
(13 links, 10 páginas); B = link num elemento que já existe (6); C = eventos: link no título
da página (9; no GWI o link é uma linha própria com o nome do evento, que no global2 foi tirada por repetir o título).

--executar: backup do jcr:content inteiro de cada página em dados/golive/backup_links_<data>.json ANTES da 1ª escrita;
relê o nó imediatamente antes de gravar (se mudou desde o dry-run e o trecho antigo sumiu, pula); grava só a
propriedade; relê e confere que só ela mudou. Tudo passa pela trava da Session do aem_lib (páginas protegidas, GWI).

    python3 corrigir_links.py                      # dry-run de A, B e C
    python3 corrigir_links.py --grupos A --executar
"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, EscritaProibida, build_session, motivo_bloqueio  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
RELATORIO = Path(__file__).resolve().parents[2] / "dados" / "mapas" / "global2_links_vs_gwi_2026-09-24.json"
M = "/content/macnicaglobal2/americas/mai/en"
NEWS, NL, EV = "about-us/news-events/news-archive", "about-us/newsletter", "about-us/news-events/events-archive"
# link de TEXTO sai como está gravado (ninguém põe .html): sem .html o author dá 302 -> barra final -> 403. Button/image/
# title põem o .html sozinhos (core). Por isso todo href interno de texto aqui termina em .html, como no GWI.
BLOG_EDGE = f"{M}/blog/removing-the-barriers-to-edge-and-gen-ai-in-embedded-vision.html"
BROADCAST = f"{M}/solutions/broadcast-proav-solutions.html"
TQ = f"{M}/products/boards-modules/tq-systems"
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author

# (grupo, página rel, nó rel ao jcr:content, tipo, dados)
CONSERTOS = [
    ("A", f"{NEWS}/macnica-americas-adds-connect-tech-inc-to-supplier-portfolio-to-accelerate-edge-ai-innovation",
     "root/container/text_1_wrap/text_1", "href", {"txt": "", "de": f"{M}/blog/", "para": BLOG_EDGE}),
    ("A", f"{NEWS}/macnica-americas-adds-connect-tech-inc-to-supplier-portfolio-to-accelerate-edge-ai-innovation",
     "root/container/text_1_wrap/text_1", "href",
     {"txt": "deliver integrated AI and high-performance computing platforms", "de": f"{M}/blog", "para": BLOG_EDGE}),
    ("A", f"{NEWS}/macnica-americas-and-softron-to-showcase-apple-prores-with-st-2110-22-on-100gbs-mep100-smart-nic-at-ibc2025",
     "root/container/text_1_wrap/text_1", "href", {"txt": "MEP100 SmartNIC solution", "de": f"{M}/solutions", "para": BROADCAST}),
    ("A", f"{NEWS}/macnica-americas-introduces-100-gbps-mep100-smartnic-with-mac-compatibility",
     "root/container/text_1_wrap/text_1", "href", {"txt": "MEP100 SmartNIC solution", "de": f"{M}/solutions/", "para": BROADCAST}),
    ("A", f"{NEWS}/macnica-americas-introduces-100-gbps-mep100-smartnic-with-mac-compatibility",
     "root/container/heading_2_wrap/text_3", "href",
     {"txt": "https://www.macnica.com/mep100", "de": M, "para": "https://www.macnica.com/mep100"}),
    ("A", f"{NL}/supercharge-your-broadcast-workflow-with-macnicas-st-2110-solutions",
     "root/container/text_1_wrap/text_1", "href",
     {"txt": "Visit us online to discover more about the MEP100", "de": f"{M}/solutions", "para": BROADCAST}),
    ("A", f"{NL}/balancing-capex-and-opex-in-modern-media-workflows", "root/container/heading_1_wrap/text_2", "href",
     {"txt": "Learn more about how Sony’s new IMX925 series", "de": f"{M}/products/semiconductors",
      "para": f"{M}/products/semiconductors/sony/sony-image-sensors/sony-imx925-series-pushing-the-limits-of-speed-and-imaging-qual.html"}),
    ("A", f"{NL}/new-terasic-fpga-development-products", "root/container/button_2_wrap/button_2", "prop",
     {"prop": "linkURL", "de": f"{M}/products/boards-modules/terasic",
      "para": f"{M}/products/boards-modules/terasic/terasic-de25-standard-development-and-education-kit"}),
    ("A", f"{NEWS}/2024-02-15-macnica-americas-welcomes-sebastien-dignard-as-president", "root/container/heading_1_wrap/text_3",
     "href", {"txt": "Macnica Fuji Electronics Holdings, Inc", "de": M, "para": "https://www.macnica.com/"}),
    ("A", f"{NEWS}/macnica-appoints-sebastien-dignard-as-ceo-of-atlantic-region-to-accelerate-global-component-to-solutions-and-vertical-strategy",
     "root/container/text_1_wrap/text_1", "href", {"txt": "Europe", "de": M, "para": "/content/macnicaglobal2/eu/atd-europe/en.html"}),
    ("A", f"{NEWS}/ienso-to-showcase-generative-ai-at-the-edge-ces2025", "root/container/text_1_wrap/text_1", "href",
     {"txt": "www.macnica.com", "de": "/content/macnicaglobal2/", "para": "https://www.macnica.com/"}),   # GWI: https://www.macnica.com/
    ("A", "products/boards-modules/mpression",
     "root/container/container_76488194_c/flexcontainer_copy/flexcontaineritem_861351158/button", "prop",
     {"prop": "linkURL", "de": f"{M}/request-a-quote.html", "para": "https://www.m-pression.com/solutions/boards"}),
    ("A", "products/boards-modules/tq-systems", "root/container/container_2023615685/tabs_copy/item_1/table", "href",
     {"txt": "TQMa243xL",
      "de": "/content/macnicagwi/americas/mai/en/products/boards-modules/tq-systems/tq-embedded-arm-modules/tqma243xl-embedded-cortex-r5f-module.html",
      "para": f"{TQ}/tq-embedded-arm-modules/tqma243xl-embedded-cortex-r5f-module.html"}),
    ("A", "products/boards-modules/tq-systems", "root/container/container_2023615685/tabs_copy/item_2/table", "href",
     {"txt": "STKLS1028A",
      "de": "/content/macnicagwi/americas/mai/en/products/boards-modules/tq-systems/tq-embedded-qoriqr-layerscape/starterkit-stkls1028a.html",
      "para": f"{TQ}/tq-embedded-qoriqr-layerscape/starterkit-stkls1028a.html"}),

    # E = correção de um conserto nosso (24/09, pergunta do Hazael sobre domínio fixo): o GWI linka https://www.macnica.com/mep100,
    # que dá 302 -> /mep100/ -> 404 em produção (a vanity de verdade é /americas/mep100, da página macnica-mep-100); o A acima
    # copiou o link morto. Destino certo: a página do MEP100 no global2, sem domínio fixo.
    ("E", f"{NEWS}/macnica-americas-introduces-100-gbps-mep100-smartnic-with-mac-compatibility",
     "root/container/heading_2_wrap/text_3", "href",
     {"txt": "https://www.macnica.com/mep100", "de": "https://www.macnica.com/mep100",
      "para": f"{M}/products/macnica-products/macnica-mep-100.html",
      "por_que": "went to the site’s root; the GWI’s own URL (www.macnica.com/mep100) is dead in production (404), "
                 "so it now opens the MEP100 page"}),
    # F = destino que não existia no global2 (pedido do Hazael, 24/09): os 2 PDFs copiados do GWI pelo copiar_asset_gwi.py
    # e o post do blog, que EXISTE no global2 com outro nome (a Anion usou o título inteiro; o GWI corta em "hospital-eq")
    ("F", "products", "root/container/text_284935450", "href",
     {"txt": "Download the Macnica Americas Linecard here",
      "de": "https://www.macnica.com/content/dam/macnicagwi/americas/mai/public/en/downloads/macnica-americas-linecard.pdf",
      "para": "/content/dam/macnicaglobal2/americas/mai/en/downloads/macnica-americas-linecard.pdf",
      "por_que": "still opened the GWI’s file; the PDF was copied into the global2 DAM"}),
    ("F", "products/boards-modules/iei/iei-networking-servers", "root/container/container_849791024/button_copy", "prop",
     {"prop": "linkURL", "de": f"{M}/products/boards-modules/iei/iei-networking-servers",
      "para": "/content/dam/macnicaglobal2/americas/mai/en/products/boards-modules/iei/pdfs/iei-puzzle-brochure-2024.pdf",
      "por_que": "opened its own page instead of the brochure; the PDF was copied into the global2 DAM"}),
    ("F", f"{NL}/macnicas-medical-healthcare-solutions", "root/container/button_1_wrap/button_1", "prop",
     {"prop": "linkURL", "de": f"{M}/blog",
      "para": f"{M}/blog/macnica-medical-displays-quality-and-innovation-for-hospital-equipment",
      "por_que": "was cut off at the blog; the post exists in global2 under a longer name than the GWI’s"}),
    ("B", f"{NEWS}/macnica-ships-mep100-smartnic-solution-as-ibc2024-approaches", "root/container/heading_1_wrap/heading_1",
     "prop", {"prop": "linkURL", "de": None, "para": "https://macnicatech.com/wp-content/uploads/2024/08/MEP100-2-pager-202408a.pdf"}),
    ("B", "products/boards-modules/iei/iei-intelligent-body-temperature-monitoring-solution",
     "root/container/container_1810978923/image", "prop",
     {"prop": "linkURL", "de": None,
      "para": "https://dls.ieiworld.com/IEIWEB/MARKETING_MATERIAL/2022_brochure/51_Body20Temperature20Monitoring20Solution_EN_20210224.pdf"}),
    ("B", "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing",
     "root/container/container_596104355/container_1619395209/title_text_1593331769", "prop",
     {"prop": "linkURL", "de": None, "para": "https://www.ieiworld.com/en/product/items_by_cat.php?CA=5&sub_cat=20&go_mark=c2_20"}),
    ("B", f"{EV}/2018-04-10-the-vision-show", "root/container/text_1_wrap/title_text_1", "prop",
     {"prop": "linkURL", "de": None, "para": "https://www.visionshow.org/"}),
    ("B", f"{EV}/2019-06-26-embedded-technologies-expo-conference", "root/container/container_evento/text", "wrap",
     {"de": "<b>Embedded Technologies Expo &amp; Conference 2019</b>",
      "para": '<b><a href="https://www.embeddedtechconf.com/" target="_blank">Embedded Technologies Expo &amp; Conference 2019</a></b>'}),
    ("B", f"{EV}/2023-03-28-isc-west-2023", "root/container/container_evento/text", "wrap",
     {"de": "<b>https://conta.cc/40lSQbT</b>",
      "para": '<b><a href="https://conta.cc/40lSQbT" target="_blank">https://conta.cc/40lSQbT</a></b>'}),
]
# C: o título (h1) do evento ganha o link do GWI; a URL vem do relatório (o link que faltava na página)
EVENTOS_C = ["2015-04-14-nab-show-2015", "2015-09-12-ibc-2015", "2016-04-19-nab-show-2016", "2016-08-18-intel-isdf-2016",
             "2016-09-10-ibc-2016", "2017-09-16-ibc-2017", "2019-02-06-ise-2019", "2019-04-09-nab-show-2019",
             "2019-06-12-infocomm-2019"]

sessao, _ = build_session(prompt_if_missing=False, verbose=False)


def url(path, sufixo=""):
    return BASE + quote(unquote(path), safe="/:") + sufixo


def ler(path, sufixo=".json"):
    r = sessao.get(url(path, sufixo), timeout=120, allow_redirects=False)
    return r.status_code, (r.json() if r.status_code == 200 else None)


def texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or "")).replace(" ", " ")).strip()


A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.I | re.S)
HREF_RE = re.compile(r"""(\bhref\s*=\s*)(["'])(.*?)\2""", re.I | re.S)


def novo_valor(tipo, d, atual):
    """(novo, motivo_para_pular). `atual` = valor da propriedade agora."""
    if tipo == "prop":
        if atual == d["para"]:
            return None, "já está certo"
        if atual != d["de"]:
            return None, f"valor atual inesperado: {atual!r}"
        return d["para"], None
    if not isinstance(atual, str):
        return None, "propriedade ausente"
    if tipo == "ext":
        novo, feitos = atual, 0
        for de, para in d["trocas"]:
            for forma in {de, html.escape(de, quote=True)}:
                alvo = f'href="{forma}"'
                if alvo in novo:
                    feitos += novo.count(alvo)
                    novo = novo.replace(alvo, f'href="{html.escape(para, quote=True)}"')
        return (novo, None) if feitos else (None, "nenhum dos hrefs está mais lá (já consertado?)")
    if tipo == "wrap":
        n = atual.count(d["de"])
        if n != 1:
            return None, ("já está certo" if d["para"] in atual else f"trecho aparece {n} vezes")
        return atual.replace(d["de"], d["para"]), None
    # href: <a> com href == de (comparado sem escapes) e texto que começa com txt ("" = link invisível)
    achados = []
    for m in A_RE.finditer(atual):
        h = HREF_RE.search(m.group(1))
        if not h or html.unescape(h.group(3)).strip() != d["de"]:
            continue
        t = texto(m.group(2))
        if (t == "" if d["txt"] == "" else t.startswith(d["txt"])):
            achados.append((m, h))
    if len(achados) != 1:
        ja = any(html.unescape((HREF_RE.search(m.group(1)) or [None] * 4)[3] or "").strip() == d["para"]
                 and (texto(m.group(2)) == "" if d["txt"] == "" else texto(m.group(2)).startswith(d["txt"]))
                 for m in A_RE.finditer(atual))
        return None, ("já está certo" if ja else f"{len(achados)} links casam (texto+href)")
    m, h = achados[0]
    ini = m.start(1) + h.start(3)
    fim = m.start(1) + h.end(3)
    return atual[:ini] + html.escape(d["para"], quote=True) + atual[fim:], None


def normal_aem(v):
    if not isinstance(v, str):
        return v
    v = re.sub(r'\s+rel="noopener noreferrer"', "", v)
    return re.sub(r"<br\s*/?>", "<br>", v)


def trecho(antes, depois, largura=90):
    """O pedaço que muda, com contexto (para ler no terminal)."""
    i = 0
    while i < min(len(antes), len(depois)) and antes[i] == depois[i]:
        i += 1
    j = 0
    while j < min(len(antes), len(depois)) - i and antes[-1 - j] == depois[-1 - j]:
        j += 1
    ctx = lambda s: re.sub(r"\s+", " ", s[max(0, i - largura): len(s) - j + largura])
    return ctx(antes), ctx(depois)


def alvo_interno(u):
    if not u.startswith("/content/"):
        return None
    base = re.sub(r"\.html$", "", u.split("#")[0].split("?")[0])
    st, j = ler(base + "/jcr:content")
    return "404" if st != 200 else ("SOFT-DELETED" if j.get("deleted") else "ok")


def plano(grupos):
    rel = json.load(open(RELATORIO))
    faltando = {r["g2"]: r["faltando"] for r in rel["paginas"]}
    lista = [c for c in CONSERTOS if c[0] in grupos]
    if "C" in grupos:
        for ev in EVENTOS_C:
            f = [x for x in faltando.get(f"{M}/{EV}/{ev}", []) if not x["via"] and x["href"].startswith("http")]
            assert len(f) == 1, (ev, f)
            lista.append(("C", f"{EV}/{ev}", "root/container/title_wrap/title", "prop",
                          {"prop": "linkURL", "de": None, "para": f[0]["href"], "gwi_txt": f[0]["txt"]}))
    return lista


def plano_d(lista_abc):
    """D: todo <a> interno do global2 sem .html nos textos das páginas do relatório (menos as protegidas), a partir do cache
    da coleta (links_vs_gwi); o valor é relido ao vivo na hora. Alvo tem de existir no global2 (lista da coleta)."""
    import pickle
    import links_vs_gwi as LV
    from aem_lib import carregar_protegidas
    b = pickle.loads(LV.CACHE.read_bytes())
    idx = LV.Indice(b)
    prot = set(carregar_protegidas())
    rel = json.load(open(RELATORIO))
    ja = {(p, no, d["de"]) for _, p, no, t, d in lista_abc if t == "href"}          # A cuida destes
    por_no, sem_alvo = {}, []
    for r in rel["paginas"]:
        pag = r["g2"]
        if pag in prot:
            continue
        for ln in LV.links_de(b["jcr"][pag], "jcr:content", [], __import__("collections").Counter()):
            if LV.PROP_LINK.search(ln["prop"]) or ln["prop"] == "cq:redirectTarget":
                continue                                        # button/image/title: o core já põe .html
            a = LV.alvo(ln["href"])
            if a["kind"] != "pagina" or a["site"] != "macnicaglobal2":
                continue
            h = html.unescape(ln["href"]).strip()
            base = re.split(r"[?#]", h, 1)[0]
            resto = h[len(base):]
            if base.endswith(".html"):
                continue
            no = ln["no"][len("jcr:content/"):]
            if (pag[len(M) + 1:], no, h) in ja:
                continue
            q = idx.g2_n.get(LV.nrel(a["rel"]))
            if not q or LV.Indice._morta(idx.g2[q]):
                sem_alvo.append((pag, h)); continue
            por_no.setdefault((pag[len(M) + 1:], no, ln["prop"]), {})[h] = q + ".html" + resto
    out = [("D", p, no, "ext", {"prop": prop, "trocas": sorted(t.items())}) for (p, no, prop), t in sorted(por_no.items())]
    return out, sem_alvo


# ---------------------------------------------------------------- antes x depois (pedido do Hazael, 24/09)
DL_RE = re.compile(r"""\sdata-cmp-data-layer=(["']).*?\1""", re.S)      # JSON do data layer: tem repo:modifyDate e o html
# qualquer edição faz o AEM carimbar a PÁGINA (cq:lastModified[By] do jcr:content) e a data aparece no data layer da página
# (repo:modifyDate, dentro de <script>, escapada com \x22/\u002D) — medido na 1ª verificação de 24/09: 52/52 só com isso
MODIFY_RE = re.compile(r"(repo:modifyDate.{0,24}?)\d{4}(?:\\u002D|-)\d{2}(?:\\u002D|-)\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", re.S)
CARIMBO_PAGINA = {("", "cq:lastModified"), ("", "cq:lastModifiedBy")}


def retrato(pag):
    """(jcr:content inteiro, html renderizado fora do editor) da página — o 'antes' e o 'depois'."""
    import links_vs_gwi as LV
    j, st = LV.fundo(f"{pag}/jcr:content")
    if j is None:
        raise SystemExit(f"[ABORTADO] retrato de {pag}: HTTP {st}")
    r = sessao.get(url(pag, ".html") + "?wcmmode=disabled", timeout=180, allow_redirects=False)
    if r.status_code != 200:
        raise SystemExit(f"[ABORTADO] render de {pag}: HTTP {r.status_code}")
    return j, r.text


def achatar(no, cam="", out=None):
    out = {} if out is None else out
    for k, v in no.items():
        if isinstance(v, dict):
            achatar(v, f"{cam}/{k}" if cam else k, out)
        else:
            out[(cam, k)] = v
    return out


def normalizar(h):
    """O render sem o que um link muda: tags <a>/</a> (e o href dentro delas) e o JSON do data layer."""
    h = DL_RE.sub("", h)
    h = MODIFY_RE.sub(r"\1<data>", h)
    h = re.sub(r"<a\b[^>]*>|</a\s*>", "", h, flags=re.I)
    return re.sub(r"\s+", " ", h).strip()


def comparar_pagina(antes, depois, escritos):
    """Diferenças que NÃO deviam existir. `escritos` = {(nó rel ao jcr:content, prop)} gravados nesta página."""
    ja, jd = achatar(antes[0]), achatar(depois[0])
    permitidas = set(escritos) | {(no, k) for no, _ in escritos for k in ("jcr:lastModified", "jcr:lastModifiedBy")}
    if escritos:
        permitidas |= CARIMBO_PAGINA
    jcr = sorted(f"{no}.{k}" for no, k in set(ja) | set(jd) if ja.get((no, k)) != jd.get((no, k)) and (no, k) not in permitidas)
    na, nd = normalizar(antes[1]), normalizar(depois[1])
    render = None
    if na != nd:
        i = next(i for i in range(min(len(na), len(nd))) if na[i] != nd[i]) if na[:min(len(na), len(nd))] != nd[:min(len(na), len(nd))] else min(len(na), len(nd))
        render = f"…{na[max(0, i - 80):i + 120]}…  ≠  …{nd[max(0, i - 80):i + 120]}…"
    links = lambda h: sorted(re.findall(r'href="([^"]*)"', DL_RE.sub("", h)))
    trocados = sorted(set(links(antes[1])) ^ set(links(depois[1])))
    return jcr, render, trocados


def verificar(pasta, quando):
    """Página inteira de hoje x backup `pasta`; o que foi gravado vem do manifesto (linhas com esse `quando`)."""
    jcr_antes = json.loads((pasta / "jcr_content.json").read_text(encoding="utf-8"))
    render_antes = json.loads((pasta / "render.json").read_text(encoding="utf-8"))
    escritos = {}
    for linha in (DADOS / "manifesto_links.jsonl").read_text(encoding="utf-8").splitlines():
        x = json.loads(linha)
        if x.get("quando") == quando and x.get("status") == "gravado":
            escritos.setdefault(x["pagina"][len(M) + 1:], set()).add((x["no"], x["prop"]))
    out, problemas = [], 0
    print("\n== antes x depois (página inteira) ==")
    for p in sorted(jcr_antes):
        jcr, render, trocados = comparar_pagina((jcr_antes[p], render_antes[p]), retrato(f"{M}/{p}"), escritos.get(p, set()))
        ok = not jcr and not render
        problemas += not ok
        print(f"{'OK ' if ok else 'DIFERENÇA'} /{p}: {len(escritos.get(p, ()))} propriedade(s) gravada(s); "
              f"hrefs que mudaram no render: {len(trocados)}" + (f"\n     JCR fora do previsto: {jcr}" if jcr else "")
              + (f"\n     render: {render}" if render else ""))
        out.append({"pagina": p, "gravadas": sorted(map(list, escritos.get(p, ()))),
                    "comparacao": {"jcr": jcr, "render": render, "hrefs_render": trocados}})
    print(f"{len(jcr_antes) - problemas}/{len(jcr_antes)} páginas iguais ao backup fora dos links")
    (pasta / "comparacao.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grupos", nargs="+", default=["A", "B", "C", "D"], choices=["A", "B", "C", "D", "E", "F"])
    ap.add_argument("--executar", action="store_true", help="grava (sem isto: só GET)")
    ap.add_argument("--verificar", metavar="PASTA", help="só GET: compara as páginas de hoje com o backup (backup_links_<data>)")
    ap.add_argument("--testar-comparador", type=int, metavar="N", default=0,
                    help="só GET: tira o retrato de N páginas do plano duas vezes e compara (tem de dar zero diferença)")
    a = ap.parse_args()
    if a.verificar:
        pasta = Path(a.verificar)
        verificar(pasta, pasta.name[len("backup_links_"):])
        return
    lista = plano(set(a.grupos) - {"D"})
    sem_alvo = []
    if "D" in a.grupos:
        d, sem_alvo = plano_d(plano({"A"}))
        lista += d
    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    paginas = sorted({p for _, p, _, _, _ in lista})

    if a.testar_comparador:
        for p in paginas[:a.testar_comparador]:
            r1, r2 = retrato(f"{M}/{p}"), retrato(f"{M}/{p}")
            jcr, render, trocados = comparar_pagina(r1, r2, set())
            print(f"{'OK ' if not (jcr or render or trocados) else 'DIF'} /{p}  jcr={jcr[:3]} render={render} links={trocados[:3]}")
        return

    retratos = {}
    if a.executar:                                              # backup ANTES de qualquer escrita: jcr:content + render
        pasta = DADOS / f"backup_links_{agora}"
        pasta.mkdir(parents=True)
        for p in paginas:
            retratos[p] = retrato(f"{M}/{p}")
        (pasta / "jcr_content.json").write_text(json.dumps({p: v[0] for p, v in retratos.items()}, ensure_ascii=False),
                                                encoding="utf-8")
        (pasta / "render.json").write_text(json.dumps({p: v[1] for p, v in retratos.items()}, ensure_ascii=False),
                                           encoding="utf-8")
        print(f"backup: {len(retratos)} páginas (jcr:content inteiro + render) -> {pasta}\n")

    resumo, saida = {"muda": 0, "pula": 0, "gravado": 0, "falhou": 0}, []
    pagina_ant = None
    for g, p, no, tipo, d in lista:
        pag = f"{M}/{p}"
        caminho = f"{pag}/jcr:content/{no}"
        if p != pagina_ant:
            st, jc = ler(f"{pag}/jcr:content")
            print(f"## [{g}] /{p}\n   último editor {jc.get('cq:lastModifiedBy')} {str(jc.get('cq:lastModified'))[4:21]}"
                  if jc else f"## [{g}] /{p}  HTTP {st}")
            pagina_ant = p
        st, nod = ler(caminho)
        prop = d.get("prop", "text")
        if st != 200:
            print(f"   PULA  {no}: nó HTTP {st}"); resumo["pula"] += 1; continue
        novo, pula = novo_valor(tipo, d, nod.get(prop))
        bloq = motivo_bloqueio("POST", url(caminho), {prop: "x"})
        dest = alvo_interno(d["para"]) if tipo not in ("wrap", "ext") else None
        linha = {"grupo": g, "pagina": pag, "no": no, "prop": prop, "tipo": tipo, "para": d.get("para") or d.get("trocas"),
                 "alvo": dest}
        if pula or bloq or dest in ("404", "SOFT-DELETED"):
            motivo = pula or bloq or f"alvo {dest}"
            print(f"   PULA  {no.rsplit('/', 1)[-1]}.{prop}: {motivo}")
            resumo["pula"] += 1; saida.append(dict(linha, status="pula", motivo=motivo)); continue
        if tipo == "prop":
            print(f"   MUDA  {no.rsplit('/', 1)[-1]}.{prop} ({nod.get('sling:resourceType', '').rsplit('/', 1)[-1]}"
                  f" “{texto(nod.get('jcr:title') or nod.get('alt') or '')[:50]}”)\n"
                  f"         antes: {nod.get(prop)!r}\n         depois: {novo!r}" + (f"   [alvo {dest}]" if dest else ""))
        elif tipo == "ext":
            print(f"   MUDA  {no.rsplit('/', 1)[-1]}.{prop} (ext: {len(d['trocas'])} href)")
            for de, para in d["trocas"]:
                print(f"         {de[len(M):] or de}  ->  {para[len(M):]}")
        else:
            antes, depois = trecho(nod[prop], novo)
            print(f"   MUDA  {no.rsplit('/', 1)[-1]}.{prop} ({tipo})\n         antes: …{antes}…\n         depois: …{depois}…"
                  + (f"   [alvo {dest}]" if dest else ""))
        resumo["muda"] += 1
        if not a.executar:
            saida.append(dict(linha, status="dry")); continue
        try:
            r = sessao.post(url(caminho), data={prop: novo, "_charset_": "utf-8"}, timeout=120)
        except EscritaProibida as e:
            print(f"         BARRADO: {e}"); resumo["falhou"] += 1; saida.append(dict(linha, status="barrado")); continue
        st2, depois_no = ler(caminho)
        mudou = {k for k in set(nod) | set(depois_no or {}) if (nod.get(k) != (depois_no or {}).get(k))}
        salvo = (depois_no or {}).get(prop)
        # o AEM normaliza o HTML ao salvar: rel="noopener noreferrer" em link com target=_blank e <br> -> <br />
        # (medido em 24/09, grupo B); igual depois disso = gravado como enviado
        ok = r.status_code in (200, 201) and depois_no and (salvo == novo or normal_aem(salvo) == normal_aem(novo)) and \
            mudou <= {prop, "jcr:lastModified", "jcr:lastModifiedBy"}
        print(f"         {'GRAVADO' if ok else 'FALHOU'}: HTTP {r.status_code}; mudou {sorted(mudou)}")
        resumo["gravado" if ok else "falhou"] += 1
        saida.append(dict(linha, status="gravado" if ok else "falhou", http=r.status_code, mudou=sorted(mudou)))
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps(dict(linha, quando=agora, status=saida[-1]["status"], antes=nod.get(prop)),
                               ensure_ascii=False) + "\n")

    if a.executar:                                              # depois: página inteira contra o backup
        saida += verificar(DADOS / f"backup_links_{agora}", agora)

    if sem_alvo:
        print(f"\nD: {len(sem_alvo)} href sem .html cujo alvo NÃO existe no global2 (não mexidos): " +
              "; ".join(f"{p[len(M):]} -> {h[len(M):]}" for p, h in sem_alvo))
    print(f"\n{len(lista)} consertos em {len(paginas)} páginas: {resumo}" + ("" if a.executar else "  (DRY-RUN: nada gravado)"))
    (DADOS / f"corrigir_links_{'exec' if a.executar else 'dry'}_{agora}.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
