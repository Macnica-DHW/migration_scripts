#!/usr/bin/env python3
"""mapa_assets.py — origem -> destino de cada asset que as páginas do ESCOPO usam. SOMENTE LEITURA.

Escopo = famílias de _comum.familias() menos as páginas de teste. Desenho e nome da Anion:
  <DAM_G2>/<família>/{images,pdfs,logos,downloads}/<nome-em-minúscula-com-hífen>
Asset usado por 2+ famílias -> <DAM_G2>/common/. Dois arquivos que caem no mesmo destino: compara
dam:sha1 — igual vira um só, diferente ganha sufixo -2. Lê dados/links/refs.csv; grava dados/golive/mapa_assets.csv.
"""
import collections, csv, re
from urllib.parse import unquote
from _comum import DADOS, DAM_G2, PASTA_DAM, T, TESTE, XF_T, familias, ler

REFS = DADOS.parent / "links" / "refs.csv"


def nome(n):
    base, _, ext = unquote(n).rpartition(".")
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") + "." + ext.lower()


def sub(a):
    ext = a.rsplit(".", 1)[-1].lower()
    if "/logos/" in a: return "logos"
    if ext == "pdf": return "pdfs"
    if ext in ("zip", "rar", "gz"): return "downloads"
    return "images"


def main():
    fams = set(familias())
    usa = collections.defaultdict(set)
    for l in csv.DictReader(open(REFS)):
        if not l["classe"].startswith("DAM"): continue
        if l["onde"] == "XF":
            usa[unquote(l["url"])].add("common"); continue
        rel = l["pagina"][len(T):]
        f = rel.strip("/").split("/")[0]
        if f in fams and rel not in TESTE:
            usa[unquote(l["url"])].add(f)
    linhas, por_destino = [], collections.defaultdict(list)
    for a, fs in sorted(usa.items()):
        f = PASTA_DAM.get(next(iter(fs)), next(iter(fs))) if len(fs) == 1 else "common"
        st, meta = ler(a, "/jcr:content/metadata.json")
        if st != 200:
            print(f"[erro] origem não existe: {a} (HTTP {st})"); raise SystemExit(1)
        d = f"{DAM_G2}/{f}/{sub(a)}/{nome(a.rsplit('/', 1)[-1])}"
        por_destino[d].append((a, meta.get("dam:sha1"), int(meta.get("dam:size", 0) or 0), sorted(fs)))
    fundidos = sufixados = 0
    for d, origens in sorted(por_destino.items()):
        vistos = {}
        for a, sha, tam, fs in origens:
            if sha in vistos:                                   # mesmo arquivo: um asset só
                linhas.append([a, vistos[sha], sha, tam, ";".join(fs), "mesmo-sha-de-outro"]); fundidos += 1
                continue
            dest = d if not vistos else re.sub(r"(\.[a-z0-9]+)$", rf"-{len(vistos) + 1}\1", d)
            sufixados += bool(vistos)
            vistos[sha] = dest
            linhas.append([a, dest, sha, tam, ";".join(fs), ""])
    with open(DADOS / "mapa_assets.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["origem", "destino", "sha1", "bytes", "familias", "nota"]); w.writerows(sorted(linhas))
    dest = {l[1] for l in linhas}
    print(f"{len(linhas)} origens -> {len(dest)} assets a criar ({sum(l[3] for l in linhas if not l[5]) / 1e6:.0f} MB); "
          f"fundidos por sha igual: {fundidos}; com sufixo por sha diferente: {sufixados}")
    print("pastas:", dict(collections.Counter(d.split("/")[-3] for d in dest).most_common()))
    print("sem sha1:", sum(1 for l in linhas if not l[2]))


if __name__ == "__main__":
    main()
