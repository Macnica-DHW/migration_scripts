#!/usr/bin/env python3
"""
Confere uma migração comparando origem e destino. SOMENTE LEITURA.

Responde, com dado real, três perguntas que só dá para responder DEPOIS
de rodar o migrate:

  1. Faltou alguma página? (existe na origem, não existe no destino)
  2. Sobrou alguma? (existe no destino, não existe na origem — geralmente
     duplicata de maiúscula/minúscula, o problema que já aconteceu no
     TQ Systems)
  3. As páginas criadas têm mesmo conteúdo, ou nasceram vazias?

Também confere o template aplicado e, com --links, procura links que
continuaram apontando para o site antigo (quebram ao publicar).

Não cria, move, altera nem deleta nada.

COMO RODAR:
  # comparação básica
  python3 aem_verify.py --source /content/macnicagwi/.../semiconductors

  # conferindo também os links internos
  python3 aem_verify.py --source /content/macnicagwi/.../semiconductors --links
"""

import argparse
import re
import sys
from collections import Counter

from aem_lib import (
    CONFIG, add_common_args, build_session, crawl_tree, fetch_with_depth_fallback,
    normalize_path, print_header, session_expired, write_csv,
)

LINK_RE = re.compile(r'/content/[A-Za-z0-9_\-./]+')


def coletar_links(node):
    """Junta todo caminho /content/... que aparecer em qualquer valor."""
    achados = set()

    def walk(n):
        if isinstance(n, dict):
            for k, v in n.items():
                if k in ("fileReference", "linkURL") and isinstance(v, str):
                    if v.startswith("/content/"):
                        achados.add(v)
                elif isinstance(v, str) and "/content/" in v:
                    achados.update(LINK_RE.findall(v))
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return achados


