#!/usr/bin/env python3
"""
Remigra `semiconductors` do GWI para uma árvore NOVA, no dialeto Anion.

DESTINO: `/content/copia-teste/americas/mai/en/products/semiconductors-remigration`

É árvore de rascunho, criada do zero. **Nada em `/semiconductors` é tocado** —
as edições manuais do Bruno no `/canon` (79 nós, incluindo 8 blocos de texto em
português que não existem no GWI e uma anotação viva) continuam onde estão.
Também não se escreve em `macnicagwi` — NUNCA, regra mestra do Hazael — nem em
`macnicaglobal2`, salvo com `--alvo-global2` (autorizado em 21/09/2026 para
`/technology` e `/services`; travas em `remigracao/ferramentas/golive/direto.py`).

ESCOPO: 135 páginas — tudo em `/semiconductors` que a Anion ainda NÃO autorou.
Fora: `sony-image-sensors` (216) e `deepx` (3). Conferido: o global2 só tem
`sony`, `deepx`, `Titles` e `sony-test` no ramo, então não há nada autoral fora
desses caminhos.

O QUE MUDA EM RELAÇÃO AO `aem_migrate.py`
O motor de layout é o `aem_lib` -> `aem_layout` (ver o docstring de lá para a
regra de fronteira de seção e sua validação). Este script é só o driver:
percorre, resolve o que depende de rede, cria a página e grava.

O QUE ESTE DRIVER RESOLVE, QUE O MOTOR SOZINHO NÃO CONSEGUE
  - **rótulo de download**: vem do `dc:title` do asset no DAM. NUNCA do nome
    do arquivo — é isso que produz os 506 rótulos inventados de hoje (tipo
    'multi power sequencer 2.1.2' onde o `dc:title` é 'Multi-Rail Power
    Sequencer and Monitor - Complete Archive').
  - **`relatedsuggestions` nos modos `children` e `search`**: materializa em
    `static` resolvendo contra o GWI. Manter `children` faria o `parentPage`
    reescrito avaliar a árvore de DESTINO, que tem outro conjunto de filhos —
    deriva silenciosa (é o que acontece hoje em 44 páginas).
  - **assets**: copia do DAM do GWI para o de `copia-teste` (`copy_asset` é
    idempotente e confere o destino antes).

CONVENÇÕES
  - Diagnóstico é o padrão. Só escreve com `--executar`.
  - Trava de escrita: só `copia-teste`.
  - CSV de páginas + CSV de pendências, sempre.
  - Pendência é explícita: nada é descartado em silêncio.

COMO RODAR
  python3 aem_remigrar.py --limite 3                 # dry-run, 3 páginas
  python3 aem_remigrar.py --so /altera --executar    # uma subárvore
  python3 aem_remigrar.py --executar                 # as 135

  # outra seção, DIRETO no global2 (dry-run; o `= servidor`/`MUDA` sai na tela):
  python3 aem_remigrar.py --origem <gwi>/technology --destino <global2>/solutions \
      --alvo-global2 --template-por-origem --so-publicadas \
      --gemeos-conhecidos <global2>/technology/Broadcast-ProAV-Solutions …
  # gravar: só as que MUDAM, com --paginas <lista> --executar; depois
  # remigracao/ferramentas/golive/conferir_direto.py <csv do driver>
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_page_payload, build_pd_props, build_seo_props,
                     build_session, build_tag_props, copy_asset, crawl_tree,
                     delete_node, detect_tag_region, get_json, load_tag_taxonomy,
                     normalize_name, post_node, print_header, session_expired,
                     write_csv)
import aem_layout as AL

# Os popups de sucesso/erro do form (R27) vivem no espelho de XFs do rascunho
# (AEM_EF_ROOT), criados por remigracao/ferramentas/criar_xf_popups.py. No
# go-live o caminho vira /content/experience-fragments/macnicaglobal2/americas/
# mai/en/site/popups — a convenção que a APAC já usa.
AL.XF_FORM_POPUPS = CONFIG["ef_root"].rstrip("/") + "/popups"

GWI_ROOT = "/content/macnicagwi/americas/mai/en/products/semiconductors"
DEST_ROOT = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
TEMPLATE = "/conf/macnicaglobal2/settings/wcm/templates/mai-mae-product-page"

# A Anion já fez estes ramos; remigrar seria retrabalho e risco.
FORA_DE_ESCOPO = ("sony", "deepx")

# O diálogo com os fieldsets Model Information / Product Hierarchy Details só
# existe no maeproductpage (24.874 bytes contra 3.162 do page). Com
# `components/page` o autor não consegue nem ver nem editar as propriedades
# pd_*. As 16 páginas migradas hoje estão todas erradas nisso.
PAGE_RT = "macnicaglobal2/components/maeproductpage"

# Página de CONTEÚDO (`/technology`, `/services`): o GWI usa `base-page-content` e as cascas que o
# time do site criou no global2 usam `mai-page-content` + `components/page`. Conferido em
# 21/09/2026: os 24 mapeamentos de policy e a structure são IDÊNTICOS aos do `mai-mae-product-page`
# — os styleIds do motor valem igual. Só com `--template-por-origem` (as 136 não mudam).
TEMPLATE_CONTEUDO = "/conf/macnicaglobal2/settings/wcm/templates/mai-page-content"
PAGE_RT_CONTEUDO = "macnicaglobal2/components/page"


def template_de(jcr, por_origem):
    tpl = str(jcr.get("cq:template", "")).rsplit("/", 1)[-1]
    if por_origem and tpl == "base-page-content":
        return TEMPLATE_CONTEUDO, PAGE_RT_CONTEUDO
    return TEMPLATE, PAGE_RT


def destino_de(origem):
    """Caminho equivalente no destino, com os nomes normalizados.

    `normalize_name` importa: o GWI tem nós com maiúscula e o destino
    normaliza para minúscula. Copiar sem casar cria página nova e deixa a
    antiga órfã — foram 29 assim em tq-systems.
    """
    rel = origem[len(GWI_ROOT):].strip("/")
    if not rel:
        return DEST_ROOT
    partes = [normalize_name(p) for p in rel.split("/")]
    return DEST_ROOT + "/" + "/".join(partes)


def em_escopo(origem):
    rel = origem[len(GWI_ROOT):].strip("/")
    if not rel:
        # A própria landing `/semiconductors` é conteúdo (23 unidades de texto,
        # manchete + introdução + os 16 fabricantes) e a Anion não a autorou.
        # Deixá-la de fora era um furo de escopo, não uma decisão.
        return True
    return not rel.split("/")[0].startswith(FORA_DE_ESCOPO)


def normalizar_links_do_escopo(payload, link_de, link_para):
    """href para página do ESCOPO leva o nome de nó NORMALIZADO.

    `destino_de` normaliza o nome (`canon-li8030SA-…` -> `canon-li8030sa-…`,
    5 páginas). A `list` já grava o nome novo, mas o href de rich text só
    troca o prefixo (`rewrite_links_in_html`) e seguia apontando para o nome
    antigo: 404 no go-live. Só dentro do escopo — sony/deepx são da Anion e
    têm os nomes que ela deu.
    """
    raiz = link_para + GWI_ROOT[len(link_de):]
    padrao = re.compile(re.escape(raiz) + r"((?:/[A-Za-z0-9_-]+)+)")

    def troca(m):
        if not em_escopo(GWI_ROOT + m.group(1)):
            return m.group(0)
        return raiz + "/".join(normalize_name(x) if x else x
                               for x in m.group(1).split("/"))

    for k, v in payload.items():
        if isinstance(v, str) and raiz in v:
            payload[k] = padrao.sub(troca, v)

SUPPLIERLIST_RT = "macnicagwi/components/content/supplierlist"
_RC_RT = "macnicagwi/components/content/resizablecontainer"
_BANNER_RT = "macnicagwi/components/content/bannerimage"


def materializar_supplierlists(session, base_url, auth, jcr, cache):
    """`supplierlist` -> grade de logos com link e legenda (R59). Devolve os logos dos cards.

    O GWI desenha, para cada página da lista (estática, na ordem de `pages`), um
    card: o `manufacturerlogo` da página LINKADA, o `navTitle` dela embaixo e o
    card inteiro como link — 4 por linha. Nada disso está no nó: depende de ler
    as páginas dos fornecedores, por isso mora no driver (como o `related`).

    Em vez de inventar um emissor, o nó é REESCRITO no JCR da origem (em
    memória) na estrutura que o motor já sabe migrar e que a landing
    `/technology` usa: colunas de largura 3, cada uma com um `bannerimage`
    (imagem com link; o `subText` vira a legenda visível, R58). Sem isto a aba
    "Suppliers/Partners" da `imaging-and-vision` saía com 6 títulos e nada
    embaixo (3.180px no GWI, 828 no destino) — apontado pelo Hazael em 21/09/2026.
    Lista que não é estática, ou página sem logo, fica como estava (pendência).
    """
    feitas = 0

    def anda(no):
        nonlocal feitas
        for k, v in list(no.items()):
            if not isinstance(v, dict):
                continue
            if v.get("sling:resourceType") != SUPPLIERLIST_RT:
                anda(v)
                continue
            pages = v.get("pages")
            pages = [pages] if isinstance(pages, str) else [x for x in (pages or []) if x]
            if str(v.get("listFrom") or "static").lower() != "static" or not pages:
                continue
            cards = {}
            for i, pg in enumerate(pages, 1):
                if pg not in cache:
                    pj, st = get_json(session, f"{base_url}{pg}/jcr:content.1.json", auth)
                    cache[pg] = pj if st == 200 and isinstance(pj, dict) else {}
                pj = cache[pg]
                logo = (pj.get("manufacturerlogo") or {}).get("fileReference")
                if not logo:
                    cards = None
                    break
                nome = (pj.get("navTitle") or pj.get("jcr:title") or pg.rsplit("/", 1)[-1]).strip()
                cards[f"card_{i}"] = {
                    "jcr:primaryType": "nt:unstructured", "sling:resourceType": _RC_RT,
                    "cq:responsive": {"default": {"width": "3", "offset": "0"}},
                    "logo": {"jcr:primaryType": "nt:unstructured", "sling:resourceType": _BANNER_RT,
                             "fileReference": logo, "linkURL": pg, "subText": nome, "alt": nome}}
            if not cards:
                continue
            no[k] = {"jcr:primaryType": "nt:unstructured", "sling:resourceType": _RC_RT, **cards}
            logos.update(c["logo"]["fileReference"] for c in cards.values())
            feitas += 1

    logos = set()
    anda(jcr)
    return logos


def titulo_do_asset(session, base_url, auth, ref, cache):
    """`dc:title` do asset no DAM. Sem inventar nada a partir do nome."""
    if ref in cache:
        return cache[ref]
    d, st = get_json(session, f"{base_url}{ref}/jcr:content/metadata.json", auth)
    titulo = ""
    if st == 200 and isinstance(d, dict):
        t = d.get("dc:title")
        if isinstance(t, list):
            t = t[0] if t else ""
        titulo = (t or "").strip()
    cache[ref] = titulo
    return titulo


def resolver_related(session, base_url, auth, bloco, origem_pagina):
    """Materializa `children`/`search` em lista estática, contra o GWI.

    Respeita `orderBy`, `sortOrder` e `maxItems` da origem: o
    `productlisting` da `/ambarella` tem maxItems=2 e orderBy=jcr:title, e
    ignorar isso traria a lista inteira em vez dos dois cards que o GWI mostra.
    """
    modo = (bloco.props.get("listFrom") or "static").lower()
    pages = bloco.props.get("pages")
    if isinstance(pages, str):
        pages = [pages]
    # `pages` só vale em `static`. Em `children` o GWI IGNORA a propriedade:
    # o productlisting da `/canon` tem listFrom=children e um `pages` residual
    # com 6 caminhos (2 já são 404 no próprio GWI), e a tela do GWI mostra os
    # 13 filhos. Devolver `pages` antes de olhar o modo gravava os 6 — e só 4
    # renderizavam (R5). Ver R11.
    if modo == "static":
        return [p for p in (pages or []) if p]

    if modo == "children":
        pai = bloco.props.get("parentPage") or origem_pagina
        d, st = get_json(session, f"{base_url}{pai}.2.json", auth)
        if st != 200 or not isinstance(d, dict):
            return []
        # `orderBy` decide a CHAVE: o productlisting usa `pageTitle`, o
        # relatedsuggestions usa `title` (= jcr:title). Ordenar sempre por
        # jcr:title trocava a ordem dos cards na `/altera/altera-stratix-10`
        # (NX antes de AX) e na `/altera/development-kits` — com
        # faltando=0 sobrando=0, porque ordem não é conteúdo (R11).
        chave = str(bloco.props.get("orderBy") or "title").lower()

        def valor(conteudo, nome):
            if chave == "pagetitle":
                return conteudo.get("pageTitle") or conteudo.get("jcr:title") or nome
            return conteudo.get("jcr:title") or nome

        filhos = []
        for k, v in d.items():
            if not isinstance(v, dict) or v.get("jcr:primaryType") != "cq:Page":
                continue
            conteudo = v.get("jcr:content") or {}
            filhos.append((valor(conteudo, k), f"{pai}/{k}"))
        filhos.sort(key=lambda x: (x[0] or "").lower(),
                    reverse=str(bloco.props.get("sortOrder") or "asc").lower() == "desc")
        caminhos = [c for _t, c in filhos]
        maximo = bloco.props.get("maxItems")
        try:
            if maximo and int(str(maximo)) > 0:
                caminhos = caminhos[:int(str(maximo))]
        except ValueError:
            pass
        if bloco.kind == "related":
            # O RelatedSuggestions do GWI tira a PRÓPRIA página DEPOIS de
            # cortar em maxItems, e não repõe: na `udp25g` (maxItems=3, e ela
            # é a 1ª por título desc) o GWI mostra 2 cards — UDP10G e UDP100G
            # — não 3. Excluir antes de cortar traria o TOE25G a mais; não
            # excluir faria a página listar a si mesma (R8).
            caminhos = [c for c in caminhos if c != origem_pagina]
        return caminhos

    # `search`: a policy do list tem disableSearch='true', então não há como
    # manter a consulta viva no destino. As tags `macnica-atd-europe:` não
    # aparecem em cq:tags de nenhuma página, logo a resolução vive fora do
    # JCR: renderizar a página do GWI e ler os links dos cards.
    return []


def aplicar_titulos_download(page, session, base_url, auth, cache):
    for b in page.blocks:
        if b.kind == "download" and not b.props.get("titulo"):
            b.props["titulo"] = titulo_do_asset(
                session, base_url, auth, b.props.get("fileReference", ""), cache)
        elif b.kind == "downloadlist":
            for it in b.props.get("itens") or []:
                if not it.get("titulo"):
                    it["titulo"] = titulo_do_asset(
                        session, base_url, auth, it.get("fileReference", ""), cache)


def dims_do_asset(session, base_url, auth, ref, cache):
    """(largura, altura) em px do asset no DAM, ou None."""
    chave = ("dims", ref)
    if chave in cache:
        return cache[chave]
    dims = None
    d, st = get_json(session, f"{base_url}{ref}/jcr:content/metadata.json", auth)
    if st == 200 and isinstance(d, dict):
        try:
            w, h = int(d.get("tiff:ImageWidth") or 0), int(d.get("tiff:ImageLength") or 0)
            if w > 0 and h > 0:
                dims = (w, h)
        except (TypeError, ValueError):
            pass
    cache[chave] = dims
    return dims


def aplicar_dimensoes_de_imagem(page, session, base_url, auth, cache):
    """Largura x altura de cada imagem que pode virar `textwithimage` (R36).

    O motor calcula o `imageRatio` a partir do tamanho que o GWI DESENHA, e
    para isso precisa da proporção do asset. Roda ANTES de `copiar_assets`
    (o `fileReference` ainda é o do GWI). Os `textwithimage` de linha 6/6 só
    nascem na emissão (`_tentar_textwithimage`), por isso as dimensões vão
    nos blocos de imagem e nos slides de carousel, não só no que já é twi.
    """
    def todos(blocos):
        for b in blocos:
            yield b
            for p in b.panels:
                for r in p.rows:
                    yield from todos(r.blocks)

    for b in todos(page.blocks):
        # Com `largura_px` autoral o asset não era consultado — bastava a
        # largura. A R46 passou a CAPAR essa largura pelo que o GWI desenha
        # (min(480, W, 277*W/H)), e para isso precisa da proporção real: sem
        # ela o teto cai no palpite 3:2 (416px) e o logo CVflow de 510x287
        # saía 416 em vez dos 480 do GWI. Origem imagetext consulta sempre.
        precisa_dims = (not b.props.get("largura_px")
                        or b.props.get("origem_midia") == "imagetext")
        if b.kind in ("image", "textwithimage") and precisa_dims:
            ref = b.props.get("fileReference")
            if isinstance(ref, str) and ref.startswith("/content/dam/"):
                b.props["dims"] = dims_do_asset(session, base_url, auth, ref, cache)
        elif b.kind == "carousel":
            for sl in b.props.get("slides") or []:
                ref = sl.get("fileReference")
                if isinstance(ref, str) and ref.startswith("/content/dam/"):
                    sl["dims"] = dims_do_asset(session, base_url, auth, ref, cache)


def copiar_assets(page, session, base_url, auth, cache, dry_run, copiador=None):
    """Todo fileReference do GWI vira o equivalente em copia-teste.

    `copiador(ref) -> caminho novo | None`: quem grava em outro DAM (o do
    global2, `--alvo-global2`) passa o seu; a trava e o desenho de pastas são dele.
    """
    src, dst = CONFIG["dam_source_prefix"], CONFIG["dam_target_prefix"]
    falhas = []

    def tratar(props, chave):
        ref = props.get(chave)
        if not isinstance(ref, str) or not ref.startswith(src):
            return
        if copiador is not None:
            novo = copiador(ref)
        else:
            novo = copy_asset(session, base_url, ref, src, dst, auth,
                              cache=cache, dry_run=dry_run)
        if novo:
            props[chave] = novo
        else:
            falhas.append(ref)

    for b in page.blocks:
        tratar(b.props, "fileReference")
        for s in b.props.get("slides") or []:
            tratar(s, "fileReference")
        for it in b.props.get("itens") or []:
            tratar(it, "fileReference")
        for p in b.panels:
            for r in p.rows:
                for bb in r.blocks:
                    tratar(bb.props, "fileReference")
    for chave, val in (page.page_props or {}).items():
        if isinstance(val, dict):
            tratar(val, "fileReference")
    return falhas


def main():
    global GWI_ROOT, DEST_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=GWI_ROOT)
    ap.add_argument("--destino", default=DEST_ROOT)
    ap.add_argument("--so", default=None,
                    help="só o que estiver sob este caminho relativo (ex: /altera)")
    ap.add_argument("--paginas", nargs="+", default=None, metavar="REL",
                    help="só ESTAS páginas (caminho relativo exato, ex: /altera "
                         "/canon/canon-li7050). É o que o dry-run de "
                         "cmp_motor.py lista como 'muda': grava o que muda, sem "
                         "regravar a subárvore inteira. '/' é a landing.")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--inicio", type=int, default=0)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--link-de", default=CONFIG["gwi_prefix"])
    ap.add_argument("--link-para", default=CONFIG["global2_prefix"])
    ap.add_argument("--output", default="remigracao.csv")
    ap.add_argument("--pendencias", default="remigracao_pendencias.csv")
    ap.add_argument("--sem-tags", action="store_true")
    ap.add_argument("--links-de-lista", choices=("destino", "global2"),
                    default="destino",
                    help="para onde os itens de `list` apontam. O componente "
                         "List do AEM resolve a página em tempo de render: "
                         "apontando para o global2 (que ainda não tem estas "
                         "páginas) a lista sai VAZIA na tela. 'destino' faz a "
                         "lista renderizar já na árvore de rascunho; trocar "
                         "para global2 é passada de go-live.")
    ap.add_argument("--alvo-global2", action="store_true",
                    help="grava DIRETO no macnicaglobal2 (autorizado pelo Hazael em "
                         "21/09/2026 para /technology e /services). Travas em "
                         "remigracao/ferramentas/golive/direto.py: lista branca de "
                         "caminhos exatos, situação relida ao vivo, backup, manifesto, "
                         "e NUNCA um POST contra URL do GWI.")
    ap.add_argument("--gemeos-conhecidos", nargs="*", default=[], metavar="CAMINHO",
                    help="cascas do global2 com o nome do GWI em MAIÚSCULA que ficam AO "
                         "LADO da página de nome normalizado (não são tocadas)")
    ap.add_argument("--template-por-origem", action="store_true",
                    help="base-page-content -> mai-page-content + components/page")
    ap.add_argument("--so-publicadas", action="store_true",
                    help="pula página que não está ativada no GWI (teste, rascunho)")
    args = ap.parse_args()

    # `destino_de`, `em_escopo` e `normalizar_links_do_escopo` leem as raízes do
    # MÓDULO: sem isto `--origem/--destino` mudavam o crawl e mais nada, e uma
    # página de outra família (macnica-products/macnica-cv75) sairia com o
    # destino calculado contra `/semiconductors`.
    GWI_ROOT, DEST_ROOT = args.origem.rstrip("/"), args.destino.rstrip("/")

    print_header("remigração semiconductors (dialeto Anion)")
    print(f"  origem  : {args.origem}")
    print(f"  destino : {args.destino}")
    print(f"  modo    : {'EXECUTAR (escreve)' if args.executar else 'diagnóstico'}")

    session, auth = build_session(verbose=False)
    todas = crawl_tree(session, args.base_url, args.origem, auth,
                       only_pages=True, quiet=True)
    paginas = [p for p in todas if em_escopo(p)]
    if args.so:
        alvo = args.origem.rstrip("/") + "/" + args.so.strip("/")
        paginas = [p for p in paginas if p == alvo or p.startswith(alvo + "/")]
    if args.paginas:
        alvos = {args.origem.rstrip("/") + ("/" + r.strip("/") if r.strip("/") else "")
                 for r in args.paginas}
        fora = alvos - set(paginas)
        if fora:
            sys.exit(f"[erro] --paginas fora do escopo ou inexistentes: {sorted(fora)}")
        paginas = [p for p in paginas if p in alvos]
    paginas = paginas[args.inicio:]
    if args.limite:
        paginas = paginas[:args.limite]
    if args.so_publicadas:
        vivas = []
        for p in paginas:
            c0, _st = get_json(session, f"{args.base_url}{p}/jcr:content.0.json", auth)
            if isinstance(c0, dict) and c0.get("cq:lastReplicationAction") == "Activate":
                vivas.append(p)
            else:
                print(f"  [pulada] não publicada no GWI: {p[len(GWI_ROOT):]}")
        paginas = vivas
    print(f"  páginas : {len(paginas)} (de {len(todas)} no GWI; "
          f"{len(todas) - len([p for p in todas if em_escopo(p)])} fora de escopo)\n")

    alvo_g2 = None
    if args.alvo_global2:
        sys.path.insert(0, str(Path(__file__).resolve().parent / "remigracao" / "ferramentas" / "golive"))
        import direto as DIR
        if not DEST_ROOT.startswith(DIR.MAI + "/") or not GWI_ROOT.startswith(DIR.GWI_MAI + "/"):
            sys.exit(f"[erro] --alvo-global2 exige origem sob {DIR.GWI_MAI} e destino sob {DIR.MAI}")
        secao_g2 = DEST_ROOT[len(DIR.MAI):].strip("/").split("/")[0]
        alvo_g2 = DIR.Alvo(session, secao_g2, [destino_de(p) for p in paginas],
                           gemeos_conhecidos=args.gemeos_conhecidos)
        # os XFs de contato e os popups do form já existem no global2 (go-live, 21/09/2026)
        AL.XF_MAP = {k: DIR.XF_G2 + k[len(DIR.XF_GWI):] for k in AL.XF_MAP}
        # `master1` é a variação de 3 botões do MESMO XF (Contact Us, Request a Quote, Request
        # Evaluation Kit), usada só na `st-2110-at-scale-resources`. O global2 só tem a `master`
        # (2 botões) e o alvo do 3º botão nem existe lá: melhor o bloco de contato com 2 botões
        # do que a página sem bloco nenhum. Criar a variação no global2 é decisão do Hazael.
        AL.XF_MAP[DIR.XF_GWI + "/products-contact-block/master1"] = DIR.XF_G2 + "/products-contact-block/master"
        AL.XF_FORM_POPUPS = DIR.XF_G2 + "/popups"
        args.links_de_lista = "global2"
        print(f"  ALVO    : macnicaglobal2 DIRETO — {len(alvo_g2.paginas)} caminhos na lista branca; "
              f"DAM em {alvo_g2.dam}\n")

    taxonomia = None if args.sem_tags else load_tag_taxonomy(
        session, args.base_url, auth)
    cache_asset, cache_dc = set(), {}   # set: ensure_dam_folder faz cache.add()
    linhas, pend_rows = [], []

    for i, origem in enumerate(paginas, 1):
        if session_expired(auth):
            print("\n[erro] sessão expirada — renove o cookie e recomece com "
                  f"--inicio {args.inicio + i - 1}", file=sys.stderr)
            break

        jcr, st = get_json(session, f"{args.base_url}{origem}/jcr:content.50.json",
                           auth)
        if st != 200 or not isinstance(jcr, dict):
            linhas.append({"origem": origem, "destino": "", "status": f"erro {st}",
                           "topologia": "", "secoes": "", "blocos": "",
                           "pendencias": "", "detalhe": "sem jcr:content"})
            continue

        logos_de_card = materializar_supplierlists(session, args.base_url, auth, jcr, cache_dc)
        page = AL.extract_tree(jcr, origem)

        if alvo_g2 is not None:
            # Duas variações do MESMO XF na origem (`master` e `master1`) caem na única que o
            # global2 tem: o bloco de contato saía DUAS vezes na `st-2110-at-scale-resources`
            # — o Hazael apagou a cópia à mão no editor (21/09/2026, 23:28 GMT). A 2ª ocorrência
            # do mesmo alvo na página não é emitida.
            vistos_xf = set()
            for sec in page.sections:
                for row in sec.rows:
                    for col in row.columns:
                        fica = []
                        for blk in col.blocks:
                            alvo_xf = blk.props.get("fragmentVariationPath") if blk.kind == "xf" else None
                            if alvo_xf and alvo_xf in vistos_xf:
                                continue
                            if alvo_xf:
                                vistos_xf.add(alvo_xf)
                            fica.append(blk)
                        col.blocks = fica

        # depende de rede: rótulo de download e related children/search
        aplicar_titulos_download(page, session, args.base_url, auth, cache_dc)
        aplicar_dimensoes_de_imagem(page, session, args.base_url, auth, cache_dc)
        for b in page.blocks:
            if b.kind in ("related", "productlist"):
                resolvidas = resolver_related(session, args.base_url, auth, b, origem)
                if not resolvidas:
                    continue
                if args.links_de_lista == "destino":
                    # `list` resolve a página no RENDER: se apontar para uma
                    # que não existe, o componente não desenha item nenhum.
                    # Os dois cards "Ambarella CV72S SoC"/"Ambarella N1 SoC"
                    # sumiam por isso — o alvo no global2 ainda não existe.
                    resolvidas = [destino_de(x) if x.startswith(GWI_ROOT) else x
                                  for x in resolvidas]
                b.props["pages"] = resolvidas
                b.props["listFrom"] = "static"

        copiador = None
        if alvo_g2 is not None:
            fam = DIR.familia_de(destino_de(origem), alvo_g2.secao)
            # logo de card de fornecedor: versão de TAMANHO ÚNICO (ver direto.logo_uniforme, R62)
            copiador = lambda ref, _f=fam, _l=logos_de_card: (
                alvo_g2.logo_uniforme(ref, _f, args.executar) if ref in _l
                else alvo_g2.copiar_asset(ref, _f, args.executar))
        falhas = copiar_assets(page, session, args.base_url, auth, cache_asset,
                               dry_run=not args.executar, copiador=copiador)
        for ref in falhas:
            page.pendencias.append(AL.Pendencia(
                origem, "asset", "asset_nao_copiado", "copy_asset falhou", ref))

        # Cabeçalho: `title` vazio em TODA página cujo template do GWI desenha
        # o pageTitle (o AEM renderiza o pageTitle como h1, reproduzindo o
        # cabeçalho que o GWI põe ANTES do corpo — mesmo quando o corpo tem h1
        # próprio; ver R6 em REGRAS-disposicao.md).
        #
        # Tem de ser uma SEÇÃO PRÓPRIA, de largura cheia. Injetar dentro da
        # primeira coluna existente punha o título DENTRO de uma coluna de 6:
        # na `/ambarella` o resultado foi título+vídeo empilhados à esquerda e
        # o texto sozinho à direita, quando o GWI tem o título em cima de tudo
        # e vídeo|texto lado a lado embaixo.
        #
        # Largura cheia e antes de tudo — mas como `cabecalho` da 1ª linha, não
        # como seção própria (R28): ver `AL.inserir_titulo_da_pagina`.
        AL.inserir_titulo_da_pagina(page, origem)

        tpl_pagina, rt_pagina = template_de(jcr, args.template_por_origem)
        payload, contagens = AL.build_layout_payload(
            page, template_path=tpl_pagina,
            link_de=args.link_de, link_para=args.link_para,
            reescrever_listas=(args.links_de_lista != "destino"))

        normalizar_links_do_escopo(payload, args.link_de, args.link_para)

        destino = destino_de(origem)
        seo = build_seo_props(jcr)
        pagina_payload = build_page_payload(
            title=jcr.get("jcr:title") or destino.rsplit("/", 1)[-1],
            template_path=tpl_pagina,
            description=jcr.get("jcr:description"),
            hide_in_nav=str(jcr.get("hideInNav", "")).lower() == "true",
            seo_props=seo)
        # maeproductpage, não page — sem isso o diálogo pd_* nem aparece
        pagina_payload["jcr:content/sling:resourceType"] = rt_pagina
        if "jcr:content/hideInNav" not in pagina_payload:
            # Página que JÁ existia, feita por outro script: o POST faz MERGE e
            # o `hideInNav=true` antigo sobrevivia (macnica-cv75). O GWI não tem
            # a propriedade, nem as páginas da Anion no global2.
            pagina_payload["jcr:content/hideInNav@Delete"] = ""

        # build_tag_props devolve (props, pendencias) e as chaves vêm SEM o
        # prefixo jcr:content/ — o chamador é que prefixa.
        tag_props = {}
        if not args.sem_tags and taxonomia:
            regiao = detect_tag_region(origem)
            tag_props, tag_pend = build_tag_props(
                jcr.get("sling:resourceType", ""), jcr, regiao, taxonomia)
            for tp in tag_pend:
                page.pendencias.append(AL.Pendencia(
                    origem, tp.get("resourceType", "tag"), "tag",
                    tp.get("motivo", ""), tp.get("path", "")))
            for prop, valor in tag_props.items():
                pagina_payload[f"jcr:content/{prop}"] = valor
                if isinstance(valor, list):
                    pagina_payload[f"jcr:content/{prop}@TypeHint"] = "String[]"

        if tag_props and rt_pagina == PAGE_RT:        # pd_* só existe no diálogo do maeproductpage
            fabricante = tag_props.get("manufacturer", "")
            slug = fabricante.rsplit("/", 1)[-1] if fabricante else None
            pd_props = build_pd_props(jcr, destino.rsplit("/", 1)[-1], slug)
            # `pd_modelName` do navTitle do GWI, não do slug em maiúsculas:
            # acerta 189/209 contra 181/209 da regra antiga, que produz lixo
            # do tipo '6-ALTERA-SOC-EMBEDDED-DESIGN-SUITE'.
            nav = (jcr.get("navTitle") or "").strip()
            if nav:
                pd_props["pd_modelName"] = nav
            # multivalorado -> primeiro valor (125/128 de acerto)
            for k in ("pd_resolution", "pd_pixelSize", "pd_interface",
                      "pd_productFamilyText"):
                v = pd_props.get(k)
                if isinstance(v, list):
                    pd_props[k] = v[0] if v else ""
            for prop, valor in pd_props.items():
                pagina_payload[f"jcr:content/{prop}"] = valor

        for chave, val in (page.page_props or {}).items():
            if not isinstance(val, dict):
                continue
            base = f"jcr:content/{chave}"
            pagina_payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
            pagina_payload[f"{base}/sling:resourceType"] = \
                "core/wcm/components/image/v3/image"
            for k2, v2 in val.items():
                pagina_payload[f"{base}/{k2}"] = v2

        proibidas = []
        if alvo_g2 is not None:
            for ref in DIR.assets_do_html(payload, alvo_g2, fam, args.executar):
                page.pendencias.append(AL.Pendencia(
                    origem, "asset", "asset_nao_copiado", "asset de HTML cru não copiado", ref))
            DIR.acertar_links(payload, ("solutions", "services"))
            DIR.acertar_links(pagina_payload, ("solutions", "services"))
            trocas, mortos = DIR.resolver_alvos(payload, alvo_g2, a_nascer=alvo_g2.paginas)
            for de, para in trocas:
                print(f"        link: {de[len(DIR.MAI):]} -> {para[len(DIR.MAI):]}")
            for morto in mortos:
                page.pendencias.append(AL.Pendencia(
                    origem, "link", "alvo_inexistente_no_global2",
                    "a página-alvo ainda não existe no global2", morto))
            proibidas = DIR.sobras_proibidas(payload) + DIR.sobras_proibidas(pagina_payload)
            for chave, trecho in proibidas:
                page.pendencias.append(AL.Pendencia(
                    origem, "ref", "ref_proibida_no_global2", trecho[:150], chave))

        n_pend = len(page.pendencias)
        for p in page.pendencias:
            r = p.as_row()
            r["pagina"] = origem
            pend_rows.append(r)

        linhas.append({
            "origem": origem, "destino": destino,
            "status": "simulado" if not args.executar else "",
            "topologia": page.topology,
            "secoes": len(page.sections),
            "blocos": sum(contagens.values()),
            "pendencias": n_pend,
            "detalhe": " ".join(f"{k}={v}" for k, v in sorted(contagens.items())),
        })

        marca = "·" if n_pend == 0 else "!"
        print(f"  [{i:3}/{len(paginas)}] {marca} {page.topology:8} "
              f"sec={len(page.sections):2} blocos={sum(contagens.values()):3} "
              f"pend={n_pend:2}  {destino[len(DEST_ROOT):][:52]}")

        if alvo_g2 is not None:
            sit = alvo_g2.situacao(destino)               # lido AO VIVO; aborta se for de outra pessoa
            linhas[-1]["detalhe"] = f"[{sit}] " + linhas[-1]["detalhe"]
            muda = ""
            if sit == "nossa":
                d3 = DIR.diferenca_com_o_servidor(alvo_g2, destino, payload)
                muda = "  = servidor" if d3 == (0, 0, 0) else f"  MUDA +{d3[0]} -{d3[1]} ~{d3[2]}"
                linhas[-1]["detalhe"] = muda.strip() + " " + linhas[-1]["detalhe"]
            print(f"        global2: {sit:6} {destino[len(DIR.MAI):]}{muda}")
            if proibidas:
                linhas[-1]["status"] = "NAO GRAVADA: ref proibida"
                print(f"        [não gravo] {len(proibidas)} referência(s) a GWI/copia-teste no payload")
                continue
            if not args.executar:
                continue
            sit, res = alvo_g2.gravar_pagina(destino, pagina_payload, payload)
            linhas[-1]["status"] = res
            if res != "ok":
                print(f"        [falha] {res}")
            time.sleep(CONFIG["write_delay"])
            continue

        if not args.executar:
            continue

        # O Sling POST faz MERGE, não substituição: regravar por cima deixa os
        # nós da passada anterior misturados com os novos (foi assim que
        # nasceram as 136 páginas com conteúdo em dobro). Numa árvore de
        # rascunho, que é reescrita a cada iteração do motor, apagar o `root`
        # antes é obrigatório — e é seguro porque nada aqui é autoral.
        _existe, st0 = get_json(session, f"{args.base_url}{destino}/jcr:content.0.json",
                                auth)
        if st0 == 200:
            delete_node(session, args.base_url, f"{destino}/jcr:content/root", auth)

        st1, txt1 = post_node(session, args.base_url, destino, pagina_payload, auth)
        if st1 not in (200, 201):
            linhas[-1]["status"] = f"falha página {st1}"
            print(f"        [falha] criar página: {st1} {txt1[:90]}")
            continue
        st2, txt2 = post_node(session, args.base_url, destino, payload, auth)
        linhas[-1]["status"] = "ok" if st2 in (200, 201) else f"falha conteúdo {st2}"
        if st2 not in (200, 201):
            print(f"        [falha] gravar conteúdo: {st2} {txt2[:90]}")
        time.sleep(CONFIG["write_delay"])

    write_csv(args.output,
              ["origem", "destino", "status", "topologia", "secoes", "blocos",
               "pendencias", "detalhe"], linhas)
    write_csv(args.pendencias,
              ["pagina", "origem", "resourceType", "categoria", "motivo", "ref"],
              pend_rows)

    ok = sum(1 for l in linhas if l["status"] in ("ok", "simulado"))
    print(f"\n  páginas processadas : {len(linhas)}  ({ok} sem falha)")
    print(f"  pendências          : {len(pend_rows)}")
    if pend_rows:
        from collections import Counter
        for k, v in Counter(r["categoria"] for r in pend_rows).most_common():
            print(f"      {v:4}  {k}")
    print(f"  CSV                 : {args.output}")
    print(f"  pendências          : {args.pendencias}")
    if not args.executar:
        print("\n  (diagnóstico — nada foi escrito; use --executar)")


if __name__ == "__main__":
    main()
