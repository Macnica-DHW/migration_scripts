#!/usr/bin/env python3
"""
Detecta e remove o marcador de SOFT-DELETE do AEM (deleted/deletedBy).

O PROBLEMA QUE ISTO RESOLVE (achado em 17/09/2026)
O fluxo "Request for Page Deletion" do AEM NÃO apaga a página: grava
'deleted' e 'deletedBy' em jcr:content. O console Sites filtra qualquer
página com essa propriedade — então ela some da árvore mas continua no
JCR, ocupando o nome. Os sintomas são sempre os mesmos quatro:

  1. a página sumiu do console;
  2. não dá para criar outra com o mesmo nome (o AEM sufixa: nome0,
     nome1, nome2...), porque o nó nunca saiu do lugar;
  3. "restore" não faz nada — não há o que restaurar, a página está lá;
  4. o editor mostra o banner "subject to the workflow Request for Page
     Deletion", às vezes sem workflow vivo nenhum (instância expurgada).

O marcador fica em CADA página da subárvore, não só na raiz: em
tq-systems eram 144. Limpar só a raiz faz a página reaparecer, mas os
filhos continuam invisíveis.

SEGURANÇA
Escrita fora de copia-teste exige --permitir-escrita-global2 com o
caminho EXATO de --raiz, mesma convenção do aem_migrate.py. Sem isso,
assert_target_is_safe() aborta.

REVERSÍVEL: para desfazer, regrave 'deleted' (data) e 'deletedBy'
(usuário) — o relatório guarda os valores originais no CSV.

COMO RODAR
  # 1. diagnosticar (não escreve)
  python3 aem_soft_delete.py --raiz /content/copia-teste/.../familia

  # 2. limpar de verdade
  python3 aem_soft_delete.py --raiz /content/copia-teste/.../familia --executar

  # 3. em macnicaglobal2, exceção pontual e explícita
  python3 aem_soft_delete.py \
    --raiz /content/macnicaglobal2/.../tq-systems --executar \
    --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, build_session, crawl_tree, get_json, post_node,
                     print_header, session_expired, write_csv)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", required=True, help="Subárvore a varrer.")
    ap.add_argument("--executar", action="store_true",
                    help="Escreve. Sem isto, só diagnostica (padrão seguro).")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO",
                    help="Libera escrita em macnicaglobal2 SÓ neste caminho, "
                         "que precisa ser idêntico a --raiz.")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    raiz = args.raiz.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != raiz:
            print(f"[erro] --permitir-escrita-global2 não bate com --raiz:\n"
                  f"  liberado: {lib}\n  raiz:     {raiz}", file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"soft_delete_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("SOFT-DELETE (deleted / deletedBy)")
    print(f"  raiz: {raiz}")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico (nada será escrito)'}")
    if allow:
        print(f"  *** escrita em macnicaglobal2 liberada para {allow[0]} ***")
    print()

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas na subárvore\n")

    marcadas = []
    for p in paginas:
        jc, _ = get_json(s, urljoin(base, f"{p}/_jcr_content.json"), at)
        jc = jc or {}
        if jc.get("deleted"):
            marcadas.append((p, str(jc.get("deleted")), str(jc.get("deletedBy", ""))))

    print(f"  com marcador: {len(marcadas)}")
    for p, q, quem in marcadas[:10]:
        print(f"    {p.rsplit('/', 1)[-1]:<48} {q[:24]}  {quem}")
    if len(marcadas) > 10:
        print(f"    ... e mais {len(marcadas) - 10}")

    linhas = [{"pagina": p, "deleted": q, "deletedBy": quem,
               "acao": "pendente" if not args.executar else ""} for p, q, quem in marcadas]

    if not args.executar:
        write_csv(saida, ["pagina", "deleted", "deletedBy", "acao"], linhas)
        print(f"\n  Nada foi escrito. Rode com --executar para limpar.")
        print(f"  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, _, _) in enumerate(marcadas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(marcadas)}", file=sys.stderr)
            break
        st, corpo = post_node(s, base, f"{p}/jcr:content",
                              {"deleted@Delete": "", "deletedBy@Delete": ""},
                              at, allow_extra=allow)
        if st in (200, 201):
            ok += 1
            linhas[i - 1]["acao"] = "limpo"
        else:
            falhas += 1
            linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p} :: {corpo[:90]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(marcadas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "deleted", "deletedBy", "acao"], linhas)
    print(f"\n  limpos: {ok}   falhas: {falhas}")
    print(f"  CSV (guarda os valores originais, para desfazer): {saida}")


if __name__ == "__main__":
    main()
