#!/usr/bin/env python3
"""
Remove 'text-align: center' injetado nas tabelas do GLOBAL2.

POR QUE ISTO É DANO, E NÃO DECISÃO DE DESIGN
Varredura de 17/09/2026 nas duas árvores de tq-systems:

    GWI     : 251 tabelas -> 0 ocorrências de text-align:center
    DESTINO : 253 tabelas -> 88 ocorrências, em apenas 5 páginas

Ou seja: a origem não centraliza nada e 168 das 173 páginas do destino
também não. As 5 restantes destoam. Centralizar o texto dentro de uma
célula larga joga o marcador da lista para longe do texto e estica a
altura da linha — é exatamente o que se vê comparando a mesma tabela de
Specifications nos dois lados.

O QUE FAZ
Tira só a declaração 'text-align: center' de dentro do atributo style,
onde ela aparecer (td, p, li). Se o style ficar vazio, o atributo
inteiro sai. Nada mais é tocado: conteúdo, larguras, outras
declarações de style e as demais tabelas ficam como estão.

Alinhamento à esquerda é o padrão do CSS, então não é preciso escrever
'text-align:left' — basta remover.

IDEMPOTENTE: tabela sem centralização é pulada.

COMO RODAR
  python3 aem_corrigir_alinhamento.py --raiz /content/macnicaglobal2/.../tq-systems
  python3 aem_corrigir_alinhamento.py --raiz ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     list_child_nodes, post_node, print_header, session_expired,
                     write_csv)

CENTER_RE = re.compile(r"text-align\s*:\s*center\s*;?", re.I)
STYLE_VAZIO_RE = re.compile(r'\s*style\s*=\s*"\s*"', re.I)


def limpar(html):
    """Tira text-align:center; e o style que sobrar vazio."""
    novo = CENTER_RE.sub("", html)
    novo = STYLE_VAZIO_RE.sub("", novo)
    return novo


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    raiz = args.raiz.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != raiz:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --raiz.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"alinhamento_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("REMOVER text-align:center DAS TABELAS")
    print(f"  raiz: {raiz}")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, tarefas = [], []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 10, at)
        if dd is None:
            continue
        jcr = (dd or {}).get("jcr:content", {}) or {}
        if jcr.get("deleted"):
            continue

        def walk(node, caminho):
            for nome, ch in list_child_nodes(node):
                sub = f"{caminho}/{nome}"
                if (ch.get("sling:resourceType") or "").endswith("/table"):
                    html = ch.get("text") or ""
                    n = len(CENTER_RE.findall(html))
                    if n:
                        tarefas.append((p, sub.lstrip("/"), limpar(html)))
                        linhas.append({"pagina": p, "tabela": sub.lstrip("/"),
                                       "ocorrencias": n, "acao": "pendente"})
                walk(ch, sub)

        walk(jcr, "jcr:content")

    total = sum(l["ocorrencias"] for l in linhas)
    print(f"  tabelas a corrigir: {len(tarefas)}   ocorrências: {total}\n")
    for l in linhas:
        print(f"   {l['pagina'].rsplit('/', 1)[-1][:50]:<52} {l['ocorrencias']:>4}x  "
              f"{l['tabela'].rsplit('/', 1)[-1]}")

    if not args.executar:
        write_csv(saida, ["pagina", "tabela", "ocorrencias", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, rel, novo) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        st, corpo = post_node(s, base, f"{p}/{rel}",
                              {"text": novo, "textIsRich": "true"},
                              at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "corrigido"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p} :: {corpo[:70]}")

    write_csv(saida, ["pagina", "tabela", "ocorrencias", "acao"], linhas)
    print(f"\n  corrigidas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
