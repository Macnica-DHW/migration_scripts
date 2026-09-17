#!/usr/bin/env python3
"""
Corrige o bloco de introdução das páginas-neta de tq-systems: hoje o
H1+parágrafo introdutório está num componente 'text' puro (sem imagem)
e o bloco "Features" está no 'textwithimage' (com a imagem) — invertido
do padrão confirmado com o Bruno em 17/09/2026, usando
.../tq-embedded-qoriqr-layerscape/tqmls1088a-embedded-octal-cortex
como referência.

O QUE FAZ (só nas páginas que têm o padrão invertido — 'text' com H1 +
'textwithimage' com Features, adjacentes no mesmo container):

  1. Troca o CONTEÚDO 'text' dos dois componentes: o H1+intro (hoje no
     'text' puro) passa a ficar no 'textwithimage' (que mantém sua
     imagem, fileReference, alt etc — só o campo 'text' muda). O
     "Features" (hoje no 'textwithimage') vira o texto de um 'text'
     puro novo, sem imagem.
  2. Aplica no CONTAINER do bloco 2 (imagem) padding L/R Large
     (1717498053499) + T/B No Padding (1717498056876) — confirmado na
     página de referência. No componente 'textwithimage' de dentro,
     aplica 'Image Position: Left' (1718154328384) + Vertical
     Alignment: Center (1783061491236).
  3. Aplica backgroundColor '#f0f0f0' (rgb(240,240,240) convertido,
     confirmado com o Bruno) no bloco de Features resultante.

NÃO mexe em páginas que já não têm mais esse padrão (ex: tqmt1022, que
já foi reorganizada antes — só sobrou Specifications+Ordering).

SEGURANÇA: escreve em copia-teste normalmente. Para macnicaglobal2,
precisa de --permitir-escrita-global2 com o --target exato.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_tq_image_swap.py --target /content/copia-teste/.../tq-embedded-power-modules --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_tq_image_swap.py --target /content/copia-teste/.../tq-embedded-power-modules
"""

import argparse
import sys

from aem_lib import (
    CONFIG, assert_target_is_safe, add_common_args, build_session, crawl_tree,
    delete_node, fetch_with_depth_fallback, flatten_node, list_child_nodes,
    post_node, print_header, session_expired, write_csv,
)

CONTAINER_RT = "macnicaglobal2/components/content/container"
STYLE_PADDING_LEFT_RIGHT_LARGE = "1717498053499"

TEXT_RT = "macnicaglobal2/components/content/text"
TEXTWITHIMAGE_RT = "macnicaglobal2/components/content/textwithimage"

STYLE_IMAGE_POSITION_LEFT = "1718154328384"
STYLE_VERTICAL_ALIGN_CENTER = "1783061491236"
STYLE_PADDING_TOP_BOTTOM_NO_PADDING = "1717498056876"
BACKGROUND_COLOR_FEATURES = "#f0f0f0"


