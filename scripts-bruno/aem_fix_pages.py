#!/usr/bin/env python3
"""
Corrige páginas JÁ MIGRADAS em copia-teste, aplicando tudo que os
scripts antigos não faziam — sem recriar a página nem tocar no conteúdo
que já está certo.

O QUE CORRIGE (cada item é conferido antes; se já estiver certo, não
reescreve):

  1. ESTRUTURA  — remove o container-pai intermediário, promovendo os
                  blocos para root/container/<bloco>_wrap (2 níveis).
  2. PADDING    — L/R Large em todos os containers de bloco;
                  T/B Small só no primeiro (o do título).
  3. TÍTULO ROXO— remove o style de Font Color do componente title.
                  Confirmado com o Bruno em 13/09/2026: o roxo é a cor
                  PADRÃO do CSS; as classes 'black'/'white' é que
                  sobrescrevem. Título roxo = slot de cor VAZIO.
  4. SEO        — copia pageTitle/navTitle/keywords do GWI de origem.
  5. TAGS       — Product Hierarchy Details (manufacturer,
                  businessCategories, interface, resolution...) +
                  campos pd_*, lidos do GWI e validados contra a
                  taxonomia real.
  6. hideInNav  — marca 'Hide in Navigation' (diretriz do cliente).
  7. LAYOUT     — apaga o nó cq:responsive de qualquer componente que
                  tenha ficado com largura reduzida (grid arrastado
                  manualmente no editor: width<12 e/ou offset>0).
                  Confirmado com o Bruno em 15/09/2026: os componentes
                  criados pelos nossos scripts nunca têm cq:responsive
                  (o container do MACNICA GLOBAL2 tem layoutDisabled na
                  policy), então "sem o nó" É o estado de largura
                  máxima — não se grava width=12 explícito, remove-se
                  o nó inteiro.

NÃO MEXE em: cor de fundo alternada dos containers (o Bruno pediu para
deixar para uma segunda rodada) e no conteúdo dos blocos em si.

CONFERE TAMBÉM: páginas sem conteúdo nenhum, que os scripts antigos
criaram vazias. Elas são reportadas no CSV com status
'SEM CONTEÚDO (remigrar)' — este script NÃO tenta preencher conteúdo,
isso é trabalho do aem_migrate.py.

A origem no GWI é derivada do caminho de destino. Como o GWI tem nomes
de nó com maiúsculas (ex: 'MBLS1028A-IND-...') e o destino está
normalizado, a busca tenta o nome normalizado e, se falhar, procura o
irmão que normaliza para o mesmo slug.

SEGURANÇA: só escreve dentro de copia-teste (assert_target_is_safe em
post_node). macnicagwi e macnicaglobal2 são SOMENTE LEITURA.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_pages.py --target /content/copia-teste/.../tq-systems --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_pages.py --target /content/copia-teste/.../tq-systems
"""

import argparse
import sys

from aem_lib import (
    CONFIG, STYLE_PADDING_LEFT_RIGHT_LARGE, STYLE_PADDING_TOP_BOTTOM_SMALL,
    add_common_args, build_pd_props, build_seo_props, build_session,
    build_tag_props, crawl_tree, delete_node, detect_tag_region,
    fetch_with_depth_fallback, flatten_node, list_child_nodes,
    load_tag_taxonomy, post_node, print_header, session_expired,
    strip_empty_blocks, write_csv,
)

TITLE_RT = "macnicaglobal2/components/content/title"
CONTAINER_RT = "macnicaglobal2/components/content/container"

# Styles de Font Color do componente title (policy real
# .../policies/macnicaglobal2/components/content/title). São os ÚNICOS
# dois que existem — não há roxo. O roxo é a cor padrão do CSS, então
# "título roxo" = nenhum destes aplicado.
TITLE_FONT_COLOR_STYLE_IDS = {
    "1717668061877",  # Black
    "1717668062802",  # White
}

RICH_TEXT_PROPS = ("text",)


