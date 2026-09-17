#!/usr/bin/env python3
"""
Troca sling:resourceType de 'macnicaglobal2/components/page' (genérico)
para 'macnicaglobal2/components/maeproductpage' (específico de produto)
em toda página-filha/neta de uma árvore. Não mexe em mais NADA — só
essa propriedade.

Achado com o Bruno em 16/09/2026: a aba "Product Hierarchy Details" (e
"Product Details") do Page Properties só aparece em páginas com
resourceType 'maeproductpage' — esse componente herda de 'page'
(sling:resourceSuperType) e só adiciona um cq:dialog extra, sem HTL de
renderização próprio. Trocar a propriedade não recria nada, não muda
template, não afeta conteúdo — testado em
copia-teste/.../tq-embedded-power-modules (5 páginas) antes de aplicar
em escala: HTML continuou idêntico, só a aba passou a aparecer.

Achado mais amplo: só a página RAIZ de cada família de produto (ex:
tq-systems) veio como maeproductpage — todas as filhas/netas vieram
como 'page' genérico desde a criação original, sistemático em toda a
migração (confirmado também em semiconductors), não é bug desta rodada.

SEGURANÇA: escreve em copia-teste normalmente. Para macnicaglobal2,
precisa de --permitir-escrita-global2 com o --target exato (mesma
trava pontual do aem_migrate.py).

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_resourcetype_maeproductpage.py --target /content/copia-teste/.../tq-systems --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_resourcetype_maeproductpage.py --target /content/copia-teste/.../tq-systems

  # Em macnicaglobal2, com a exceção pontual:
  python3 aem_fix_resourcetype_maeproductpage.py \\
      --target /content/macnicaglobal2/.../tq-systems-embedded \\
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems-embedded
"""

import argparse
import sys

from aem_lib import (
    CONFIG, add_common_args, assert_target_is_safe, build_session, crawl_tree,
    fetch_with_depth_fallback, post_node, print_header, session_expired,
    write_csv,
)

RT_GENERICO = "macnicaglobal2/components/page"
RT_ALVO = "macnicaglobal2/components/maeproductpage"


def main():
    parser = argparse.ArgumentParser(
        description="Troca sling:resourceType de 'page' para 'maeproductpage' "
                    "em toda a árvore, para expor a aba Product Hierarchy Details")
    parser.add_argument("--target", required=True)
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO",
                        help="Exceção pontual à trava de macnicaglobal2 — precisa "
                             "bater exatamente com --target.")
    parser.add_argument("--output", default="fix_resourcetype_maeproductpage.csv")
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
        # Sem a exceção, confia na trava padrão (só copia-teste) —
        # falha cedo e claro se o alvo for macnicaglobal2 sem permissão.
        assert_target_is_safe(target_root)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("TROCA sling:resourceType -> maeproductpage")
    print(f"  Destino: {target_root}")
    print(f"  {RT_GENERICO} -> {RT_ALVO}")
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

        linha = {"pagina": path, "resourceType_antes": "", "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path, 2, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        rt_atual = jcr.get("sling:resourceType")
        linha["resourceType_antes"] = rt_atual or ""

        if rt_atual == RT_ALVO:
            linha["status"] = "OK (já correto)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        if rt_atual != RT_GENERICO:
            linha["status"] = f"PULADO (resourceType inesperado: {rt_atual})"
            resultados.append(linha)
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        if args.dry_run:
            linha["status"] = "DRY-RUN"
        else:
            payload = {"jcr:content/sling:resourceType": RT_ALVO}
            st, resposta = post_node(session, base_url, path, payload, auth_tracker,
                                     allow_extra=allow_extra)
            if st not in (200, 201):
                linha["status"] = f"ERRO ao escrever ({st}): {resposta[:120]}"
                resultados.append(linha)
                continue
            linha["status"] = "OK"

        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output, ["pagina", "resourceType_antes", "status"], resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN", "OK (já correto)"))
    erros = [r for r in resultados if "ERRO" in r["status"]]
    pulados = [r for r in resultados if "PULADO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}")
    print(f"    ok:                {ok}")
    print(f"    trocadas:          {sum(1 for r in resultados if r['status'] in ('OK','DRY-RUN'))}")
    print(f"    já corretas:       {sum(1 for r in resultados if r['status']=='OK (já correto)')}")
    print(f"    puladas (tipo inesperado): {len(pulados)}")
    print(f"    erros:             {len(erros)}")

    if pulados:
        print(f"\n  --- {len(pulados)} página(s) com resourceType inesperado ---")
        for r in pulados[:10]:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}: {r['resourceType_antes']}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
