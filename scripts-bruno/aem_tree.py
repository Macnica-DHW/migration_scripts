#!/usr/bin/env python3
"""
Explora a árvore completa de QUALQUER caminho do AEM. SOMENTE LEITURA.

Você passa UM caminho e ele desce recursivamente tudo que existe dentro,
sem precisar saber de antemão o que tem lá. Funciona em qualquer nível:

    /content                      -> todos os sites da instância
    /content/macnicagwi           -> tudo do GWI
    /content/macnicagwi/americas  -> só a região americas
    /content/dam/macnicagwi       -> a árvore de assets

Não cria, move, altera nem deleta nada — só faz GET .json.

SAÍDA:
  - árvore desenhada no terminal (com filtros de profundidade)
  - CSV com uma linha por nó: caminho, título, template, tipo, se é
    página, se tem conteúdo, profundidade
  - com --componentes: conta também os tipos de componente de cada
    página, e imprime o ranking geral no fim (útil para saber o que o
    migrate ainda não sabe tratar)

COMO RODAR:
  # visão geral, 2 níveis
  python3 aem_tree.py /content/macnicagwi --max-depth 2

  # árvore inteira de uma categoria, com CSV
  python3 aem_tree.py /content/macnicagwi/americas/mai/en/products/semiconductors

  # só as páginas de verdade (pula pastas), contando componentes
  python3 aem_tree.py /content/macnicagwi/americas --so-paginas --componentes
"""

import argparse
import sys
from collections import Counter
from urllib.parse import urljoin

from aem_lib import (
    CONFIG, add_common_args, build_session, crawl_tree, fetch_with_depth_fallback,
    list_child_nodes, print_header, session_expired, write_csv,
)


def contar_componentes(jcr_content):
    """Conta os sling:resourceType dentro de um jcr:content, recursivamente."""
    contagem = Counter()

    def walk(node):
        for _, child in list_child_nodes(node):
            rt = child.get("sling:resourceType")
            if rt:
                contagem[rt] += 1
            walk(child)

    walk(jcr_content)
    return contagem


def desenhar_arvore(inventory, root_path, max_linhas=400):
    """Desenha a árvore no terminal, com prefixos de ramo."""
    caminhos = sorted(inventory.keys())
    if not caminhos:
        return

    print_header(f"ÁRVORE: {root_path}")
    print()

    # Para cada caminho, descobre se é o último filho do seu pai — é o que
    # decide entre o prefixo └── e o ├──.
    filhos_por_pai = {}
    for p in caminhos:
        pai = p.rsplit("/", 1)[0]
        filhos_por_pai.setdefault(pai, []).append(p)

    mostrados = 0
    for path in caminhos:
        if mostrados >= max_linhas:
            print(f"\n  ... e mais {len(caminhos) - mostrados} nós "
                  f"(lista completa no CSV)")
            break

        meta = inventory[path]
        nivel = meta["depth"]

        if nivel == 0:
            print(f"{path}")
            mostrados += 1
            continue

        pai = path.rsplit("/", 1)[0]
        irmaos = filhos_por_pai.get(pai, [])
        eh_ultimo = irmaos and path == irmaos[-1]
        ramo = "└── " if eh_ultimo else "├── "
        nome = path.rsplit("/", 1)[-1]

        marca = "" if meta["is_page"] else "  [pasta]"
        if meta["is_page"] and not meta["has_content"]:
            marca = "  [vazia]"

        titulo = meta["title"]
        rotulo = f"{nome}" + (f"  — {titulo}" if titulo and titulo != nome else "")
        print(f"{'│   ' * (nivel - 1)}{ramo}{rotulo}{marca}")
        mostrados += 1