def achar_origem_gwi(session, base_url, dest_path, target_root, gwi_root, auth_tracker,
                     cache_irmaos):
    """Descobre o caminho no GWI que originou uma página de copia-teste.

    Tenta o caminho direto (nomes já normalizados batem na maioria dos
    casos). Se der 404, procura entre os irmãos do nó pai no GWI aquele
    cujo nome normaliza para o mesmo slug — o GWI tem nomes com
    maiúsculas (ex: 'MBLS1028A-IND-single-board-computer') que o
    normalize_name() transformou no destino.
    """
    from aem_lib import normalize_name

    rel = dest_path[len(target_root):].lstrip("/")
    candidato = f"{gwi_root}/{rel}" if rel else gwi_root

    data, status = fetch_with_depth_fallback(session, base_url, candidato, 1, auth_tracker)
    if data is not None:
        return candidato, data

    # Fallback: procurar o irmão com nome equivalente depois de normalizar.
    if not rel:
        return None, None
    pai_rel, _, nome_dest = rel.rpartition("/")
    pai_gwi = f"{gwi_root}/{pai_rel}" if pai_rel else gwi_root

    if pai_gwi not in cache_irmaos:
        pai_data, _ = fetch_with_depth_fallback(session, base_url, pai_gwi, 1, auth_tracker)
        cache_irmaos[pai_gwi] = [n for n, _ in list_child_nodes(pai_data)] if pai_data else []

    for irmao in cache_irmaos[pai_gwi]:
        if normalize_name(irmao) == nome_dest:
            achado = f"{pai_gwi}/{irmao}"
            data, _ = fetch_with_depth_fallback(session, base_url, achado, 1, auth_tracker)
            if data is not None:
                return achado, data
    return None, None


def detectar_container_pai(container_node):
    """Detecta o container-pai antigo (estrutura de 3 níveis).

    Retorna (nome, node) ou (None, None) se a página já está em 2 níveis
    ou está vazia. Não assume o nome 'containerpy': as páginas migradas
    por scripts antigos usam nomes gerados ('container_386242080_',
    'container_copy'...).
    """
    filhos = list_child_nodes(container_node)
    if len(filhos) != 1:
        return None, None
    nome, node = filhos[0]
    netos = list_child_nodes(node)
    # Um único bloco já promovido: container/algo_wrap/algo
    if nome.endswith("_wrap") and len(netos) == 1:
        return None, None
    return nome, node


def tem_conteudo_real(node, profundidade=0):
    """True se houver algum componente que não seja container puro."""
    if profundidade > 8:
        return False
    for _, filho in list_child_nodes(node):
        rt = filho.get("sling:resourceType", "")
        if rt and not rt.endswith("/container"):
            return True
        if tem_conteudo_real(filho, profundidade + 1):
            return True
    return False


def limpar_style_cor_titulo(payload, base):
    """Tira o style de Font Color de todo componente title sob 'base'.

    O AEM guarda cq:styleIds como array posicional, um slot por grupo de
    style. Zerar o slot da cor (em vez de remover o item) preserva a
    posição dos outros grupos — Font Size, Design, Display Position.
    """
    alterados = 0
    for chave, valor in list(payload.items()):
        if not chave.startswith(f"{base}/") or not chave.endswith("/cq:styleIds"):
            continue
        no_do_style = chave.rsplit("/", 1)[0]
        # só mexe se for o styleIds de um componente title
        if payload.get(f"{no_do_style}/sling:resourceType") != TITLE_RT:
            continue
        if isinstance(valor, list):
            novo = ["" if v in TITLE_FONT_COLOR_STYLE_IDS else v for v in valor]
        else:
            novo = "" if valor in TITLE_FONT_COLOR_STYLE_IDS else valor
        if novo != valor:
            payload[chave] = novo
            alterados += 1
    return alterados


