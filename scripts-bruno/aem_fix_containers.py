#!/usr/bin/env python3
"""
Corrige a estrutura e o estilo das páginas JÁ CRIADAS em copia-teste,
trazendo o que já existe para o mesmo padrão que aem_migrate.py gera.

O QUE FAZ (pedidos do Bruno, ver aem_lib.py / BlockBuilder):
  1. Remove o container-pai intermediário, promovendo os blocos:
       ANTES: root/container/containerpy/title_wrap/title
       DEPOIS: root/container/title_wrap/title
  2. backgroundColor alternado #fff / #f7f7f7 a cada bloco
  3. padding Left/Right Large em TODOS os containers de bloco
     padding Top/Bottom Small só no PRIMEIRO (o do título)
     (via cq:styleIds — os IDs vêm da policy real do container)
  4. Remove os blocos de espaçamento vazios dos textos
     ('<p>&nbsp;</p>' que o autor do GWI usava como "enter")

Roda tanto em página de 3 níveis (promove + estiliza) quanto em página
que já está em 2 níveis (só reaplica estilo e limpa texto), então pode
ser rodado de novo com segurança depois de uma correção parcial.

Este script NÃO recria páginas — ele lê a estrutura de cada página já
existente e a REESCREVE no formato novo, preservando os blocos como
estão (mesma técnica de flatten_node usada no clone fiel, não uma
tradução de conteúdo).

IDEMPOTENTE: uma página que já está no formato de 2 níveis (ou vazia) é
detectada e pulada, reportada como "JÁ CORRETA"/"VAZIA" no CSV — rodar de
novo não duplica nem quebra nada.

ORDEM DE ESCRITA (evita perda de conteúdo se algo falhar no meio):
  1. Escreve os blocos promovidos direto em root/container/<bloco>_wrap
  2. Só DEPOIS de confirmar OK, apaga o container-pai antigo
  Se o passo 1 falhar, o container-pai antigo continua intacto — nada é
  perdido.

SEGURANÇA: mesma trava de sempre (assert_target_is_safe, embutida em
post_node/delete_node) — só escreve/apaga dentro de copia-teste, mesmo
que --source aponte para outro lugar por engano.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_containers.py --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_containers.py
"""

import argparse
import sys
from urllib.parse import urljoin

from aem_lib import (
    ALTERNATING_BACKGROUND_COLORS, CONFIG, STYLE_PADDING_LEFT_RIGHT_LARGE,
    STYLE_PADDING_TOP_BOTTOM_SMALL, add_common_args, build_session,
    crawl_tree, delete_node, fetch_with_depth_fallback, flatten_node,
    list_child_nodes, post_node, print_header, session_expired,
    strip_empty_blocks, write_csv,
)

# Propriedades de texto rico que recebem a limpeza de blocos vazios.
# 'text' cobre os componentes text e table do GLOBAL2 (ambos usam a mesma
# convenção text/textIsRich, confirmado nos exemplos autorais).
RICH_TEXT_PROPS = ("text",)


def find_container_slot(jcr_content):
    """Acha jcr:content/root/container, se existir."""
    root = jcr_content.get("root")
    if not isinstance(root, dict):
        return None
    container = root.get("container")
    if not isinstance(container, dict):
        return None
    return container


def find_legacy_parent(container_node):
    """Detecta o padrão antigo: um ÚNICO filho do slot que por sua vez
    tem um ou mais '<algo>_wrap' dentro dele — esse filho único é o
    container-pai a remover. Não assume o nome 'containerpy': o padrão
    real observado em páginas autorais usa nomes gerados
    (ex: 'container_386242080_').

    Retorna (nome_do_pai, node_do_pai) ou (None, None) se a página já
    estiver no formato novo (blocos direto no slot) ou vazia.
    """
    filhos = list_child_nodes(container_node)
    if len(filhos) != 1:
        # 0 filhos = vazia; 2+ filhos = já são os blocos promovidos
        # (title_wrap, text_1_wrap, ...) direto no slot — já corrigida.
        return None, None

    nome, node = filhos[0]
    netos = list_child_nodes(node)
    parece_bloco_unico = nome.endswith("_wrap") and len(netos) == 1
    if parece_bloco_unico:
        # Um único bloco na página inteira: container/algo_wrap/algo — já
        # é o formato novo (só tem 1 bloco de conteúdo), não é o pai antigo.
        return None, None

    # Filho único que não parece ser ele mesmo um "_wrap" de bloco final
    # (ou tem múltiplos netos) => é o container-pai antigo envolvendo os
    # blocos de verdade.
    return nome, node


