#!/usr/bin/env python3
"""
serie_twi.py — pares texto|foto em SÉRIE com a mesma largura de coluna (R50),
aplicado ao que JÁ está gravado, sem regenerar a página.

A R36/R46 dimensionam cada foto pela altura que o GWI desenha (277px), então
a coluna varia com a proporção: 36% para 16:9, 32% para 3:2. Numa série isso
põe a borda esquerda das fotos em zigue-zague (`/ambarella`, "Why Choose…":
5 colunas de 472px e 2 de 419px). Regra: série = 2+ `textwithimage` seguidos
na ordem do documento, com só `hr`/espaçador entre eles; todos ficam com a
MAIOR razão da série. Par isolado não muda.

O motor tem a mesma regra (`_harmonizar_series_twi`) para os próximos lotes;
isto aqui alinha o servidor agora — e não apaga o fundo por grupo, que a
regeneração da página apagaria. Escreve SÓ `imageRatio`. Idempotente.

    python3 serie_twi.py /ambarella            # dry-run (padrão)
    python3 serie_twi.py --todas --executar
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
INVOLUCROS = {"container", "flexcontainer", "flexcontaineritem", "responsivegrid", ""}


def em_ordem(no, caminho, saida):
    for k, v in no.items():
        if not isinstance(v, dict) or k == "cq:responsive":
            continue
        rt = str(v.get("sling:resourceType", "")).split("/")[-1]
        saida.append((f"{caminho}/{k}", rt, v))
        em_ordem(v, f"{caminho}/{k}", saida)
    return saida


def espacador(rt, no):
    return rt == "text" and not re.sub(r"<[^>]+>|&nbsp;|\s", "", str(no.get("text") or ""))


def series(jcr):
    """[[(caminho, nó), ...], ...] — corridas de 2+ textwithimage."""
    corridas, atual = [], []
    for caminho, rt, no in em_ordem(jcr.get("root", {}), "root", []):
        if rt == "textwithimage":
            atual.append((caminho, no))
        elif rt in INVOLUCROS or espacador(rt, no):
            continue
        else:
            if len(atual) >= 2:
                corridas.append(atual)
            atual = []
    if len(atual) >= 2:
        corridas.append(atual)
    return corridas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paginas", nargs="*")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--executar", action="store_true")
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

    total = n_series = 0
    for rel in rels:
        destino = RAIZ_DESTINO + ("" if rel == "/" else "/" + rel.strip("/"))
        jcr, st = get_json(sessao, f"{base}{destino}/jcr:content.infinity.json", auth)
        if st != 200 or not jcr:
            print(f"[erro] {rel}: HTTP {st}")
            continue
        payload, linhas = {}, []
        for corrida in series(jcr):
            n_series += 1
            razoes = [int(no["imageRatio"]) for _, no in corrida
                      if str(no.get("imageRatio", "")).isdigit()]
            if not razoes:
                continue
            alvo = max(razoes)
            atuais = [str(no.get("imageRatio", "—")) for _, no in corrida]
            if all(a == str(alvo) for a in atuais):
                continue
            linhas.append(f"   série de {len(corrida)}: {' '.join(atuais)}  ->  todos {alvo}")
            for caminho, no in corrida:
                if str(no.get("imageRatio", "")) != str(alvo):
                    payload[f"{caminho}/imageRatio"] = str(alvo)
        if not payload:
            continue
        print(f"\n=== {rel} ===")
        print("\n".join(linhas))
        total += len(payload)
        if not args.executar:
            print(f"   [dry-run] {len(payload)} imageRatio a gravar")
            continue
        st, txt = post_node(sessao, base, f"{destino}/jcr:content", payload, auth)
        print(f"   [gravado] {len(payload)}  HTTP {st}" if st in (200, 201)
              else f"   [FALHA] HTTP {st} {txt[:120]}")
    print(f"\n{n_series} série(s) na árvore; {total} imageRatio "
          f"{'gravados' if args.executar else 'a gravar'}.")


if __name__ == "__main__":
    main()
