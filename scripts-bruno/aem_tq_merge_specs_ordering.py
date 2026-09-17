#!/usr/bin/env python3
"""
Duas correções finais em tq-systems, confirmadas com o Bruno em
16/09/2026 usando .../tq-embedded-arm-modules/starterkit-stka6ulx
(já editada manualmente por ele) como referência do padrão-alvo:

  1. PADDING PENÚLTIMO — o container com o texto "TQ Embedded is known
     for:..." (universal, 139/139 páginas) recebe T/B Small
     (1717498052331) + L/R Large (1717498053499). Existe em toda
     página como o bloco logo antes de botoes_wrap_novo.

  2. FUNDIR SPECIFICATIONS + ORDERING INFORMATION — os dois viram um
     único container: title(Specifications) -> table -> title(Ordering
     Information) -> table, nessa ordem. O container fundido recebe
     backgroundColor '#f7f7f7' + T/B Small + L/R Large (confirmado na
     referência — não é 'No Padding' como os outros containers de
     seção, é Small).

     Levantamento real (138 páginas, sem contar a de referência):
       108 páginas: Specifications e Ordering Information já cada um
                    em seu container próprio com title+table juntos —
                    funde os dois containers em um.
        16 páginas: só Ordering Information — não há o que fundir, só
                    aplica padding/background no bloco único.
         7 páginas: só Specifications — idem.
         1 página  (mbls1028a-ind-single-board-computer): título e
                    tabela cada um em SEU PRÓPRIO container (4 blocos:
                    heading_3_wrap, table_1_wrap, heading_4_wrap,
                    table_2_wrap) — funde os 4 num só.
     A detecção é por CONTEÚDO (algum filho tem jcr:title contendo
     'specification' ou 'ordering', ou é uma 'table' adjacente a um
     desses blocos), não por nome de nó fixo — os nomes variam.

NÃO MEXE em: qualquer página sem nenhum dos dois blocos (6 páginas,
já reportadas antes) — fica de fora, reportada no CSV.

SEGURANÇA: só escreve dentro de copia-teste (assert_target_is_safe em
post_node/delete_node). macnicagwi e macnicaglobal2 são SOMENTE LEITURA.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_tq_merge_specs_ordering.py --target /content/copia-teste/.../tq-systems --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_tq_merge_specs_ordering.py --target /content/copia-teste/.../tq-systems
"""

import argparse
import sys

from aem_lib import (
    CONFIG, add_common_args, build_session, crawl_tree, delete_node,
    fetch_with_depth_fallback, flatten_node, list_child_nodes, post_node,
    print_header, session_expired, write_csv,
)

TQ_SYSTEMS_ROOT = "/content/copia-teste/americas/mai/en/products/boards-modules/tq-systems"
CONTAINER_RT = "macnicaglobal2/components/content/container"
TABLE_RT = "macnicaglobal2/components/content/table"
TEXT_RT = "macnicaglobal2/components/content/text"

STYLE_PADDING_TOP_BOTTOM_SMALL = "1717498052331"
STYLE_PADDING_LEFT_RIGHT_LARGE = "1717498053499"
BACKGROUND_COLOR_SECTIONS = "#f7f7f7"
STYLE_ALVO = [STYLE_PADDING_LEFT_RIGHT_LARGE, STYLE_PADDING_TOP_BOTTOM_SMALL]

BLOCO_BOTOES = "botoes_wrap_novo"
TEXTO_KNOWN_FOR = "known for"


def _titulo_de(node):
    return (node.get("jcr:title") or "").strip().lower()


def eh_bloco_specs_ordering(node):
    """True se o bloco de topo tiver, entre seus filhos diretos, um
    title com 'specification'/'ordering' no texto, OU só uma 'table'
    (caso do padrão de 4 blocos separados: a tabela vem em bloco à
    parte, sem título próprio).
    """
    filhos = list_child_nodes(node)
    for _, v in filhos:
        t = _titulo_de(v)
        if "specification" in t or "ordering" in t:
            return "titulo"
    if len(filhos) == 1 and filhos[0][1].get("sling:resourceType") == TABLE_RT:
        return "tabela_solta"
    return None