def limpar_textos(payload, base):
    """Aplica strip_empty_blocks em toda propriedade de texto rico abaixo
    de 'base' no payload já achatado.

    Devolve quantas propriedades foram efetivamente alteradas — serve
    para o relatório dizer se a página tinha blocos vazios ou não.
    """
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


def build_blocks_payload(blocos_node):
    """Reescreve os blocos direto no slot root/container, aplicando as
    três correções de uma vez:

      - backgroundColor alternado (#fff / #f7f7f7)
      - padding L/R Large em todos os containers de bloco
      - padding T/B Small só no primeiro (o do título)
      - limpeza dos blocos de espaçamento vazios nos textos

    Serve tanto para promover um container-pai antigo (3 níveis -> 2)
    quanto para só reaplicar estilo/limpeza numa página que já está em 2
    níveis — em ambos os casos a entrada é o nó que CONTÉM os '*_wrap'.
    """
    payload = {
        "jcr:content/root/container/jcr:primaryType": "nt:unstructured",
        "jcr:content/root/container/sling:resourceType":
            "macnicaglobal2/components/content/container",
    }
    nomes_blocos = []
    textos_limpos = 0

    for i, (nome_wrap, node_wrap) in enumerate(list_child_nodes(blocos_node)):
        nomes_blocos.append(nome_wrap)
        base = f"jcr:content/root/container/{nome_wrap}"
        flatten_node(node_wrap, base, payload)

        # Cor alternada, na ordem em que os blocos aparecem.
        payload[f"{base}/backgroundColor"] = \
            ALTERNATING_BACKGROUND_COLORS[i % len(ALTERNATING_BACKGROUND_COLORS)]

        # Padding: L/R Large em todos; T/B Small só no primeiro.
        styles = [STYLE_PADDING_LEFT_RIGHT_LARGE]
        if i == 0:
            styles.append(STYLE_PADDING_TOP_BOTTOM_SMALL)
        payload[f"{base}/cq:styleIds"] = styles
        # TypeHint obrigatório: sem ele, uma lista de 1 elemento vira
        # String simples no JCR, e o padrão autoral real é String[].
        payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"

        textos_limpos += limpar_textos(payload, base)

    return payload, nomes_blocos, textos_limpos


