#!/usr/bin/env python3
"""
Remigra `semiconductors` do GWI para uma árvore NOVA, no dialeto Anion.

DESTINO: `/content/copia-teste/americas/mai/en/products/semiconductors-remigration`

É árvore de rascunho, criada do zero. **Nada em `/semiconductors` é tocado** —
as edições manuais do Bruno no `/canon` (79 nós, incluindo 8 blocos de texto em
português que não existem no GWI e uma anotação viva) continuam onde estão.
Também não se escreve em `macnicagwi` nem em `macnicaglobal2`.

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


def copiar_assets(page, session, base_url, auth, cache, dry_run):
    """Todo fileReference do GWI vira o equivalente em copia-teste."""
    src, dst = CONFIG["dam_source_prefix"], CONFIG["dam_target_prefix"]
    falhas = []

    def tratar(props, chave):
        ref = props.get(chave)
        if not isinstance(ref, str) or not ref.startswith(src):
            return
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
    args = ap.parse_args()

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
    print(f"  páginas : {len(paginas)} (de {len(todas)} no GWI; "
          f"{len(todas) - len([p for p in todas if em_escopo(p)])} fora de escopo)\n")

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

        page = AL.extract_tree(jcr, origem)

        # depende de rede: rótulo de download e related children/search
        aplicar_titulos_download(page, session, args.base_url, auth, cache_dc)
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

        falhas = copiar_assets(page, session, args.base_url, auth, cache_asset,
                               dry_run=not args.executar)
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
        if AL.precisa_title_vazio(page):
            cab = AL.Section(origem, -1, role="header")
            cab.pad_tb = "small"
            linha = AL.Row("single")
            col = AL.Column(origem, width=12)
            col.blocks = [AL.Block("title_vazio", origem)]
            linha.columns = [col]
            cab.rows = [linha]
            page.sections.insert(0, cab)

        payload, contagens = AL.build_layout_payload(
            page, template_path=TEMPLATE,
            link_de=args.link_de, link_para=args.link_para,
            reescrever_listas=(args.links_de_lista != "destino"))

        normalizar_links_do_escopo(payload, args.link_de, args.link_para)

        destino = destino_de(origem)
        seo = build_seo_props(jcr)
        pagina_payload = build_page_payload(
            title=jcr.get("jcr:title") or destino.rsplit("/", 1)[-1],
            template_path=TEMPLATE,
            description=jcr.get("jcr:description"),
            hide_in_nav=str(jcr.get("hideInNav", "")).lower() == "true",
            seo_props=seo)
        # maeproductpage, não page — sem isso o diálogo pd_* nem aparece
        pagina_payload["jcr:content/sling:resourceType"] = PAGE_RT

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

        if tag_props:
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