def limpar_textos(payload, base):
    """Aplica strip_empty_blocks nas propriedades de texto rico."""
    alterados = 0
    for chave, valor in list(payload.items()):
        if not chave.startswith(f"{base}/") or not isinstance(valor, str):
            continue
        if chave.rsplit("/", 1)[-1] not in RICH_TEXT_PROPS:
            continue
        limpo = strip_empty_blocks(valor)
        if limpo != valor:
            payload[chave] = limpo
            alterados += 1
    return alterados


def _layout_e_estreito(node):
    """True se node/cq:responsive/default tiver width!=12 ou offset!=0."""
    resp = node.get("cq:responsive")
    if not isinstance(resp, dict):
        return False
    default = resp.get("default")
    if not isinstance(default, dict):
        return False
    largura = str(default.get("width", "12"))
    deslocamento = str(default.get("offset", "0"))
    return largura != "12" or deslocamento != "0"


def detectar_layout_estreito(node, base, profundidade=0):
    """Acha todo nó cq:responsive com largura reduzida em 'node' e sob ele.

    "Reduzido" = tem sub-nó 'default' com width != '12' ou offset != '0'
    (aceita ausência de valor como não-reduzido, já que só queremos os
    que foram de fato arrastados no editor). Checa o PRÓPRIO 'node'
    além dos filhos — bug encontrado em produção: um bloco de topo
    inteiro (ex: 'content_area') pode estar com width=8/offset=2 sem
    que nenhum filho seu tenha nada, e olhar só os filhos deixa passar.
    Retorna caminhos relativos (a partir de 'base') do nó cq:responsive,
    prontos para virar delete_node — não dá para "zerar" width=12
    porque um grid ativo com width=12 ainda é grid ativo; o padrão dos
    nossos componentes é NUNCA ter cq:responsive (policy com
    layoutDisabled).
    """
    achados = []
    if _layout_e_estreito(node):
        achados.append(f"{base}/cq:responsive")
    for nome, filho in list_child_nodes(node):
        if profundidade > 10:
            continue
        achados.extend(detectar_layout_estreito(filho, f"{base}/{nome}", profundidade + 1))
    return achados


def ler_bloco_isolado(session, base_url, caminho_completo, auth_tracker):
    """Relê um bloco com .infinity.json, para não perder cq:responsive.

    fetch_with_depth_fallback usa profundidade numérica, e o servidor
    recusa (HTTP 300) profundidades altas em páginas com muitos nós,
    recuando para a maior aceita — que pode ser rasa demais para expor
    um cq:responsive de componente (2 níveis abaixo do próprio nó:
    componente/cq:responsive/default/width). .infinity.json num bloco
    isolado (não na página inteira) não tem esse limite, na prática.
    Retorna None em qualquer erro — quem chama usa o nó já lido, sem
    quebrar o fluxo.
    """
    from urllib.parse import urljoin
    url = urljoin(base_url, f"{caminho_completo}.infinity.json")
    try:
        resp = session.get(url, timeout=CONFIG["timeout"])
    except Exception:
        return None
    if resp.status_code == 200:
        if auth_tracker is not None:
            auth_tracker["fails"] = 0
        try:
            return resp.json()
        except ValueError:
            return None
    if resp.status_code in (401, 403) and auth_tracker is not None:
        auth_tracker["fails"] += 1
    return None