def main():
    parser = argparse.ArgumentParser(
        description="Corrige a estrutura de containers já criada em copia-teste "
                    "(remove o container-pai, aplica cor alternada)")
    parser.add_argument("--source", default=CONFIG["target_prefix"],
                        help="Raiz a corrigir. Padrão: toda a área de teste.")
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. RODE SEMPRE ANTES.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--output", default="fix_containers.csv")
    args = parser.parse_args()

    source_root = args.source.rstrip("/")
    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("CORREÇÃO DE CONTAINERS")
    print(f"  Raiz:  {source_root}")
    print(f"  Cores: {ALTERNATING_BACKGROUND_COLORS}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    print(f"== Percorrendo {source_root} ==")
    inventory = crawl_tree(session, base_url, source_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay,
                           only_pages=True)
    paginas = sorted(p for p, m in inventory.items() if m["is_page"])
    print(f"  {len(paginas)} páginas encontradas\n")

    if not paginas:
        print(f"[erro] nenhuma página encontrada em {source_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    print(f"== Processando {len(paginas)} páginas ==")
    for i, path in enumerate(paginas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i - 1}/{len(paginas)} processadas.",
                  file=sys.stderr)
            for resto in paginas[i - 1:]:
                resultados.append({"pagina": resto, "blocos_promovidos": "",
                                   "container_pai_antigo": "",
                                   "status": "NÃO TENTADO (sessão expirou)"})
            break

        data, status = fetch_with_depth_fallback(
            session, base_url, path, args.source_depth, auth_tracker)
        if data is None:
            resultados.append({"pagina": path, "blocos_promovidos": "",
                               "container_pai_antigo": "",
                               "status": f"ERRO ao ler (status {status})"})
            continue

        container = find_container_slot(data.get("jcr:content", {}) or {})
        if container is None:
            resultados.append({"pagina": path, "blocos_promovidos": 0,
                               "container_pai_antigo": "",
                               "status": "VAZIA (sem root/container)"})
            continue

        nome_pai, node_pai = find_legacy_parent(container)

        # Dois casos, mesmo payload:
        #   - 3 níveis: promover os filhos do container-pai (e apagá-lo)
        #   - 2 níveis: os blocos já estão no slot, só reaplicar
        #     estilo/cor/limpeza de texto
        blocos_node = node_pai if nome_pai else container
        if not list_child_nodes(blocos_node):
            resultados.append({"pagina": path, "blocos": 0,
                               "container_pai_antigo": "", "textos_limpos": 0,
                               "status": "VAZIA (sem blocos)"})
            continue

        payload, nomes_blocos, textos_limpos = build_blocks_payload(blocos_node)
        acao = "promoveria" if nome_pai else "reaplicaria estilo em"

        if args.dry_run:
            status_label = (f"DRY-RUN ({acao} {len(nomes_blocos)} blocos, "
                            f"{textos_limpos} texto(s) a limpar)")
        else:
            post_status, resposta = post_node(session, base_url, path, payload,
                                              auth_tracker)
            if post_status not in (200, 201):
                resultados.append({"pagina": path, "blocos": 0,
                                   "container_pai_antigo": nome_pai or "",
                                   "textos_limpos": 0,
                                   "status": f"ERRO ao escrever ({post_status}): {resposta}"})
                continue

            status_label = "OK"
            if nome_pai:
                # Só apaga o container-pai antigo DEPOIS de confirmar que a
                # promoção foi escrita com sucesso.
                del_path = f"{path}/jcr:content/root/container/{nome_pai}"
                del_status, _ = delete_node(session, base_url, del_path, auth_tracker)
                if del_status not in (200, 204):
                    status_label = (f"OK (promovido), mas ERRO ao apagar pai antigo "
                                    f"({del_status}) — remova manualmente {nome_pai}")

        resultados.append({"pagina": path, "blocos": len(nomes_blocos),
                           "container_pai_antigo": nome_pai or "",
                           "textos_limpos": textos_limpos,
                           "status": status_label})

        if i % 10 == 0 or i <= 5 or "ERRO" in resultados[-1]["status"]:
            print(f"  [{i}/{len(paginas)}] {path} -> {resultados[-1]['status']}")

    write_csv(args.output,
              ["pagina", "blocos", "container_pai_antigo", "textos_limpos", "status"],
              resultados)

    ok = sum(1 for r in resultados if r["status"] == "OK" or "DRY-RUN" in r["status"])
    promovidas = sum(1 for r in resultados if r["container_pai_antigo"])
    vazias = sum(1 for r in resultados if "VAZIA" in r["status"])
    erros = sum(1 for r in resultados if "ERRO" in r["status"])
    textos = sum(r["textos_limpos"] for r in resultados
                 if isinstance(r.get("textos_limpos"), int))

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}")
    print(f"    corrigidas:            {ok}")
    print(f"      (com container-pai removido: {promovidas})")
    print(f"    vazias:                {vazias}")
    print(f"    erros:                 {erros}")
    print(f"  Textos com blocos vazios limpos: {textos}")
    print(f"\n  Relatório: {args.output}")

    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")
    elif ok:
        print(f"\n  Confira visualmente no editor:")
        print(f"    - o container-pai sumiu (onde havia)")
        print(f"    - a cor alterna entre os blocos (#fff / #f7f7f7)")
        print(f"    - o 1º container (título) tem padding top/bottom Small")
        print(f"    - todos os containers têm padding left/right Large")
        print(f"    - os espaços vazios entre parágrafos sumiram")
        print(f"  Recomendado rodar aem_verify.py de novo sobre as árvores afetadas.")


if __name__ == "__main__":
    main()
