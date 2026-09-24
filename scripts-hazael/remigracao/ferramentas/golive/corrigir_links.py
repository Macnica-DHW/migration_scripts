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

Nenhum nó é criado, movido ou apagado; nenhuma outra propriedade muda. Título com link no global2 renderiza igual ao
sem link (medido em atd-europe/sony-gnss: mesma cor, peso, tamanho, sem sublinhado, mesma altura).

Grupos: A = href errado (13 links, 10 páginas); B = link num elemento que já existe (6); C = eventos: link no título
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
BLOG_EDGE = f"{M}/blog/removing-the-barriers-to-edge-and-gen-ai-in-embedded-vision"
BROADCAST = f"{M}/solutions/broadcast-proav-solutions"
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
      "para": f"{M}/products/semiconductors/sony/sony-image-sensors/sony-imx925-series-pushing-the-limits-of-speed-and-imaging-qual"}),
    ("A", f"{NL}/new-terasic-fpga-development-products", "root/container/button_2_wrap/button_2", "prop",
     {"prop": "linkURL", "de": f"{M}/products/boards-modules/terasic",
      "para": f"{M}/products/boards-modules/terasic/terasic-de25-standard-development-and-education-kit"}),
    ("A", f"{NEWS}/2024-02-15-macnica-americas-welcomes-sebastien-dignard-as-president", "root/container/heading_1_wrap/text_3",
     "href", {"txt": "Macnica Fuji Electronics Holdings, Inc", "de": M, "para": "https://www.macnica.com/"}),
    ("A", f"{NEWS}/macnica-appoints-sebastien-dignard-as-ceo-of-atlantic-region-to-accelerate-global-component-to-solutions-and-vertical-strategy",
     "root/container/text_1_wrap/text_1", "href", {"txt": "Europe", "de": M, "para": "/content/macnicaglobal2/eu/atd-europe/en"}),
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--grupos", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
    ap.add_argument("--executar", action="store_true", help="grava (sem isto: só GET)")
    a = ap.parse_args()
    lista = plano(set(a.grupos))
    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    paginas = sorted({p for _, p, _, _, _ in lista})

    if a.executar:                                              # backup ANTES de qualquer escrita
        backup = {}
        for p in paginas:
            st, j = ler(f"{M}/{p}/jcr:content", ".infinity.json")
            if st != 200:
                sys.exit(f"[ABORTADO] backup de {p}: HTTP {st}")
            backup[p] = j
        arq = DADOS / f"backup_links_{agora}.json"
        arq.write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")
        print(f"backup: {len(backup)} páginas -> {arq}\n")

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
        dest = alvo_interno(d["para"]) if tipo != "wrap" else None
        linha = {"grupo": g, "pagina": pag, "no": no, "prop": prop, "tipo": tipo, "para": d["para"], "alvo": dest}
        if pula or bloq or dest in ("404", "SOFT-DELETED"):
            motivo = pula or bloq or f"alvo {dest}"
            print(f"   PULA  {no.rsplit('/', 1)[-1]}.{prop}: {motivo}")
            resumo["pula"] += 1; saida.append(dict(linha, status="pula", motivo=motivo)); continue
        if tipo == "prop":
            print(f"   MUDA  {no.rsplit('/', 1)[-1]}.{prop} ({nod.get('sling:resourceType', '').rsplit('/', 1)[-1]}"
                  f" “{texto(nod.get('jcr:title') or nod.get('alt') or '')[:50]}”)\n"
                  f"         antes: {nod.get(prop)!r}\n         depois: {novo!r}" + (f"   [alvo {dest}]" if dest else ""))
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
        ok = r.status_code in (200, 201) and depois_no and depois_no.get(prop) == novo and \
            mudou <= {prop, "jcr:lastModified", "jcr:lastModifiedBy"}
        print(f"         {'GRAVADO' if ok else 'FALHOU'}: HTTP {r.status_code}; mudou {sorted(mudou)}")
        resumo["gravado" if ok else "falhou"] += 1
        saida.append(dict(linha, status="gravado" if ok else "falhou", http=r.status_code, mudou=sorted(mudou)))
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps(dict(linha, quando=agora, status=saida[-1]["status"], antes=nod.get(prop)),
                               ensure_ascii=False) + "\n")

    print(f"\n{len(lista)} consertos em {len(paginas)} páginas: {resumo}" + ("" if a.executar else "  (DRY-RUN: nada gravado)"))
    (DADOS / f"corrigir_links_{'exec' if a.executar else 'dry'}_{agora}.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