def build_payload_estrutura(blocos_node, session=None, base_url=None,
                            page_path=None, auth_tracker=None, nome_pai=None):
    """Reescreve os blocos direto no slot, com padding e título roxo.

    NÃO aplica backgroundColor — a cor alternada ficou para a segunda
    rodada, por decisão do Bruno em 13/09/2026.

    session/base_url/page_path/auth_tracker (opcionais): se vierem,
    cada bloco é relido com .infinity.json isolado antes de checar
    layout estreito. Necessário porque fetch_with_depth_fallback, em
    páginas com muitos blocos, recebe HTTP 300 do servidor e recua
    para uma profundidade que corta o cq:responsive de componentes
    (ele fica 2 níveis abaixo do componente: title/cq:responsive/
    default/width). Bug real encontrado em 15/09/2026 na
    i-chips-scaler-lsi: a árvore principal não mostrava cq:responsive
    nenhum, mas o HTML publicado renderizava componentes em width=8 —
    só apareceu ao reler o bloco isoladamente com .infinity.json.
    """
    payload = {
        "jcr:content/root/container/jcr:primaryType": "nt:unstructured",
        "jcr:content/root/container/sling:resourceType": CONTAINER_RT,
    }
    nomes, textos_limpos, titulos_roxos = [], 0, 0
    layouts_estreitos = []
    pode_reler = session is not None and base_url is not None and page_path is not None

    for i, (nome_wrap, node_wrap) in enumerate(list_child_nodes(blocos_node)):
        nomes.append(nome_wrap)
        base = f"jcr:content/root/container/{nome_wrap}"
        flatten_node(node_wrap, base, payload)

        # Padding é style de CONTAINER. Se o bloco de primeiro nível não
        # for um container (acontece: há páginas cujo filho direto do
        # slot é o próprio 'title'), gravar o padding ali destruiria os
        # styles daquele componente — o title perderia o Font Size.
        eh_container = node_wrap.get("sling:resourceType") == CONTAINER_RT
        if eh_container:
            estilos = [STYLE_PADDING_LEFT_RIGHT_LARGE]
            if i == 0:
                estilos.append(STYLE_PADDING_TOP_BOTTOM_SMALL)
            payload[f"{base}/cq:styleIds"] = estilos
            payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"

        # Depois do padding: limpar_style_cor_titulo só mexe em nós cujo
        # resourceType é title, então não desfaz o padding acima.
        textos_limpos += limpar_textos(payload, base)
        titulos_roxos += limpar_style_cor_titulo(payload, base)

        # Layout estreito: acha os cq:responsive com width/offset != full
        # e tira do payload achatado (senão o POST recriaria o mesmo nó
        # estreito) — a remoção de verdade no servidor é um delete_node
        # à parte, feito pelo chamador depois do POST principal.
        no_para_checar = node_wrap
        if pode_reler:
            # Caminho real no servidor: quando há container-pai (estrutura
            # de 3 níveis ainda não promovida), o bloco está um nível mais
            # fundo do que o 'base' usado no payload de destino (que já
            # promove os blocos para fora do pai).
            prefixo_pai = f"/{nome_pai}" if nome_pai else ""
            caminho_real = (f"{page_path}/jcr:content/root/container"
                           f"{prefixo_pai}/{nome_wrap}")
            fresco = ler_bloco_isolado(session, base_url, caminho_real, auth_tracker)
            if fresco is not None:
                no_para_checar = fresco
        for caminho in detectar_layout_estreito(no_para_checar, base):
            layouts_estreitos.append(caminho)
            for chave in [k for k in payload if k == caminho or k.startswith(f"{caminho}/")]:
                del payload[chave]

    return payload, nomes, textos_limpos, titulos_roxos, layouts_estreitos


