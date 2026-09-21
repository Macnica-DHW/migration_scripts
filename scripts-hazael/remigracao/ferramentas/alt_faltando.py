#!/usr/bin/env python3
"""
alt_faltando.py — preenche o `alt` que falta em textwithimage e image (R49).

Por que existe: o diálogo dos dois componentes herda a aba Metadata do core
image v2, onde "Alternative Text" (`./alt`) é OBRIGATÓRIO. O motor gravava
`alt=""`, o JCR não guarda string vazia, e o autor não consegue salvar o
diálogo (Hazael, 21/09/2026, tentando pôr 36% nos textwithimage). 69 nós em
41 páginas. O GWI também não tinha alt, e o DAM não serve: dos 68 assets, 48
não têm dc:title e os 20 que têm trazem nome de arquivo ou id de banco
("1129543888", "IP00C755 - 1").

De onde sai o texto — sempre do que a própria página já diz, nesta ordem:
  textwithimage:  o <hN> do próprio texto da dupla
                  › o último `title` acima, na ordem do documento
                  › o título da página
  image:          o último `title` acima › o título da página
Nunca a primeira frase de uma lista de features ("Built on TSMC's 55 nm…"
não é alt). Nunca `isDecorative` — foto de produto não é decoração.

Escreve SÓ a propriedade `alt` e SÓ onde ela está vazia. Idempotente.

    python3 alt_faltando.py /altera/altera-max-10        # dry-run (padrão)
    python3 alt_faltando.py --todas                       # varre a árvore
    python3 alt_faltando.py --todas --executar
"""
import argparse
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))

from aem_lib import CONFIG, build_session, get_json, post_node

RAIZ_DESTINO = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
ALVOS = ("textwithimage", "image")


def texto(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v or ""))).strip()


def heading_do_texto(html):
    m = re.search(r"<h[1-6][^>]*>(.*?)</h[1-6]>", str(html or ""), re.S)
    return texto(m.group(1)) if m else ""


def em_ordem(no, caminho, saida):
    """(caminho, resourceType, nó) em ordem de documento."""
    for k, v in no.items():
        if not isinstance(v, dict) or k == "cq:responsive":
            continue
        rt = str(v.get("sling:resourceType", "")).split("/")[-1]
        saida.append((f"{caminho}/{k}", rt, v))
        em_ordem(v, f"{caminho}/{k}", saida)
    return saida


def plano_da_pagina(jcr):
    """[(caminho relativo a jcr:content, alt novo, fonte)] para os nós sem alt."""
    titulo_pagina = texto(jcr.get("jcr:title")) or texto(jcr.get("pageTitle"))
    plano = []
    ultimo_titulo = ""
    for caminho, rt, no in em_ordem(jcr.get("root", {}), "root", []):
        if rt == "title" and texto(no.get("jcr:title")):
            ultimo_titulo = texto(no.get("jcr:title"))
        if rt not in ALVOS:
            continue
        # Sem `altValueFromDAM=false` o componente assume o checkbox LIGADO
        # (default do core image v2): ignora o alt do nó e serve o metadata do
        # DAM — `alt="544581870"` na tela — e trava o diálogo quando o DAM não
        # tem nada. O motor gravava a flag no `image` e nunca no twi.
        flags = {f: "false" for f in ("altValueFromDAM", "isDecorative")
                 if str(no.get(f, "")).lower() not in ("true", "false")}
        if texto(no.get("alt")):
            if flags:
                plano.append((caminho, None, "só flags", flags))
            continue
        novo, fonte = "", ""
        if rt == "textwithimage" and heading_do_texto(no.get("text")):
            novo, fonte = heading_do_texto(no.get("text")), "heading da dupla"
        elif ultimo_titulo:
            novo, fonte = ultimo_titulo, "título anterior"
        elif titulo_pagina:
            novo, fonte = titulo_pagina, "título da página"
        if novo:
            plano.append((caminho, novo[:120], fonte, flags))
        else:
            plano.append((caminho, "", "SEM FONTE", flags))
    return plano


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paginas", nargs="*", help="caminhos relativos, ex: /altera/altera-max-10")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--executar", action="store_true", help="grava (padrão é dry-run)")
    args = ap.parse_args()
    sessao, auth = build_session()
    base = CONFIG["base_url"]

    rels = list(args.paginas)
    if args.todas:
        url = (base + "/bin/querybuilder.json?path=" + RAIZ_DESTINO +
               "&type=cq:Page&p.limit=-1&p.hits=selective&p.properties=jcr:path")
        dados, _ = get_json(sessao, url, auth)
        rels = sorted(h["jcr:path"][len(RAIZ_DESTINO):] or "/" for h in dados["hits"])
    if not rels:
        print(__doc__)
        sys.exit(1)

    total = gravados = sem_fonte = 0
    for rel in rels:
        destino = RAIZ_DESTINO + ("" if rel == "/" else "/" + rel.strip("/"))
        jcr, st = get_json(sessao, f"{base}{destino}/jcr:content.infinity.json", auth)
        if st != 200 or not jcr:
            print(f"[erro] {rel}: HTTP {st}")
            continue
        plano = plano_da_pagina(jcr)
        if not plano:
            continue
        print(f"\n=== {rel}  —  {len(plano)} nó(s) a corrigir ===")
        payload = {}
        for caminho, novo, fonte, flags in plano:
            for f, v in flags.items():
                payload[f"{caminho}/{f}"] = v
            if novo is None:                      # alt já existe; faltavam só as flags
                print(f"   {caminho.split('/')[-1]:22} [{fonte:16}] + {', '.join(flags)}")
                continue
            marca = "  <<< SEM FONTE, não grava" if not novo else ""
            print(f"   {caminho.split('/')[-1]:22} [{fonte:16}] {novo!r}{marca}")
            if novo:
                payload[f"{caminho}/alt"] = novo
            else:
                sem_fonte += 1
        total += len(payload)
        if not payload:
            continue
        if not args.executar:
            print(f"   [dry-run] {len(payload)} alt(s) a gravar. Use --executar.")
            continue
        st, txt = post_node(sessao, base, f"{destino}/jcr:content", payload, auth)
        if st in (200, 201):
            gravados += len(payload)
            print(f"   [gravado] {len(payload)} alt(s)  HTTP {st}")
        else:
            print(f"   [FALHA] HTTP {st} {txt[:120]}")
    print(f"\n{total} alt(s) {'gravados' if args.executar else 'a gravar'}"
          f"{f', {gravados} gravados' if args.executar else ''}"
          f"{f', {sem_fonte} sem fonte' if sem_fonte else ''}.")


if __name__ == "__main__":
    main()