def achar_grupo_specs_ordering(container):
    """Acha a sequência CONTÍGUA de blocos de topo relacionados a
    Specifications/Ordering Information. Devolve lista de (nome, node,
    tipo) na ordem em que aparecem, ou [] se não achar nenhum.

    Confia em contiguidade: uma vez que o primeiro bloco do grupo é
    achado, inclui blocos seguintes enquanto continuarem sendo
    título-relacionado ou 'tabela solta' (cobre o caso raro de 4
    blocos separados, onde a tabela não tem jcr:title próprio).
    """
    blocos = list_child_nodes(container)
    grupo = []
    dentro = False
    for nome, node in blocos:
        tipo = eh_bloco_specs_ordering(node)
        if tipo == "titulo":
            grupo.append((nome, node, tipo))
            dentro = True
        elif tipo == "tabela_solta" and dentro:
            grupo.append((nome, node, tipo))
        else:
            if dentro and grupo and grupo[-1][2] != "titulo":
                # a tabela solta só pertence ao grupo se veio logo
                # depois de um bloco de título — se já fechamos e
                # aparece outra coisa, para de acumular.
                pass
            dentro = False
    return grupo


def _proximo_nome_livre(container, base):
    if base not in container:
        return base
    i = 2
    while f"{base}_{i}" in container:
        i += 1
    return f"{base}_{i}"


def processar_pagina(session, base_url, path, source_depth, auth_tracker, dry_run):
    linha = {"pagina": path, "penultimo_ajustado": "", "specs_ordering_fundidos": "",
             "blocos_removidos": 0, "status": ""}

    data, status = fetch_with_depth_fallback(session, base_url, path,
                                             source_depth, auth_tracker)
    if data is None:
        linha["status"] = f"ERRO ao ler ({status})"
        return linha

    jcr = data.get("jcr:content", {}) or {}
    container = (jcr.get("root", {}) or {}).get("container", {}) or {}
    blocos = list_child_nodes(container)
    if not blocos:
        linha["status"] = "SEM CONTEÚDO (fora do escopo)"
        return linha

    payload = {}
    blocos_a_apagar = []

    # --- Regra 1: penúltimo (texto "known for") com T/B Small + L/R Large ---
    penultimo_nome = None
    for nome, node in blocos:
        def tem_texto(nd):
            for _, v in list_child_nodes(nd):
                t = v.get("text", "")
                if isinstance(t, str) and TEXTO_KNOWN_FOR in t.lower():
                    return True
                if tem_texto(v):
                    return True
            return False
        if tem_texto(node):
            penultimo_nome = nome
            atuais = node.get("cq:styleIds") or []
            if isinstance(atuais, str):
                atuais = [atuais]
            if set(atuais) != set(STYLE_ALVO):
                base = f"jcr:content/root/container/{nome}"
                payload[f"{base}/cq:styleIds"] = list(STYLE_ALVO)
                payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
                linha["penultimo_ajustado"] = nome
            break

    # --- Regra 2: fundir Specifications + Ordering Information ---
    grupo = achar_grupo_specs_ordering(container)
    if not grupo:
        linha["status"] = "SEM Specifications/Ordering (fora do escopo)"
    elif len(grupo) == 1:
        # só um dos dois existe — sem fusão, só padroniza padding/bg.
        nome, node, _ = grupo[0]
        atuais = node.get("cq:styleIds") or []
        if isinstance(atuais, str):
            atuais = [atuais]
        precisa_style = set(atuais) != set(STYLE_ALVO)
        precisa_bg = node.get("backgroundColor") != BACKGROUND_COLOR_SECTIONS
        if precisa_style or precisa_bg:
            base = f"jcr:content/root/container/{nome}"
            if precisa_style:
                payload[f"{base}/cq:styleIds"] = list(STYLE_ALVO)
                payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
            if precisa_bg:
                payload[f"{base}/backgroundColor"] = BACKGROUND_COLOR_SECTIONS
            linha["specs_ordering_fundidos"] = f"{nome} (só 1 bloco, sem fusão — padronizado)"
    else:
        # 2+ blocos: funde tudo no PRIMEIRO nome do grupo. A ordem final
        # é simplesmente a ordem em que os blocos já apareciam na
        # página — achar_grupo_specs_ordering lê em ordem de leitura, e
        # o levantamento real (138 páginas) confirmou que Specifications
        # sempre vem antes de Ordering Information na origem. Não tenta
        # reclassificar por título: só concatena os filhos de cada
        # bloco do grupo, na ordem em que os blocos vieram.
        nome_final = grupo[0][0]
        base = f"jcr:content/root/container/{nome_final}"

        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = CONTAINER_RT
        payload[f"{base}/cq:styleIds"] = list(STYLE_ALVO)
        payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
        payload[f"{base}/backgroundColor"] = BACKGROUND_COLOR_SECTIONS

        usados = set()
        for nome, node, tipo in grupo:
            for fn, fv in list_child_nodes(node):
                nome_no = fn
                while nome_no in usados:
                    nome_no = f"{fn}_{nome}"  # nomes colidem entre blocos diferentes
                usados.add(nome_no)
                flatten_node(fv, f"{base}/{nome_no}", payload)

        for nome, node, tipo in grupo[1:]:
            blocos_a_apagar.append(nome)

        linha["specs_ordering_fundidos"] = (
            f"{nome_final} (fundiu {', '.join(n for n,_,_ in grupo)})")

    linha["blocos_removidos"] = len(blocos_a_apagar)

    if not payload and not blocos_a_apagar:
        if not linha["status"]:
            linha["status"] = "OK (já correto)"
        return linha

    if dry_run:
        linha["status"] = "DRY-RUN"
        return linha

    if payload:
        st, resposta = post_node(session, base_url, path, payload, auth_tracker)
        if st not in (200, 201):
            linha["status"] = f"ERRO ao escrever ({st}): {resposta[:150]}"
            return linha

    erros = []
    for nome in blocos_a_apagar:
        del_st, _ = delete_node(session, base_url,
                                f"{path}/jcr:content/root/container/{nome}", auth_tracker)
        if del_st not in (200, 204):
            erros.append(nome)

    linha["status"] = "OK"
    if erros:
        linha["status"] += f" | ERRO ao apagar: {', '.join(erros)}"

    return linha


