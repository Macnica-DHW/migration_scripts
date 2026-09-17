#!/usr/bin/env python3
"""
Padroniza o Text with Image do topo pelo design de referência.

A REFERÊNCIA
/content/macnicaglobal2/.../tq-systems-embedded/tq-embedded-qoriqr-layerscape/
tqmls1088a-embedded-octal-cortex — página montada como exemplo da migração.

O QUE DIFERE, E O QUE CADA COISA SIGNIFICA
Os styleIds saem da policy do componente
(/conf/macnicaglobal2/settings/wcm/policies/.../textwithimage/policy_1718154236394),
onde têm nome:

    1718154328384  【Image Position】     Left
    1783061491236  【Vertical Alignment】 Center
    1783061500464  【Vertical Alignment】 Bottom
    1718154382437  【Text Wrapping】      Wrap

    referência : cq:styleIds = ['1718154328384']                  (só Left)
    demais     : cq:styleIds = ['1718154328384','1783061491236']  (Left + Center)

    referência : imageRatio = '40'   (imagem 40% / texto 60%)
    demais     : imageRatio ausente  (cai no padrão do componente)

    referência : spImage/fileReference preenchido com a MESMA imagem
    demais     : nó spImage existe mas sem fileReference

O 'spImage' é a variante para telas pequenas. Sem fileReference ele fica
sem imagem no celular — por isso recebe a mesma do componente, como na
referência.

O QUE ESCREVE (só no primeiro textwithimage de cada página)
    cq:styleIds          = ['1718154328384']        (String[])
    imageRatio           = '40'
    spImage/fileReference = o fileReference do próprio componente

NÃO TOCA em text, alt, fileReference principal, links ou qualquer outro
componente da página.

Página cujo textwithimage não tem fileReference recebe styleIds e
imageRatio, mas NÃO ganha spImage — não há imagem para apontar. Sai
reportada no CSV.

IDEMPOTENTE: página já igual à referência é pulada.

COMO RODAR
  python3 aem_padronizar_textwithimage.py --raiz /content/macnicaglobal2/.../tq-systems
  python3 aem_padronizar_textwithimage.py --raiz ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     list_child_nodes, post_node, print_header, session_expired,
                     write_csv)

ESTILO_REF = ["1718154328384"]      # só 【Image Position】 Left
RATIO_REF = "40"
IMAGE_RT = "macnicaglobal2/components/content/image"


def achar_topo(jcr):
    """(caminho_rel, nó) do PRIMEIRO textwithimage, em ordem de documento."""
    cont = ((jcr.get("root") or {}).get("container") or {})
    for nome, wrap in list_child_nodes(cont):
        for n2, comp in list_child_nodes(wrap):
            if (comp.get("sling:resourceType") or "").endswith("/textwithimage"):
                return f"jcr:content/root/container/{nome}/{n2}", comp
    return None, None


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

    saida = args.output or f"twi_padrao_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("PADRONIZAR TEXT WITH IMAGE (pelo design de referência)")
    print(f"  raiz: {raiz}")
    print(f"  alvo: cq:styleIds={ESTILO_REF}  imageRatio={RATIO_REF}  spImage=mesma imagem")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, tarefas, sem_twi, sem_img = [], [], 0, []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 8, at)
        if dd is None:
            continue
        jcr = (dd or {}).get("jcr:content", {}) or {}
        if jcr.get("deleted"):
            continue
        rel, comp = achar_topo(jcr)
        if comp is None:
            sem_twi += 1
            continue

        estilos = comp.get("cq:styleIds")
        estilos = list(estilos) if isinstance(estilos, list) else \
            ([estilos] if estilos else [])
        ratio = str(comp.get("imageRatio") or "")
        fref = comp.get("fileReference")
        sp = comp.get("spImage") if isinstance(comp.get("spImage"), dict) else {}
        sp_ref = sp.get("fileReference")

        muda = []
        if estilos != ESTILO_REF:
            muda.append(f"styleIds {estilos} -> {ESTILO_REF}")
        if ratio != RATIO_REF:
            muda.append(f"imageRatio {ratio or '(ausente)'} -> {RATIO_REF}")
        if fref and sp_ref != fref:
            muda.append(f"spImage {'(vazio)' if not sp_ref else 'difere'} -> imagem do componente")
        if not fref:
            sem_img.append(p.rsplit("/", 1)[-1])
        if not muda:
            continue

        tarefas.append((p, rel, fref))
        linhas.append({"pagina": p, "componente": rel.rsplit("/", 2)[-2] + "/" +
                       rel.rsplit("/", 1)[-1],
                       "mudancas": " | ".join(muda),
                       "imagem": (fref or "(sem imagem)").rsplit("/", 1)[-1],
                       "acao": "pendente"})

    print(f"  páginas sem textwithimage (ignoradas) : {sem_twi}")
    print(f"  páginas a padronizar                  : {len(tarefas)}")
    if sem_img:
        print(f"  [aviso] sem fileReference (não ganham spImage): {len(sem_img)}")
        for n in sem_img[:8]:
            print(f"     {n}")
    print()
    for l in linhas[:40]:
        print(f"   {l['pagina'].rsplit('/', 1)[-1][:44]:<46} {l['mudancas'][:88]}")
    if len(linhas) > 40:
        print(f"   ... e mais {len(linhas) - 40}")

    if not args.executar:
        write_csv(saida, ["pagina", "componente", "mudancas", "imagem", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, rel, fref) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        payload = {
            "cq:styleIds": ESTILO_REF,
            "cq:styleIds@TypeHint": "String[]",
            "imageRatio": RATIO_REF,
        }
        if fref:
            payload["spImage/jcr:primaryType"] = "nt:unstructured"
            payload["spImage/sling:resourceType"] = IMAGE_RT
            payload["spImage/fileReference"] = fref
        st, corpo = post_node(s, base, f"{p}/{rel}", payload, at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "padronizado"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p} :: {corpo[:70]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(tarefas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "componente", "mudancas", "imagem", "acao"], linhas)
    print(f"\n  padronizadas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
