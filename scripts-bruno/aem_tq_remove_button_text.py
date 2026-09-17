#!/usr/bin/env python3
"""
Remove o componente 'text' de apoio ("Stay up to date..." / "For more
information:") de dentro de cada flexcontaineritem do bloco de botões
(botoes_wrap_novo), criado pelo aem_fix_tq_layout.py em tq-systems.
Deixa só o componente 'button' em cada item.

Confirmado com o Bruno em 16/09/2026: o texto acima dos botões deve
sumir, mantendo só Sign up / Contact us dentro do flexcontainer.

Escopo: só páginas-NETA de tq-systems que têm 'botoes_wrap_novo'
(criado na correção anterior). Não mexe em nada além desses 2 nós
'text' — não toca no botão, no flexcontainer, nem em qualquer outro
bloco da página.

SEGURANÇA: só escreve dentro de copia-teste (assert_target_is_safe em
delete_node). macnicagwi e macnicaglobal2 são SOMENTE LEITURA.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_tq_remove_button_text.py --target /content/copia-teste/.../tq-systems --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_tq_remove_button_text.py --target /content/copia-teste/.../tq-systems
"""

import argparse
import sys

from aem_lib import (
    CONFIG, add_common_args, build_session, crawl_tree, delete_node,
    fetch_with_depth_fallback, list_child_nodes, print_header,
    session_expired, write_csv,
)

TQ_SYSTEMS_ROOT = "/content/copia-teste/americas/mai/en/products/boards-modules/tq-systems"
TEXT_RT = "macnicaglobal2/components/content/text"
FLEXCONTAINER_RT = "macnicaglobal2/components/content/flexcontainer"
BLOCO_BOTOES = "botoes_wrap_novo"


def achar_textos_para_remover(container):
    """Acha os nós 'text' dentro de cada flexcontaineritem do bloco de
    botões. Devolve lista de caminhos relativos (a partir de
    jcr:content/root/container) do próprio nó 'text'.
    """
    bloco = container.get(BLOCO_BOTOES)
    if not bloco or bloco.get("sling:resourceType") != "macnicaglobal2/components/content/container":
        return []
    fc = bloco.get("flexcontainer")
    if not fc or fc.get("sling:resourceType") != FLEXCONTAINER_RT:
        return []

    achados = []
    for item_nome, item in list_child_nodes(fc):
        for nome_filho, filho in list_child_nodes(item):
            if filho.get("sling:resourceType") == TEXT_RT:
                achados.append(
                    f"jcr:content/root/container/{BLOCO_BOTOES}/flexcontainer/"
                    f"{item_nome}/{nome_filho}")
    return achados


def main():
    parser = argparse.ArgumentParser(
        description="Remove o texto de apoio de dentro do bloco de botões "
                    "(botoes_wrap_novo) nas páginas-neta de tq-systems")
    parser.add_argument("--target", required=True,
                        help="Raiz de tq-systems dentro de copia-teste.")
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. RODE SEMPRE ANTES.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--output", default="tq_remove_button_text.csv")
    args = parser.parse_args()

    target_root = args.target.rstrip("/")
    if not target_root.startswith(CONFIG["target_prefix"]):
        print(f"[erro] --target precisa estar dentro de {CONFIG['target_prefix']}: "
              f"{target_root}", file=sys.stderr)
        sys.exit(1)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("TQ-SYSTEMS: REMOVER TEXTO DE APOIO DOS BOTÕES")
    print(f"  Destino: {target_root}")
    print(f"  Remove:  componente 'text' dentro de cada flexcontaineritem "
          f"de {BLOCO_BOTOES}")
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
                resultados.append({"pagina": resto, "textos_removidos": 0,
                                   "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = {"pagina": path, "textos_removidos": 0, "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path,
                                                 args.source_depth, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        container = (jcr.get("root", {}) or {}).get("container", {}) or {}

        caminhos = achar_textos_para_remover(container)
        if not caminhos:
            linha["status"] = "SEM botoes_wrap_novo (fora do escopo)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(netas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        if args.dry_run:
            linha["textos_removidos"] = len(caminhos)
            linha["status"] = "DRY-RUN"
        else:
            erros = []
            removidos = 0
            for caminho_relativo in caminhos:
                del_st, resp = delete_node(session, base_url,
                                           f"{path}/{caminho_relativo}", auth_tracker)
                if del_st in (200, 204):
                    removidos += 1
                else:
                    erros.append(f"{caminho_relativo} ({del_st})")
            linha["textos_removidos"] = removidos
            linha["status"] = "OK" if not erros else f"ERRO: {', '.join(erros)}"

        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(netas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output, ["pagina", "textos_removidos", "status"], resultados)

    total_removidos = sum(r["textos_removidos"] for r in resultados)
    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN"))
    fora_escopo = [r for r in resultados if "fora do escopo" in r["status"]]
    erros = [r for r in resultados if "ERRO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas:  {len(resultados)}")
    print(f"    ok:                 {ok}")
    print(f"    textos removidos:   {total_removidos}")
    print(f"    fora do escopo:     {len(fora_escopo)}")
    print(f"    erros:              {len(erros)}")

    if fora_escopo:
        print(f"\n  --- {len(fora_escopo)} página(s) sem botoes_wrap_novo ---")
        for r in fora_escopo:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
