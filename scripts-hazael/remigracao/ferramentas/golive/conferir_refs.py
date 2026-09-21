#!/usr/bin/env python3
"""conferir_refs.py <prefixo> <raiz> — lê dados/links/<prefixo>_refs.csv (do censo_links.py) e responde:
(1) sobrou referência para copia-teste / macnicagwi?  (2) todo alvo interno existe no global2 — ou, se a
raiz ainda é o staging, vai existir com a cópia?  SOMENTE LEITURA. Sai 1 se houver pendência não prevista."""
import collections, csv, re, sys
from urllib.parse import unquote
from _comum import DADOS, G, MAI, STG, ler
from staging import paginas

PREVISTOS = {f"{MAI}/products/ip-software/v-by-oner-hs-ip", f"{MAI}/products/ip-software/munvme-ip-core"}   # página ainda não migrada por ninguém


def main():
    prefixo, raiz = sys.argv[1], sys.argv[2].rstrip("/")
    L = list(csv.DictReader(open(DADOS.parent / "links" / f"{prefixo}_refs.csv")))
    if "--familias-nossas" in sys.argv:
        from _comum import familias
        nossas = set(familias())
        L = [l for l in L if l["onde"] == "XF" or l["pagina"][len(raiz):].strip("/").split("/")[0] in nossas]
    print(f"{len(L)} referências sob {raiz}")
    print("  por classe:", dict(collections.Counter(l["classe"] for l in L)))
    fora = [l for l in L if re.search(r"copia-teste|macnicagwi|gwi", l["classe"], re.I)]
    a_criar = {G + p for p in paginas(STG)} if raiz == STG else set()
    alvos = collections.defaultdict(set)
    for l in L:
        if l["url"].startswith("/content/"):
            u = re.sub(r"\.html(?=$|[?#])", "", unquote(l["url"])).split("#")[0].split("?")[0].rstrip("/")
            alvos[u].add(l["pagina"][len(raiz):])
    falta = {}
    for u, pgs in sorted(alvos.items()):
        if u in a_criar:
            continue
        st, _ = ler(u, ".json")
        if st != 200:
            falta[u] = (st, sorted(pgs))
    print(f"  alvos internos distintos: {len(alvos)}; que a cópia cria: {sum(1 for u in alvos if u in a_criar)}; inexistentes: {len(falta)}")
    for u, (st, pgs) in falta.items():
        print(f"     {'previsto' if u in PREVISTOS else 'PENDENTE'} HTTP {st}  {u.replace(MAI, '<mai/en>')}   <- {pgs[:3]}{' …' if len(pgs) > 3 else ''}")
    for l in fora[:15]:
        print("  [FORA DO GLOBAL2]", l["pagina"][len(raiz):], l["prop"], l["url"][:110])
    ruim = len(fora) + sum(1 for u in falta if u not in PREVISTOS)
    print("  RESULTADO:", "PENDÊNCIAS: %d" % ruim if ruim else "tudo aponta para o global2 e todo alvo existe (fora os 2 previstos)")
    sys.exit(1 if ruim else 0)


if __name__ == "__main__":
    main()