def main():
    parser = argparse.ArgumentParser(
        description="Corrige páginas já migradas em copia-teste (estrutura, "
                    "padding, título roxo, SEO, tags, hideInNav)")
    parser.add_argument("--target", required=True,
                        help="Raiz a corrigir dentro de copia-teste.")
    parser.add_argument("--gwi-root", default=None,
                        help="Raiz correspondente no GWI. Padrão: deriva do "
                             "--target trocando o prefixo do site.")
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. RODE SEMPRE ANTES.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--sem-tags", action="store_true")
    parser.add_argument("--sem-seo", action="store_true")
    parser.add_argument("--skip", action="append", default=None,
                        metavar="TRECHO",
                        help="Não toca em caminhos que contenham TRECHO. "
                             "Repetível. Padrão: AEM_SKIP_PATH_CONTAINS do .env. "
                             "Use --skip '' para não pular nada.")
    parser.add_argument("--output", default="fix_pages.csv")
    args = parser.parse_args()

    skip = CONFIG["skip_path_contains"] if args.skip is None else args.skip
    skip = tuple(s for s in skip if s)

    target_root = args.target.rstrip("/")
    if not target_root.startswith(CONFIG["target_prefix"]):
        print(f"[erro] --target precisa estar dentro de {CONFIG['target_prefix']}: "
              f"{target_root}", file=sys.stderr)
        sys.exit(1)

    gwi_root = (args.gwi_root.rstrip("/") if args.gwi_root
                else CONFIG["gwi_prefix"] + target_root[len(CONFIG["target_prefix"]):])

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("CORREÇÃO DE PÁGINAS JÁ MIGRADAS")
    print(f"  Destino: {target_root}")
    print(f"  Origem:  {gwi_root}   (somente leitura)")
    print(f"  Corrige: estrutura, padding, título roxo, layout (largura máxima)"
          f"{'' if args.sem_seo else ', SEO'}"
          f"{'' if args.sem_tags else ', tags + pd_*'}, hideInNav")
    print(f"  NÃO mexe: cor de fundo (2ª rodada)")
    if skip:
        print(f"  PULA:    {', '.join(skip)}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    taxonomy = None if args.sem_tags else load_tag_taxonomy(session, base_url, auth_tracker)
    region = detect_tag_region(gwi_root)

    print(f"== Percorrendo {target_root} ==")
    inventory = crawl_tree(session, base_url, target_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay,
                           skip_contains=skip, only_pages=True)
    paginas = sorted(p for p, m in inventory.items() if m["is_page"])

    # Segunda trava: o crawl já poda os ramos pulados, mas filtrar a lista
    # final garante que nada passe caso o --target aponte para dentro de um
    # caminho pulado (aí o crawl não teria o que podar).
    if skip:
        antes = len(paginas)
        paginas = [p for p in paginas if not any(s in p for s in skip)]
        if antes != len(paginas):
            print(f"  {antes - len(paginas)} páginas puladas por --skip")
    print(f"  {len(paginas)} páginas\n")
    if not paginas:
        print(f"[erro] nenhuma página em {target_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    cache_irmaos = {}
    print(f"== Processando {len(paginas)} páginas ==")

    for i, path in enumerate(paginas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i-1}/{len(paginas)} processadas.",
                  file=sys.stderr)
            for resto in paginas[i-1:]:
                resultados.append({"pagina": resto, "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = {"pagina": path, "origem_gwi": "", "blocos": 0, "textos_limpos": 0,
                 "titulos_roxos": 0, "seo": 0, "tags": 0, "pd": 0,
                 "container_pai": "", "layouts_estreitos": 0, "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path,
                                                 args.source_depth, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        container = (jcr.get("root", {}) or {}).get("container", {}) or {}

        nome_pai, node_pai = detectar_container_pai(container)
        blocos_node = node_pai if nome_pai else container
        linha["container_pai"] = nome_pai or ""

        if not tem_conteudo_real(container):
            linha["status"] = "SEM CONTEÚDO (remigrar com aem_migrate.py)"
            resultados.append(linha)
            if i % 10 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        payload, nomes, textos, roxos, layouts_estreitos = build_payload_estrutura(
            blocos_node, session=session, base_url=base_url,
            page_path=path, auth_tracker=auth_tracker, nome_pai=nome_pai)
        linha.update({"blocos": len(nomes), "textos_limpos": textos,
                      "titulos_roxos": roxos,
                      "layouts_estreitos": len(layouts_estreitos)})

        # --- propriedades vindas do GWI ---
        gwi_path, gwi_data = achar_origem_gwi(session, base_url, path, target_root,
                                              gwi_root, auth_tracker, cache_irmaos)
        if gwi_data is not None:
            linha["origem_gwi"] = gwi_path
            gwi_full, _ = fetch_with_depth_fallback(session, base_url, gwi_path,
                                                    args.source_depth, auth_tracker)
            gwi_jcr = (gwi_full or {}).get("jcr:content", {}) or {}

            if not args.sem_seo:
                seo = build_seo_props(gwi_jcr)
                for prop, valor in seo.items():
                    payload[f"jcr:content/{prop}"] = valor
                linha["seo"] = len(seo)

            if not args.sem_tags:
                tag_props, _ = build_tag_props(gwi_jcr.get("sling:resourceType", ""),
                                               gwi_jcr, region, taxonomy)
                for prop, valor in tag_props.items():
                    payload[f"jcr:content/{prop}"] = valor
                linha["tags"] = len(tag_props)

                if tag_props:
                    fabricante = tag_props.get("manufacturer", "")
                    slug = fabricante.rsplit("/", 1)[-1] if fabricante else None
                    pd_props = build_pd_props(gwi_jcr, path.rsplit("/", 1)[-1], slug)
                    descricao = gwi_jcr.get("jcr:description", "")
                    if descricao:
                        pd_props["pd_description"] = descricao
                    for prop, valor in pd_props.items():
                        payload[f"jcr:content/{prop}"] = valor
                    linha["pd"] = len(pd_props)
        else:
            linha["origem_gwi"] = "(não encontrada no GWI)"

        payload["jcr:content/hideInNav"] = "true"

        if args.dry_run:
            linha["status"] = "DRY-RUN"
        else:
            st, resposta = post_node(session, base_url, path, payload, auth_tracker)
            if st not in (200, 201):
                linha["status"] = f"ERRO ao escrever ({st}): {resposta[:120]}"
                resultados.append(linha)
                continue
            linha["status"] = "OK"
            if nome_pai:
                del_st, _ = delete_node(
                    session, base_url,
                    f"{path}/jcr:content/root/container/{nome_pai}", auth_tracker)
                if del_st not in (200, 204):
                    linha["status"] = (f"OK (corrigido), mas ERRO ao apagar "
                                       f"container-pai ({del_st}) — remover {nome_pai}")

            erros_layout = []
            for caminho_relativo in layouts_estreitos:
                del_st, _ = delete_node(session, base_url,
                                        f"{path}/{caminho_relativo}", auth_tracker)
                if del_st not in (200, 204):
                    erros_layout.append(caminho_relativo)
            if erros_layout:
                linha["status"] += (f" | ERRO ao apagar layout estreito em: "
                                    f"{', '.join(erros_layout)}")

        resultados.append(linha)
        if i % 10 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output,
              ["pagina", "origem_gwi", "container_pai", "blocos", "textos_limpos",
               "titulos_roxos", "layouts_estreitos", "seo", "tags", "pd", "status"],
              resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN"))
    sem_conteudo = [r for r in resultados if "SEM CONTEÚDO" in r["status"]]
    erros = [r for r in resultados if "ERRO" in r["status"]]
    sem_origem = [r for r in resultados if r["origem_gwi"] == "(não encontrada no GWI)"]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas:  {len(resultados)}")
    print(f"    corrigidas:         {ok}")
    print(f"    promovidas (3→2):   {sum(1 for r in resultados if r['container_pai'])}")
    print(f"    títulos → roxo:     {sum(r['titulos_roxos'] for r in resultados)}")
    print(f"    layouts corrigidos: {sum(r['layouts_estreitos'] for r in resultados)}")
    print(f"    textos limpos:      {sum(r['textos_limpos'] for r in resultados)}")
    print(f"    com SEO copiado:    {sum(1 for r in resultados if r['seo'])}")
    print(f"    com tags copiadas:  {sum(1 for r in resultados if r['tags'])}")
    print(f"    SEM CONTEÚDO:       {len(sem_conteudo)}")
    print(f"    erros:              {len(erros)}")

    if sem_conteudo:
        print(f"\n  --- {len(sem_conteudo)} página(s) SEM CONTEÚDO ---")
        print(f"      Precisam ser remigradas com aem_migrate.py (este script")
        print(f"      só corrige estrutura/propriedades, não preenche conteúdo).")
        for r in sem_conteudo[:10]:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}")

    if sem_origem:
        print(f"\n  --- {len(sem_origem)} página(s) sem origem no GWI ---")
        for r in sem_origem[:10]:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
