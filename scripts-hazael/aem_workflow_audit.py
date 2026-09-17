#!/usr/bin/env python3
"""
Procura workflows do AEM por payload. SOMENTE LEITURA.

PARA QUE SERVE
Quando o editor mostra "This page is subject to the workflow X" e o
'View details' abre vazio, a pergunta é: existe mesmo um workflow vivo
nessa página, ou é resíduo? Este script responde com dado.

DOIS ACHADOS QUE MOTIVARAM ISTO (17/09/2026)
1. GET /var/workflow/instances.json devolve 200 com ZERO filhos para
   usuário não-admin — parece vazio e não está. Só o QueryBuilder
   enxerga: eram 16.898 instâncias, 3.121 delas RUNNING, algumas presas
   desde jan/2024. Nunca conclua "não há workflow" a partir do GET.
2. O campo 'payload' é PROPRIEDADE do nó da instância, mas o
   p.properties do QueryBuilder devolve None para ele; é preciso ler a
   instância direto (.3.json) ou filtrar com property.operation=like.

Um workflow disparado sobre várias páginas de uma vez tem como payload
um PACOTE (/var/workflow/packages/...), não a página — por isso o
--pacotes, que procura o caminho dentro dos filtros dos pacotes.

COMO RODAR
  # workflows vivos citando um caminho
  python3 aem_workflow_audit.py --caminho /content/macnicaglobal2/.../tq-systems

  # panorama: quantos RUNNING, por modelo
  python3 aem_workflow_audit.py --panorama

  # procurar também nos pacotes
  python3 aem_workflow_audit.py --caminho /content/... --pacotes
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin, quote
from aem_lib import CONFIG, build_session, get_json, print_header


def qb(session, base, params, timeout=60):
    url = "/bin/querybuilder.json?" + "&".join(params)
    try:
        return session.get(urljoin(base, url), timeout=timeout).json()
    except Exception as e:
        print(f"  [erro] querybuilder: {e}", file=sys.stderr)
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--caminho", default=None, help="Caminho de conteúdo a procurar.")
    ap.add_argument("--panorama", action="store_true", help="Resumo dos RUNNING por modelo.")
    ap.add_argument("--pacotes", action="store_true", help="Procurar também nos pacotes.")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    if not args.caminho and not args.panorama:
        ap.error("informe --caminho ou --panorama")

    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    if args.panorama:
        print_header("PANORAMA DE WORKFLOWS")
        d = qb(s, base, ["path=/var/workflow/instances", "type=cq:Workflow",
                         "1_property=status", "1_property.value=RUNNING",
                         "p.limit=400", "p.hits=selective",
                         "p.properties=jcr%3apath%20modelId%20initiator"])
        hits = d.get("hits", [])
        print(f"  instâncias RUNNING (total no índice): {d.get('total')}")
        print(f"  amostradas: {len(hits)}\n")
        modelos, quem = Counter(), Counter()
        for h in hits:
            modelos[str(h.get("modelId", "?")).rsplit("/", 1)[-1]] += 1
            quem[h.get("initiator", "?")] += 1
        print("  por modelo:")
        for m, n in modelos.most_common(12):
            print(f"    {n:5d}x  {m}")
        print("\n  por autor:")
        for q, n in quem.most_common(8):
            print(f"    {n:5d}x  {q}")

    if args.caminho:
        alvo = args.caminho.rstrip("/")
        print_header(f"WORKFLOWS CITANDO {alvo}")
        d = qb(s, base, ["path=/var/workflow/instances", "type=cq:Workflow",
                         "1_property=payload", "1_property.operation=like",
                         f"1_property.value={quote('%' + alvo + '%', safe='')}",
                         "p.limit=50", "p.hits=selective",
                         "p.properties=jcr%3apath%20payload%20model%20state%20initiator"])
        hits = d.get("hits", [])
        print(f"  instâncias com esse payload: {d.get('total')}")
        for h in hits[:20]:
            print(f"    {h.get('jcr:path')}")
            print(f"       state={h.get('state')} model={h.get('model')}")
            print(f"       initiator={h.get('initiator')}")
        if not hits:
            print("    nenhuma — o banner no editor, se houver, é resíduo de UI.")

        if args.pacotes:
            print("\n  --- pacotes cujo filtro cita o caminho ---")
            for raiz in ("/var/workflow/packages", "/etc/workflow/packages"):
                dp = qb(s, base, [f"path={raiz}", "1_property=root",
                                  "1_property.operation=like",
                                  f"1_property.value={quote('%' + alvo + '%', safe='')}",
                                  "p.limit=30", "p.hits=selective",
                                  "p.properties=jcr%3apath%20root"])
                print(f"    {raiz}: total={dp.get('total')}")
                for h in dp.get("hits", [])[:8]:
                    print(f"       {h.get('jcr:path')}")


if __name__ == "__main__":
    main()