def main():
    parser = argparse.ArgumentParser(
        description="Explora a árvore completa de qualquer caminho do AEM (somente leitura)")
    parser.add_argument("caminho", nargs="?", default=CONFIG["gwi_prefix"],
                        help="Caminho raiz a explorar. Ex: /content/macnicagwi")
    add_common_args(parser)
    parser.add_argument("--max-depth", type=int, default=None,
                        help="Níveis a descer a partir da raiz (0 = só a raiz). "
                             "Sem isso, desce até o fim.")
    parser.add_argument("--so-paginas", action="store_true",
                        help="Lista só nós que são páginas de verdade, pulando pastas "
                             "(continua descendo nelas para achar páginas dentro).")
    parser.add_argument("--componentes", action="store_true",
                        help="Também conta os tipos de componente de cada página. "
                             "Mais lento: faz um GET profundo por página.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"],
                        help="Profundidade do .json ao contar componentes.")
    parser.add_argument("--skip-path-contains", action="append", default=None,
                        help="Ignora caminhos contendo este texto (pode repetir).")
    parser.add_argument("--sem-arvore", action="store_true",
                        help="Não desenha a árvore, só gera o CSV e o resumo.")
    parser.add_argument("--output", default=None,
                        help="CSV de saída. Padrão: arvore_<ultimo-segmento>.csv")
    args = parser.parse_args()

    caminho = args.caminho.rstrip("/")
    if not caminho.startswith("/"):
        print(f"[erro] o caminho precisa ser absoluto (começar com /): {caminho}",
              file=sys.stderr)
        sys.exit(1)

    skip = args.skip_path_contains if args.skip_path_contains is not None \
        else CONFIG["skip_path_contains"]
    output = args.output or f"arvore_{caminho.rstrip('/').rsplit('/', 1)[-1]}.csv"

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header(f"EXPLORANDO {caminho}")
    if args.max_depth is not None:
        print(f"  profundidade máxima: {args.max_depth}")
    if skip:
        print(f"  ignorando caminhos com: {', '.join(skip)}")
    print()

    inventory = crawl_tree(
        session, base_url, caminho, auth_tracker,
        max_pages=args.max_pages, max_depth=args.max_depth, delay=args.delay,
        skip_contains=skip, only_pages=args.so_paginas,
    )

    if not inventory:
        print(f"\n[erro] nada encontrado em {caminho}.", file=sys.stderr)
        print("  Confira se o caminho existe e se a sessão ainda é válida.",
              file=sys.stderr)
        sys.exit(1)

    print(f"\n  {len(inventory)} nós encontrados\n")

    # --- Componentes (opcional) ---
    componentes_globais = Counter()
    if args.componentes:
        paginas = [p for p, m in inventory.items() if m["is_page"]]
        print(f"== Contando componentes em {len(paginas)} páginas ==")
        for i, path in enumerate(paginas, 1):
            if session_expired(auth_tracker):
                print(f"  [erro] sessão expirou em {i - 1}/{len(paginas)}.",
                      file=sys.stderr)
                break
            data, _ = fetch_with_depth_fallback(
                session, base_url, path, args.source_depth, auth_tracker)
            if data is None:
                continue
            contagem = contar_componentes(data.get("jcr:content", {}) or {})
            inventory[path]["componentes"] = dict(contagem)
            inventory[path]["qtd_componentes"] = sum(contagem.values())
            componentes_globais.update(contagem)
            if i % 25 == 0:
                print(f"  [{i}/{len(paginas)}] ...", flush=True)
        print()

    # --- Árvore ---
    if not args.sem_arvore:
        desenhar_arvore(inventory, caminho)
        print()

    # --- CSV ---
    linhas = []
    for path in sorted(inventory.keys()):
        m = inventory[path]
        linha = {
            "caminho": path,
            "nome": path.rsplit("/", 1)[-1],
            "titulo": m["title"],
            "profundidade": m["depth"],
            "eh_pagina": "sim" if m["is_page"] else "não",
            "template": m["template"] or "",
            "resource_type": m["resource_type"] or "",
            "tem_conteudo": "sim" if m["has_content"] else "não",
            "qtd_filhos": len(m["children"]),
        }
        if args.componentes:
            linha["qtd_componentes"] = m.get("qtd_componentes", "")
            linha["componentes"] = "; ".join(
                f"{rt}={n}" for rt, n in sorted(m.get("componentes", {}).items()))
        linhas.append(linha)

    campos = ["caminho", "nome", "titulo", "profundidade", "eh_pagina", "template",
              "resource_type", "tem_conteudo", "qtd_filhos"]
    if args.componentes:
        campos += ["qtd_componentes", "componentes"]
    write_csv(output, campos, linhas)

    # --- Resumo ---
    paginas = [m for m in inventory.values() if m["is_page"]]
    pastas = [m for m in inventory.values() if not m["is_page"]]
    vazias = [m for m in paginas if not m["has_content"]]
    profundidade_max = max((m["depth"] for m in inventory.values()), default=0)

    print_header("RESUMO")
    print(f"  Raiz explorada:      {caminho}")
    print(f"  Total de nós:        {len(inventory)}")
    print(f"    páginas:           {len(paginas)}")
    print(f"    pastas/outros:     {len(pastas)}")
    if paginas:
        print(f"    páginas vazias:    {len(vazias)}")
    print(f"  Profundidade máxima: {profundidade_max}")

    templates = Counter(m["template"] for m in paginas if m["template"])
    if templates:
        print(f"\n  Templates em uso ({len(templates)}):")
        for tmpl, n in templates.most_common():
            print(f"    {n:5d}x  {tmpl}")

    if componentes_globais:
        print(f"\n  Tipos de componente encontrados ({len(componentes_globais)}):")
        for rt, n in componentes_globais.most_common(30):
            print(f"    {n:5d}x  {rt}")
        if len(componentes_globais) > 30:
            print(f"    ... e mais {len(componentes_globais) - 30} tipos (veja o CSV)")

    # Filhos diretos da raiz: é o que responde "o que tem dentro daqui?"
    filhos_diretos = sorted(p for p, m in inventory.items() if m["depth"] == 1)
    if filhos_diretos:
        print(f"\n  Filhos diretos de {caminho} ({len(filhos_diretos)}):")
        for p in filhos_diretos[:30]:
            m = inventory[p]
            tipo = "página" if m["is_page"] else "pasta"
            print(f"    {p.rsplit('/', 1)[-1]:35s} [{tipo}] {m['title']}")
        if len(filhos_diretos) > 30:
            print(f"    ... e mais {len(filhos_diretos) - 30}")

    print(f"\n  CSV: {output}")

    if session_expired(auth_tracker):
        print(f"\n  [aviso] a sessão expirou durante a varredura — o resultado "
              f"está INCOMPLETO.", file=sys.stderr)
        print(f"  Pegue um cookie novo e rode de novo.", file=sys.stderr)


if __name__ == "__main__":
    main()
