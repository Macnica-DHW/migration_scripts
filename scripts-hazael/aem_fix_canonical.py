#!/usr/bin/env python3
"""
Corrige cq:canonicalUrl para apontar para o próprio caminho da página.

POR QUE ISTO EXISTE
Clonar uma subárvore (aem_migrate.py --modo-clone, ou o
aem_clone_subtree.py daqui) copia o conteúdo fielmente — e
cq:canonicalUrl é conteúdo. Então toda página clonada nasce apontando o
canonical para o CAMINHO DE ORIGEM. Em tq-systems foram 143 páginas
declarando canonical em .../tq-systems-embedded/... depois da cópia.

Para o Google isso diz "a versão boa desta página é a outra" — some do
índice a página que você acabou de publicar. O HANDOFF.md já avisava
(passo 9: "alguns campos — como Canonical URL — mudam de valor porque
dependem do caminho de destino").

Mesma regra do aem_fix_seo_final.py (canonical = o próprio caminho), mas
SÓ mexe em cq:canonicalUrl — não toca em description, tags, business
categories nem manufacturer. Use este quando o problema for só o
canonical; use o aem_fix_seo_final.py quando quiser o pacote de SEO todo.

IDEMPOTENTE: página cujo canonical já bate não é reescrita.

COMO RODAR
  python3 aem_fix_canonical.py --raiz /content/copia-teste/.../familia
  python3 aem_fix_canonical.py --raiz ... --executar
  python3 aem_fix_canonical.py --raiz /content/macnicaglobal2/.../x --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../x
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
            print(f"[erro] --permitir-escrita-global2 não bate com --raiz.", file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"canonical_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("CANONICAL URL")
    print(f"  raiz: {raiz}")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])

    corrigir, ja_ok, ausente = [], 0, []
    for p in paginas:
        jc, _ = get_json(s, urljoin(base, f"{p}/_jcr_content.json"), at)
        atual = (jc or {}).get("cq:canonicalUrl")
        if atual is None:
            ausente.append(p)
        elif atual != p:
            corrigir.append((p, atual))
        else:
            ja_ok += 1

    print(f"  páginas .................. {len(paginas)}")
    print(f"  canonical já correto ..... {ja_ok}")
    print(f"  a corrigir ............... {len(corrigir)}")
    print(f"  sem a propriedade ........ {len(ausente)}")
    for p, atual in corrigir[:5]:
        print(f"\n   {p}\n     de : {atual}\n     pra: {p}")

    linhas = [{"pagina": p, "canonical_antigo": a, "canonical_novo": p,
               "acao": "pendente" if not args.executar else ""} for p, a in corrigir]

    if not args.executar:
        write_csv(saida, ["pagina", "canonical_antigo", "canonical_novo", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, _) in enumerate(corrigir, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(corrigir)}", file=sys.stderr)
            break
        st, corpo = post_node(s, base, f"{p}/jcr:content",
                              {"cq:canonicalUrl": p}, at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "corrigido"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p} :: {corpo[:90]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(corrigir)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "canonical_antigo", "canonical_novo", "acao"], linhas)
    print(f"\n  corrigidas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
