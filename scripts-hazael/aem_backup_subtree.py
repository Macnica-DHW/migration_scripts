#!/usr/bin/env python3
"""
Cópia de segurança FIEL de uma subárvore de páginas.

PARA QUE SERVE
Guardar o estado de uma família antes de alguém mexer. Diferente do
aem_clone_subtree.py, que existe para SUBSTITUIR conteúdo em um destino
já povoado, este é para criar uma cópia intacta em lugar novo.

POR QUE NÃO USA O copyPage DO AEM
O caminho natural seria /bin/wcmcommand cmd=copyPage — cópia nativa,
profunda, uma requisição só. Não funciona daqui, e a razão importa
(descoberta em 17/09/2026):

    cq:allowedTemplates está definido em /content/macnicaglobal2
        -> /conf/macnicaglobal2/settings/wcm/templates/(?!xf-).*
    e NÃO existe em lugar nenhum de /content/copia-teste.

O copyPage VALIDA o template contra essa lista e recusa:
"(Macnica Americas Product Page) not allowed below /content/copia-teste/...".
Já o Sling POST grava `cq:template` como propriedade comum e não passa por
essa validação — que é, aliás, como as páginas de copia-teste nasceram.
Então a cópia aqui é feita página a página, via POST, igual à migração.

O QUE PRESERVA, E O QUE LIMPA
Usa build_clone_payload() do aem_lib, que mantém tudo menos uuid,
versionamento e datas de replicação.

**O marcador soft-delete (`deleted`/`deletedBy`) é REMOVIDO.** Backup existe
para ser restaurado, e página com esse marcador não aparece no console —
copiá-lo produziria uma rede de segurança inútil, com as 29 órfãs de
tq-systems invisíveis também na cópia. Decisão do time em 17/09/2026,
corrigindo a primeira versão deste script, que preservava por "fidelidade".

Pelo mesmo motivo a cópia não entra em workflow nenhum: workflow tem como
payload um CAMINHO, e o backup fica em caminho novo. Nada a fazer.

Quem quiser cópia arqueológica, fiel ao estado quebrado, usa
--preservar-marcadores.

SEGURANÇA
Recusa se o destino já existir — backup não sobrescreve nada. Escrita
passa pelo assert_target_is_safe() como todo o resto.

COMO RODAR
  python3 aem_backup_subtree.py \
    --origem  /content/macnicaglobal2/.../tq-systems \
    --destino /content/copia-teste/.../tq-systems-backup
  # depois de conferir:
  python3 aem_backup_subtree.py --origem ... --destino ... --executar
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, build_clone_payload, build_session, crawl_tree,
                     fetch_with_depth_fallback, get_json, post_node, print_header,
                     session_expired, write_csv)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--profundidade", type=int, default=20)
    ap.add_argument("--preservar-marcadores", action="store_true",
                    help="Mantém deleted/deletedBy na cópia (padrão é limpar, "
                         "para o backup ser restaurável).")
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

    saida = args.output or f"backup_{dst.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("BACKUP DE SUBÁRVORE (cópia fiel)")
    print(f"  origem : {org}")
    print(f"  destino: {dst}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    ja, _ = get_json(s, urljoin(base, dst + ".json"), at)
    if ja is not None:
        print(f"[abortado] o destino já existe: {dst}\n"
              f"  Backup não sobrescreve. Escolha outro nome ou apague antes.",
              file=sys.stderr)
        sys.exit(1)

    inv = crawl_tree(s, base, org, at, quiet=True)
    paginas = sorted((p for p, m in inv.items() if m["is_page"]),
                     key=lambda x: (x.count("/"), x))
    marcadas = sum(1 for p in paginas if inv[p].get("has_content") is not None)
    marc = "PRESERVADOS (--preservar-marcadores)" if args.preservar_marcadores \
        else "removidos, para o backup ser restaurável"
    print(f"  soft-delete: {marc}")
    print(f"  páginas a copiar: {len(paginas)}")
    print(f"  (pais primeiro, para o filho sempre ter onde entrar)\n")

    if not args.executar:
        for p in paginas[:8]:
            print(f"   [simulado] {p[len(org):] or '/'}")
        print(f"   ... e mais {max(0, len(paginas)-8)}")
        print(f"\n  Nada escrito. Use --executar.")
        return

    linhas, ok, falhas = [], 0, 0
    for i, p in enumerate(paginas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(paginas)}", file=sys.stderr)
            break
        rel = p[len(org):].lstrip("/")
        alvo = f"{dst}/{rel}" if rel else dst
        d, st = fetch_with_depth_fallback(s, base, p, args.profundidade, at)
        if d is None:
            falhas += 1
            linhas.append({"origem": p, "destino": alvo, "acao": f"origem ilegível ({st})"})
            continue
        payload = build_clone_payload(d)
        if not args.preservar_marcadores:
            payload["jcr:content/deleted@Delete"] = ""
            payload["jcr:content/deletedBy@Delete"] = ""
        stp, corpo = post_node(s, base, alvo, payload, at, allow_extra=allow)
        if stp in (200, 201):
            ok += 1
            linhas.append({"origem": p, "destino": alvo, "acao": "copiada"})
        else:
            falhas += 1
            linhas.append({"origem": p, "destino": alvo, "acao": f"FALHA {stp}"})
            print(f"  [FALHA {stp}] {alvo} :: {corpo[:80]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(paginas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["origem", "destino", "acao"], linhas)
    print(f"\n  copiadas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
