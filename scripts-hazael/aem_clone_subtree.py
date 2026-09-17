#!/usr/bin/env python3
"""
Copia o conteúdo de uma subárvore para outra, SUBSTITUINDO o destino.

DIFERENÇA PARA O aem_migrate.py --modo-clone
O migrate clona criando páginas novas. Este script serve para quando o
destino JÁ EXISTE e tem conteúdo velho que precisa sair. Caso real
(17/09/2026): tq-systems tinha a versão pré-correção das 144 páginas e
tq-systems-embedded tinha a versão boa; era preciso passar o conteúdo de
embedded para tq-systems, sem duplicar nada.

POR QUE APAGAR jcr:content/root ANTES DE GRAVAR
O Sling POST faz MERGE, não substituição. Gravar o container novo por
cima de uma página que já tem container velho deixa OS DOIS — a página
renderiza o conteúdo antigo e o novo empilhados. Então, por página:

   1. POST jcr:content/root  :operation=delete   (tira o conteúdo velho)
   2. POST <pagina>          payload clonado     (grava o novo)

O payload vem do build_clone_payload() do aem_lib, que já exclui
páginas-filhas (elas têm a sua própria vez) e metadado de versão/uuid.
De quebra, remove o marcador soft-delete (ver aem_soft_delete.py).

ATENÇÃO — O QUE ELE NÃO FAZ
- Não renomeia nada: se origem e destino divergem no nome do nó
  (maiúsculas, por exemplo), a página é CRIADA com o nome da origem e a
  antiga fica para trás, órfã. Em tq-systems isso gerou 29 duplicatas
  ('TQMa8MPxL-...' x 'tqma8mpxl-...'). O relatório final lista as
  páginas do destino sem par na origem — confira antes de dar por pronto.
- Não corrige cq:canonicalUrl, que sai apontando para a ORIGEM. Rode o
  aem_fix_canonical.py depois. Sempre.

COMO RODAR
  python3 aem_clone_subtree.py --origem /content/.../boa --destino /content/.../alvo
  python3 aem_clone_subtree.py --origem ... --destino ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../alvo
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, build_clone_payload, build_session, crawl_tree,
                     delete_node, fetch_with_depth_fallback, get_json, post_node,
                     print_header, session_expired, write_csv)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--profundidade", type=int, default=20)
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    org, dst = args.origem.rstrip("/"), args.destino.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != dst:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --destino.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"clone_{dst.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("CLONE DE SUBÁRVORE (substitui o destino)")
    print(f"  origem : {org}  (somente leitura)")
    print(f"  destino: {dst}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv_o = crawl_tree(s, base, org, at, quiet=True)
    inv_d = crawl_tree(s, base, dst, at, quiet=True)
    src = sorted((p for p, m in inv_o.items() if m["is_page"]),
                 key=lambda x: (x.count("/"), x))
    dst_pgs = {p for p, m in inv_d.items() if m["is_page"]}
    rels = [p[len(org):].lstrip("/") for p in src]
    novos = [r for r in rels if (f"{dst}/{r}" if r else dst) not in dst_pgs]
    orfas = sorted(p for p in dst_pgs if (org + p[len(dst):]) not in set(src))

    print(f"  páginas na origem ........ {len(rels)}")
    print(f"  páginas no destino ....... {len(dst_pgs)}")
    print(f"  serão criadas ............ {len(novos)}")
    print(f"  órfãs no destino ......... {len(orfas)} (NÃO serão tocadas)")
    for o in orfas[:6]:
        print(f"     - {o.rsplit('/', 1)[-1]}")
    if len(orfas) > 6:
        print(f"     ... e mais {len(orfas) - 6}")

    if not args.executar:
        print(f"\n  Nada escrito. Use --executar.")
        return

    linhas, ok, falhas = [], 0, 0
    for i, rel in enumerate(rels, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(rels)}", file=sys.stderr)
            break
        s_path = f"{org}/{rel}" if rel else org
        d_path = f"{dst}/{rel}" if rel else dst
        d, st = fetch_with_depth_fallback(s, base, s_path, args.profundidade, at)
        if d is None:
            falhas += 1
            linhas.append({"pagina": d_path, "acao": f"origem ilegível ({st})"})
            continue
        payload = build_clone_payload(d)
        payload["jcr:content/deleted@Delete"] = ""
        payload["jcr:content/deletedBy@Delete"] = ""

        existe, _ = get_json(s, urljoin(base, f"{d_path}/_jcr_content.json"), at)
        if existe is not None:
            raiz_atual, _ = get_json(s, urljoin(base, f"{d_path}/jcr:content/root.json"), at)
            if raiz_atual is not None:
                std, _ = delete_node(s, base, f"{d_path}/jcr:content/root", at,
                                     allow_extra=allow)
                if std not in (200, 204):
                    falhas += 1
                    linhas.append({"pagina": d_path, "acao": f"falha ao limpar root ({std})"})
                    continue
        stp, corpo = post_node(s, base, d_path, payload, at, allow_extra=allow)
        if stp in (200, 201):
            ok += 1
            linhas.append({"pagina": d_path, "acao": "criada" if rel in novos else "substituída"})
        else:
            falhas += 1
            linhas.append({"pagina": d_path, "acao": f"FALHA {stp}"})
            print(f"  [FALHA {stp}] {d_path} :: {corpo[:90]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(rels)}] ok={ok} falhas={falhas}", flush=True)

    for o in orfas:
        linhas.append({"pagina": o, "acao": "ÓRFÃ no destino (sem par na origem)"})
    write_csv(saida, ["pagina", "acao"], linhas)
    print(f"\n  copiadas: {ok}   falhas: {falhas}   órfãs: {len(orfas)}")
    print(f"  CSV: {saida}")
    print(f"\n  >>> Rode agora o aem_fix_canonical.py --raiz {dst}")


if __name__ == "__main__":
    main()
