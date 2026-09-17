#!/usr/bin/env python3
"""
Move o flexcontainer de botões (Sign up / Contact us) para DENTRO do
penúltimo container (o de "TQ Embedded is known for:"), como irmão do
componente 'text' que já está lá — em vez de ficar sozinho no último
container da página. Depois apaga o container antigo que sobra vazio.

Confirmado com o Bruno em 17/09/2026, usando como referência
.../tq-embedded-qoriqr-layerscape/tqmls1088a-embedded-octal-cortex —
lá o container 'known for' tem dois filhos: 'text' e 'flexcontainer',
e não existe mais um container separado só para os botões no final.

O QUE FAZ:
  1. Acha o container com 'flexcontainer' (contendo botões) como filho
     — geralmente o ÚLTIMO bloco de topo, mas a busca é por conteúdo,
     não por posição.
  2. Acha o bloco imediatamente ANTERIOR a ele — deve ser o container
     do texto "known for" (confere que tem um 'text').
  3. Clona o flexcontainer inteiro (via flatten_node — preserva
     styleIds, botões, links) para dentro do container anterior.
  4. Apaga o container antigo que só tinha o flexcontainer (agora
     vazio).

NÃO mexe em páginas que já têm essa estrutura (flexcontainer já dentro
do penúltimo) nem em páginas sem botões.

SEGURANÇA: escreve em copia-teste normalmente. Para macnicaglobal2,
precisa de --permitir-escrita-global2 com o --target exato.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_tq_merge_buttons.py --target /content/copia-teste/.../tq-embedded-power-modules --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_tq_merge_buttons.py --target /content/copia-teste/.../tq-embedded-power-modules
"""

import argparse
import sys

from aem_lib import (
    CONFIG, assert_target_is_safe, add_common_args, build_session, crawl_tree,
    delete_node, fetch_with_depth_fallback, flatten_node, list_child_nodes,
    post_node, print_header, session_expired, write_csv,
)

FLEXCONTAINER_RT = "macnicaglobal2/components/content/flexcontainer"
TEXT_RT = "macnicaglobal2/components/content/text"


def achar_bloco_botoes(container):
    """Acha o bloco de topo cujo único filho de conteúdo é um
    'flexcontainer' — devolve (idx, nome_bloco, node_bloco,
    nome_flexcontainer, node_flexcontainer) ou None.
    """
    blocos = list_child_nodes(container)
    for idx, (nome_bloco, node_bloco) in enumerate(blocos):
        filhos = list_child_nodes(node_bloco)
        for nome_filho, node_filho in filhos:
            if node_filho.get("sling:resourceType") == FLEXCONTAINER_RT:
                return idx, nome_bloco, node_bloco, nome_filho, node_filho
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Move o flexcontainer de botões para dentro do penúltimo "
                    "container (known-for), apagando o container antigo vazio")
    parser.add_argument("--target", required=True)
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    parser.add_argument("--output", default="fix_tq_merge_buttons.csv")
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

    print_header("TQ: MOVER BOTÕES PARA DENTRO DO PENÚLTIMO CONTAINER")
    print(f"  Destino: {target_root}")
    print(f"  Move:    flexcontainer de botões -> dentro do container 'known for' anterior")
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

        linha = {"pagina": path, "bloco_antigo": "", "bloco_destino": "", "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path,
                                                 args.source_depth, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        container = (jcr.get("root", {}) or {}).get("container", {}) or {}
        blocos = list_child_nodes(container)

        achado = achar_bloco_botoes(container)
        if not achado:
            linha["status"] = "SEM bloco de botões (fora do escopo)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        idx_botoes, nome_botoes, node_botoes, nome_fc, node_fc = achado

        # Já dentro do penúltimo? (flexcontainer não sozinho no bloco)
        filhos_bloco_botoes = list_child_nodes(node_botoes)
        if len(filhos_bloco_botoes) > 1:
            linha["status"] = "OK (já dentro de outro bloco, nada a mover)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        if idx_botoes == 0:
            linha["status"] = "ERRO: bloco de botões é o primeiro, sem bloco anterior"
            resultados.append(linha)
            continue

        nome_anterior, node_anterior = blocos[idx_botoes - 1]
        tem_text_anterior = any(v.get("sling:resourceType") == TEXT_RT
                                for _, v in list_child_nodes(node_anterior))
        if not tem_text_anterior:
            linha["status"] = (f"PULADO: bloco anterior ({nome_anterior}) não tem "
                              f"'text' — não parece ser o known-for")
            resultados.append(linha)
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        linha["bloco_antigo"] = nome_botoes
        linha["bloco_destino"] = nome_anterior

        base_destino = f"jcr:content/root/container/{nome_anterior}/{nome_fc}"
        payload = {}
        flatten_node(node_fc, base_destino, payload)

        if args.dry_run:
            linha["status"] = "DRY-RUN"
        else:
            st, resposta = post_node(session, base_url, path, payload, auth_tracker,
                                     allow_extra=allow_extra)
            if st not in (200, 201):
                linha["status"] = f"ERRO ao escrever ({st}): {resposta[:120]}"
                resultados.append(linha)
                continue

            del_st, _ = delete_node(
                session, base_url, f"{path}/jcr:content/root/container/{nome_botoes}",
                auth_tracker, allow_extra=allow_extra)
            if del_st not in (200, 204):
                linha["status"] = (f"OK (movido), mas ERRO ao apagar container antigo "
                                  f"({del_st}) — remover {nome_botoes} manualmente")
                resultados.append(linha)
                continue

            linha["status"] = "OK"

        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output, ["pagina", "bloco_antigo", "bloco_destino", "status"], resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN"))
    ja_correto = sum(1 for r in resultados if "já dentro" in r["status"])
    pulados = [r for r in resultados if "PULADO" in r["status"]]
    erros = [r for r in resultados if "ERRO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}")
    print(f"    movidas:           {ok}")
    print(f"    já corretas:       {ja_correto}")
    print(f"    puladas:           {len(pulados)}")
    print(f"    erros:             {len(erros)}")

    if pulados:
        print(f"\n  --- {len(pulados)} página(s) puladas (verificar manualmente) ---")
        for r in pulados[:10]:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