def achar_par_invertido(container):
    """Acha, entre os blocos de topo, o primeiro que tiver um 'text'
    (H1 no início) e um 'textwithimage' como filhos diretos — devolve
    (nome_bloco, nome_anterior, nome_text, node_text, nome_twi,
    node_twi) ou None se não achar (página já corrigida ou com outro
    layout). nome_anterior é o bloco de topo logo antes de nome_bloco
    (ou None se for o primeiro) — usado para reordenar os containers
    novos de volta na mesma posição do antigo.
    """
    blocos = list_child_nodes(container)
    for idx, (nome_bloco, node_bloco) in enumerate(blocos):
        filhos = list_child_nodes(node_bloco)
        text_item = None
        twi_item = None
        for nome_filho, node_filho in filhos:
            rt = node_filho.get("sling:resourceType")
            if rt == TEXT_RT and text_item is None:
                text_item = (nome_filho, node_filho)
            elif rt == TEXTWITHIMAGE_RT and twi_item is None:
                twi_item = (nome_filho, node_filho)
        if text_item and twi_item:
            texto_h1 = text_item[1].get("text", "")
            if isinstance(texto_h1, str) and "<h1" in texto_h1.lower():
                nome_anterior = blocos[idx - 1][0] if idx > 0 else None
                return (nome_bloco, nome_anterior, text_item[0], text_item[1],
                        twi_item[0], twi_item[1])
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Troca o texto entre 'text' (H1) e 'textwithimage' (Features) "
                    "nas páginas-neta de tq-systems, com Image Position Left e "
                    "background no bloco Features")
    parser.add_argument("--target", required=True)
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    parser.add_argument("--output", default="fix_tq_image_swap.csv")
    args = parser.parse_args()

    target_root = args.target.rstrip("/")

    allow_extra = ()
    if args.permitir_escrita_global2:
        liberado = args.permitir_escrita_global2.rstrip("/")
        if liberado != target_root:
            print(f"[erro] --permitir-escrita-global2 não bate com --target:\n"
                  f"  liberado: {liberado}\n  target:   {target_root}", file=sys.stderr)
            sys.exit(1)
        allow_extra = (liberado,)
    else:
        assert_target_is_safe(target_root)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("TQ: TROCA TEXT<->TEXTWITHIMAGE (H1/Features) + BACKGROUND")
    print(f"  Destino: {target_root}")
    print(f"  Troca:   texto do 'text' (H1) <-> texto do 'textwithimage' (Features)")
    print(f"  Aplica:  Image Position Left no textwithimage, background {BACKGROUND_COLOR_FEATURES} no text de Features")
    if allow_extra:
        print(f"  *** ESCRITA EM MACNICAGLOBAL2 LIBERADA (exceção pontual): "
              f"{allow_extra[0]} ***")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    print(f"== Percorrendo {target_root} ==")
    inventory = crawl_tree(session, base_url, target_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay, only_pages=True)
    paginas = sorted(p for p, m in inventory.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")
    if not paginas:
        print(f"[erro] nenhuma página em {target_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    print(f"== Processando {len(paginas)} páginas ==")

    for i, path in enumerate(paginas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i-1}/{len(paginas)} processadas.",
                  file=sys.stderr)
            for resto in paginas[i-1:]:
                resultados.append({"pagina": resto, "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = {"pagina": path, "bloco": "", "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path,
                                                 args.source_depth, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        container = (jcr.get("root", {}) or {}).get("container", {}) or {}

        achado = achar_par_invertido(container)
        if not achado:
            linha["status"] = "SEM padrão invertido (já corrigida ou layout diferente)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        nome_bloco, nome_anterior, nome_text, node_text, nome_twi, node_twi = achado
        linha["bloco"] = nome_bloco

        texto_h1 = node_text.get("text", "")
        texto_features = node_twi.get("text", "")

        # A policy de 'text' não suporta backgroundColor (só 'container'
        # suporta) — achado real testado em 17/09/2026. Na referência,
        # H1+imagem e Features já ficam em containers SEPARADOS. Por
        # isso a correção cria 2 containers novos (um só com o
        # textwithimage+H1+imagem, outro só com o text+Features+
        # background) e apaga o container antigo que tinha os dois
        # juntos — não dá pra só trocar propriedade no lugar.
        nome_container_imagem = f"{nome_bloco}_imagem"
        nome_container_features = f"{nome_bloco}_features"
        base_img = f"jcr:content/root/container/{nome_container_imagem}"
        base_feat = f"jcr:content/root/container/{nome_container_features}"
        payload = {}

        # Container 1: textwithimage com o texto do H1 (clona o nó
        # inteiro via flatten_node — preserva fileReference, alt,
        # imageRatio, spImage etc — só o 'text' é sobrescrito depois).
        payload[f"{base_img}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base_img}/sling:resourceType"] = CONTAINER_RT
        payload[f"{base_img}/cq:styleIds"] = [STYLE_PADDING_LEFT_RIGHT_LARGE,
                                              STYLE_PADDING_TOP_BOTTOM_NO_PADDING]
        payload[f"{base_img}/cq:styleIds@TypeHint"] = "String[]"
        flatten_node(node_twi, f"{base_img}/{nome_twi}", payload)
        payload[f"{base_img}/{nome_twi}/text"] = texto_h1
        atuais_twi = node_twi.get("cq:styleIds") or []
        if isinstance(atuais_twi, str):
            atuais_twi = [atuais_twi]
        novos_twi = [s for s in atuais_twi if s and s != STYLE_IMAGE_POSITION_LEFT]
        novos_twi.append(STYLE_IMAGE_POSITION_LEFT)
        if STYLE_VERTICAL_ALIGN_CENTER not in novos_twi:
            novos_twi.append(STYLE_VERTICAL_ALIGN_CENTER)
        payload[f"{base_img}/{nome_twi}/cq:styleIds"] = novos_twi
        payload[f"{base_img}/{nome_twi}/cq:styleIds@TypeHint"] = "String[]"

        # Container 2: text com Features + background (o background
        # vai no CONTAINER, não no componente text de dentro).
        payload[f"{base_feat}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base_feat}/sling:resourceType"] = CONTAINER_RT
        payload[f"{base_feat}/cq:styleIds"] = [STYLE_PADDING_LEFT_RIGHT_LARGE]
        payload[f"{base_feat}/cq:styleIds@TypeHint"] = "String[]"
        payload[f"{base_feat}/backgroundColor"] = BACKGROUND_COLOR_FEATURES
        flatten_node(node_text, f"{base_feat}/{nome_text}", payload)
        payload[f"{base_feat}/{nome_text}/text"] = texto_features

        if args.dry_run:
            linha["status"] = "DRY-RUN"
        else:
            st, resposta = post_node(session, base_url, path, payload, auth_tracker,
                                     allow_extra=allow_extra)
            if st not in (200, 201):
                linha["status"] = f"ERRO ao escrever ({st}): {resposta[:120]}"
                resultados.append(linha)
                continue

            del_st, del_resp = delete_node(
                session, base_url, f"{path}/jcr:content/root/container/{nome_bloco}",
                auth_tracker, allow_extra=allow_extra)
            if del_st not in (200, 204):
                linha["status"] = (f"OK (novos containers), mas ERRO ao apagar "
                                  f"container antigo ({del_st}) — remover "
                                  f"{nome_bloco} manualmente")
                resultados.append(linha)
                continue

            # Reordena os 2 novos de volta pra posição do antigo — sem
            # isso eles caem no fim da página (achado real, testado em
            # 17/09/2026: novo nó sempre entra por último, precisa de
            # POST de ':order' à parte, DEPOIS de já existir).
            erro_ordem = None
            if nome_anterior:
                ordem_valor = f"after {nome_anterior}"
            else:
                ordem_valor = "first"
            st_o1, resp_o1 = post_node(
                session, base_url,
                f"{path}/jcr:content/root/container/{nome_container_imagem}",
                {":order": ordem_valor}, auth_tracker, allow_extra=allow_extra)
            if st_o1 not in (200, 201):
                erro_ordem = f"imagem ({st_o1})"
            else:
                st_o2, resp_o2 = post_node(
                    session, base_url,
                    f"{path}/jcr:content/root/container/{nome_container_features}",
                    {":order": f"after {nome_container_imagem}"}, auth_tracker,
                    allow_extra=allow_extra)
                if st_o2 not in (200, 201):
                    erro_ordem = f"features ({st_o2})"

            if erro_ordem:
                linha["status"] = (f"OK (conteúdo certo), mas ERRO ao reordenar "
                                  f"{erro_ordem} — corrigir ordem manualmente")
                resultados.append(linha)
                continue

            linha["status"] = "OK"

        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output, ["pagina", "bloco", "status"], resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN"))
    sem_padrao = [r for r in resultados if "SEM padrão" in r["status"]]
    erros = [r for r in resultados if "ERRO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}")
    print(f"    corrigidas:        {ok}")
    print(f"    sem padrão invertido: {len(sem_padrao)}")
    print(f"    erros:             {len(erros)}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
