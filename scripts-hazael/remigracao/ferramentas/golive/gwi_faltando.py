#!/usr/bin/env python3
"""
gwi_faltando.py [--gwi RAIZ] [--g RAIZ] [--nome NOME] — que página do GWI ainda não existe no global2? SOMENTE LEITURA
(só GET; o GWI é só referência).

Pedido do Hazael (23/09/2026, depois do go-live de mai/en): "Are there pages (that are not test pages) in GWI
that aren't in macnicaglobal2?". Para cada cq:Page do GWI procura par no global2:
  1. pelo caminho, com cada segmento normalizado (normalize_name) e sem diferença de caixa;
  2. pelas trocas de árvore conhecidas: `technology` → `solutions` (move do Hazael, 21/09),
     `semiconductors/sony-image-sensors/…` → `semiconductors/sony/sony-image-sensors/…` (aninhamento da Anion);
  3. se não achou: página do global2 com o mesmo título (jcr:title ou pageTitle) na mesma seção de 1º nível —
     "provável par com outro nome", para conferir à mão.
Página do global2 soft-deleted (`deleted`) não conta como par. As do GWI saem em grupos: FALTA (publicada, não é
teste, não é redirect), e à parte: teste, soft-deleted, nunca publicada/desativada, redirect.

    python3 gwi_faltando.py                         # americas/mai/en
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from levantamento_existente import DADOS, get  # noqa: E402
from aem_lib import normalize_name  # noqa: E402

TROCAS = [("technology", "solutions"),
          ("products/semiconductors/sony-image-sensors", "products/semiconductors/sony/sony-image-sensors")]
TESTE = re.compile(r"(^|[-_/])test([-_/]|s?$|ing|e)|^titles$|sony-test", re.I)
PROPS = ("jcr:path jcr:content/jcr:title jcr:content/pageTitle jcr:content/deleted jcr:content/cq:redirectTarget "
         "jcr:content/cq:lastReplicationAction jcr:content/cq:lastReplicationAction_publish jcr:content/cq:template "
         "jcr:content/cq:lastModified jcr:createdBy")


def paginas(raiz):
    """{rel: hit} de toda cq:Page, seção de 1º nível por seção (a árvore inteira de uma vez estoura o tempo)."""
    out = {}
    r = get(raiz, ".1.json")
    secoes = [k for k, v in r.json().items() if isinstance(v, dict) and v.get("jcr:primaryType") == "cq:Page"]
    for sec in [""] + secoes:
        cam = f"{raiz}/{sec}".rstrip("/")
        if sec == "":
            h = get(cam, "/jcr:content.json").json()
            out[""] = {"jcr:path": raiz, "jcr:content": h}
            continue
        h = get(cam, "/jcr:content.json")
        out[sec] = {"jcr:path": cam, "jcr:content": h.json() if h.status_code == 200 else {}}
        q = get("/bin/querybuilder.json", path=cam, type="cq:Page",
                **{"p.limit": "-1", "p.hits": "selective", "p.properties": PROPS})
        if q.status_code != 200:
            sys.exit(f"[erro] HTTP {q.status_code} no querybuilder de {cam}")
        for x in q.json()["hits"]:
            out[x["jcr:path"][len(raiz) + 1:]] = x
    return out


def c(h, k):
    return (h.get("jcr:content") or {}).get(k) or ""


def chave(rel):
    return "/".join(normalize_name(x) for x in rel.split("/")).lower() if rel else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gwi", default="/content/macnicagwi/americas/mai/en")
    ap.add_argument("--g", default="/content/macnicaglobal2/americas/mai/en")
    ap.add_argument("--nome", default="mai-en")
    a = ap.parse_args()
    W, G = paginas(a.gwi), paginas(a.g)
    g_vivas = {chave(r): r for r, h in G.items() if not c(h, "deleted")}
    g_mortas = {chave(r): r for r, h in G.items() if c(h, "deleted")}
    titulos = collections.defaultdict(list)
    for r, h in G.items():
        if not c(h, "deleted"):
            for t in {c(h, "jcr:title").strip().lower(), c(h, "pageTitle").strip().lower()} - {""}:
                titulos[(r.split("/")[0], t)].append(r)
    print(f"GWI {a.gwi}: {len(W)} páginas | global2 {a.g}: {len(G)} ({len(g_mortas)} soft-deleted)")

    grupos = collections.defaultdict(list)
    for rel in sorted(W):
        h = W[rel]
        cands = [chave(rel)]
        for de, para in TROCAS:
            k = chave(rel)
            if k == de or k.startswith(de + "/"):
                cands.append(para + k[len(de):])
        par = next((g_vivas[k] for k in cands if k in g_vivas), None)
        if par is not None:
            continue
        pub = c(h, "cq:lastReplicationAction") or c(h, "cq:lastReplicationAction_publish")
        tit = c(h, "pageTitle") or c(h, "jcr:title")
        linha = {"rel": rel, "titulo": tit, "publicacao": pub or "nunca", "redirect": c(h, "cq:redirectTarget"),
                 "template": c(h, "cq:template").rsplit("/", 1)[-1], "morta_em_g": next((g_mortas[k] for k in cands if k in g_mortas), None)}
        sec = rel.split("/")[0]
        mesmos = titulos.get((sec, tit.strip().lower())) or titulos.get((dict(TROCAS).get(sec, sec), tit.strip().lower())) or []
        if mesmos:
            linha["provavel_par"] = mesmos[:3]
        if any(TESTE.search(seg) for seg in rel.split("/")) or re.search(r"\btest\b", tit, re.I):
            grupos["TESTE"].append(linha)
        elif c(h, "deleted"):
            grupos["SOFT-DELETED no GWI"].append(linha)
        elif pub != "Activate":
            grupos["NÃO PUBLICADA no GWI"].append(linha)
        elif linha["redirect"]:
            grupos["REDIRECT no GWI"].append(linha)
        elif mesmos:
            grupos["PROVÁVEL PAR COM OUTRO NOME"].append(linha)
        else:
            grupos["FALTA"].append(linha)

    for g in ("FALTA", "PROVÁVEL PAR COM OUTRO NOME", "REDIRECT no GWI", "NÃO PUBLICADA no GWI", "SOFT-DELETED no GWI", "TESTE"):
        L = grupos.get(g, [])
        por_secao = collections.Counter("/".join(x["rel"].split("/")[:2]) for x in L)
        print(f"\n===== {g}: {len(L)}   {dict(por_secao.most_common())}")
        for x in L:
            extra = (f"  ~ {x['provavel_par']}" if x.get("provavel_par") else "") + (f"  (soft-deleted em G: {x['morta_em_g']})" if x["morta_em_g"] else "") \
                + (f"  -> {x['redirect']}" if x["redirect"] else "") + ("" if g == "FALTA" else f"  [{x['publicacao']}]")
            print(f"  {x['rel'][:110]:110} {x['titulo'][:50]!r}{extra}")
    arq = DADOS / f"gwi_faltando_{a.nome}.json"
    json.dump(grupos, open(arq, "w"), indent=1, ensure_ascii=False)
    print(f"\nJSON: {arq}")


if __name__ == "__main__":
    main()