def main():
    parser = argparse.ArgumentParser(
        description="Ajusta padding do penúltimo container e funde "
                    "Specifications+Ordering Information nas páginas-neta de tq-systems")
    parser.add_argument("--target", required=True)
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--output", default="tq_merge_specs_ordering.csv")
    args = parser.parse_args()

    target_root = args.target.rstrip("/")
    if not target_root.startswith(CONFIG["target_prefix"]):
        print(f"[erro] --target precisa estar dentro de {CONFIG['target_prefix']}: "
              f"{target_root}", file=sys.stderr)
        sys.exit(1)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("TQ-SYSTEMS: PENÚLTIMO PADDING + FUNDIR SPECS/ORDERING")
    print(f"  Destino: {target_root}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    print(f"== Percorrendo {target_root} ==")
    inventory = crawl_tree(session, base_url, target_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay, only_pages=True)
    todas = sorted(p for p, m in inventory.items() if m["is_page"])
    netas = []
    for p in todas:
        rel = p[len(TQ_SYSTEMS_ROOT):].lstrip("/")
        partes = rel.split("/") if rel else []
        if len(partes) == 2:
            netas.append(p)
    print(f"  {len(todas)} páginas no total, {len(netas)} são netas (escopo)\n")
    if not netas:
        print(f"[erro] nenhuma página-neta em {target_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    print(f"== Processando {len(netas)} páginas ==")
    for i, path in enumerate(netas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i-1}/{len(netas)} processadas.",
                  file=sys.stderr)
            for resto in netas[i-1:]:
                resultados.append({"pagina": resto, "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = processar_pagina(session, base_url, path, args.source_depth,
                                 auth_tracker, args.dry_run)
        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(netas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output,
              ["pagina", "penultimo_ajustado", "specs_ordering_fundidos",
               "blocos_removidos", "status"],
              resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN", "OK (já correto)"))
    fora = [r for r in resultados if "fora do escopo" in r["status"]]
    erros = [r for r in resultados if "ERRO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas:  {len(resultados)}")
    print(f"    ok:                 {ok}")
    print(f"    penúltimo ajustado: {sum(1 for r in resultados if r['penultimo_ajustado'])}")
    print(f"    specs/ordering:     {sum(1 for r in resultados if r['specs_ordering_fundidos'])}")
    print(f"    blocos removidos:   {sum(r['blocos_removidos'] for r in resultados)}")
    print(f"    sem specs/ordering: {len(fora)}")
    print(f"    erros:              {len(erros)}")

    if fora:
        print(f"\n  --- {len(fora)} página(s) sem Specifications/Ordering ---")
        for r in fora:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