def main():
    parser = argparse.ArgumentParser(
        description="Confere uma migração comparando origem e destino (somente leitura)")
    parser.add_argument("--source", required=True, help="Árvore de origem.")
    parser.add_argument("--target", default=None,
                        help="Árvore de destino. Padrão: espelho em copia-teste.")
    add_common_args(parser)
    parser.add_argument("--links", action="store_true",
                        help="Também procura links apontando para o site antigo.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--skip-path-contains", action="append", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    source_root = args.source.rstrip("/")
    if args.target:
        target_root = args.target.rstrip("/")
    else:
        for prefixo in (CONFIG["gwi_prefix"], CONFIG["global2_prefix"]):
            if source_root.startswith(prefixo):
                target_root = CONFIG["target_prefix"] + source_root[len(prefixo):]
                break
        else:
            print(f"[erro] não sei derivar o destino de {source_root}. Passe --target.",
                  file=sys.stderr)
            sys.exit(1)

    skip = args.skip_path_contains if args.skip_path_contains is not None \
        else CONFIG["skip_path_contains"]
    output = args.output or f"verificacao_{source_root.rsplit('/', 1)[-1]}.csv"

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("VERIFICAÇÃO")
    print(f"  Origem:  {source_root}")
    print(f"  Destino: {target_root}\n")

    print(f"== Percorrendo origem ==")
    origem = crawl_tree(session, base_url, source_root, auth_tracker,
                        max_pages=args.max_pages, delay=args.delay,
                        skip_contains=skip, quiet=True)
    print(f"  {len(origem)} nós\n")

    print(f"== Percorrendo destino ==")
    destino = crawl_tree(session, base_url, target_root, auth_tracker,
                         max_pages=args.max_pages, delay=args.delay, quiet=True)
    print(f"  {len(destino)} nós\n")

    if not origem:
        print(f"[erro] origem vazia: {source_root}", file=sys.stderr)
        sys.exit(1)

    # Mapa: para cada página da origem, onde ela DEVERIA estar no destino.
    esperados = {normalize_path(p, source_root, target_root): p for p in origem}

    faltando = [(esp, orig) for esp, orig in esperados.items() if esp not in destino]
    sobrando = [p for p in destino if p not in esperados]
    presentes = [(esp, orig) for esp, orig in esperados.items() if esp in destino]

    vazias = [(esp, orig) for esp, orig in presentes
              if not destino[esp]["has_content"] and origem[orig]["has_content"]]

    templates_destino = Counter(destino[esp]["template"] for esp, _ in presentes
                                if destino[esp]["template"])

    # --- Links (opcional) ---
    links_antigos = []
    if args.links:
        print(f"== Procurando links para o site antigo em {len(presentes)} páginas ==")
        for i, (esp, _) in enumerate(presentes, 1):
            if session_expired(auth_tracker):
                print(f"  [erro] sessão expirou em {i - 1}/{len(presentes)}.",
                      file=sys.stderr)
                break
            data, _ = fetch_with_depth_fallback(session, base_url, esp,
                                                args.source_depth, auth_tracker)
            if data is None:
                continue
            for link in coletar_links(data.get("jcr:content", {}) or {}):
                if link.startswith(CONFIG["gwi_prefix"]):
                    links_antigos.append({"pagina": esp, "link": link})
            if i % 25 == 0:
                print(f"  [{i}/{len(presentes)}] ...", flush=True)
        print()

    # --- CSV ---
    linhas = []
    for esp, orig in sorted(esperados.items()):
        existe = esp in destino
        linhas.append({
            "caminho_origem": orig,
            "caminho_destino": esp,
            "existe_no_destino": "sim" if existe else "NÃO",
            "origem_tem_conteudo": "sim" if origem[orig]["has_content"] else "não",
            "destino_tem_conteudo": ("sim" if existe and destino[esp]["has_content"]
                                     else "não" if existe else ""),
            "template_destino": destino[esp]["template"] if existe else "",
            "titulo": origem[orig]["title"],
        })
    for p in sorted(sobrando):
        linhas.append({
            "caminho_origem": "",
            "caminho_destino": p,
            "existe_no_destino": "sim (SOBRANDO)",
            "origem_tem_conteudo": "",
            "destino_tem_conteudo": "sim" if destino[p]["has_content"] else "não",
            "template_destino": destino[p]["template"] or "",
            "titulo": destino[p]["title"],
        })

    write_csv(output,
              ["caminho_origem", "caminho_destino", "existe_no_destino",
               "origem_tem_conteudo", "destino_tem_conteudo", "template_destino",
               "titulo"],
              linhas)

    if links_antigos:
        write_csv(output.replace(".csv", "_links_antigos.csv"),
                  ["pagina", "link"], links_antigos)

    # --- Resumo ---
    print_header("RESULTADO")
    print(f"  Páginas na origem:      {len(origem)}")
    print(f"  Presentes no destino:   {len(presentes)}")
    print(f"  FALTANDO no destino:    {len(faltando)}")
    print(f"  SOBRANDO no destino:    {len(sobrando)}")
    print(f"  Criadas mas VAZIAS:     {len(vazias)}")

    if templates_destino:
        print(f"\n  Templates no destino:")
        for tmpl, n in templates_destino.most_common():
            print(f"    {n:5d}x  {tmpl}")
        if len(templates_destino) > 1:
            print(f"    [aviso] mais de um template — confira se é esperado.")

    if faltando:
        print(f"\n  --- {len(faltando)} página(s) FALTANDO ---")
        for esp, orig in faltando[:12]:
            print(f"    {orig}\n      deveria estar em: {esp}")
        if len(faltando) > 12:
            print(f"    ... e mais {len(faltando) - 12} (veja o CSV)")

    if sobrando:
        print(f"\n  --- {len(sobrando)} página(s) SOBRANDO no destino ---")
        print(f"      Sem correspondente na origem. Costuma ser duplicata de")
        print(f"      maiúscula/minúscula de uma rodada anterior.")
        for p in sorted(sobrando)[:12]:
            print(f"    {p}")
        if len(sobrando) > 12:
            print(f"    ... e mais {len(sobrando) - 12} (veja o CSV)")

    if vazias:
        print(f"\n  --- {len(vazias)} página(s) criada(s) mas SEM CONTEÚDO ---")
        print(f"      A origem tem conteúdo, o destino não. Rode o migrate sem")
        print(f"      --so-estrutura para popular.")
        for esp, _ in vazias[:12]:
            print(f"    {esp}")
        if len(vazias) > 12:
            print(f"    ... e mais {len(vazias) - 12} (veja o CSV)")

    if args.links:
        if links_antigos:
            paginas_afetadas = len({x["pagina"] for x in links_antigos})
            print(f"\n  --- {len(links_antigos)} link(s) ainda apontando para o GWI ---")
            print(f"      Em {paginas_afetadas} página(s). VÃO QUEBRAR ao publicar.")
            print(f"      {output.replace('.csv', '_links_antigos.csv')}")
            for x in links_antigos[:8]:
                print(f"    {x['link']}")
            if len(links_antigos) > 8:
                print(f"    ... e mais {len(links_antigos) - 8}")
        else:
            print(f"\n  Nenhum link apontando para {CONFIG['gwi_prefix']}. ✓")

    print(f"\n  CSV: {output}")

    if not faltando and not sobrando and not vazias:
        print(f"\n  ✓ Origem e destino batem.")


if __name__ == "__main__":
    main()
