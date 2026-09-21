#!/usr/bin/env python3
"""copiar_assets.py — cria no DAM do global2 os assets de dados/golive/mapa_assets.csv. Dry-run por padrão.

Cópia servidor-a-servidor (`:operation=copy`): nenhum byte passa por esta máquina (são 1,4 GB, um
tar.gz de 858 MB), e o asset chega com renditions e `processed`. Só cria: pasta ou asset que já
exista e não esteja no manifesto ABORTA (ver _comum.py). Confere cada um depois: dam:Asset, mesmo
dam:sha1, rendition original presente.

    python3 copiar_assets.py                # dry-run
    python3 copiar_assets.py --executar
    python3 copiar_assets.py --conferir     # só relê os destinos
    python3 copiar_assets.py --pasta microchip --executar   # só uma pasta de família (ensaio)
"""
import csv, sys
from _comum import DADOS, DAM_G2, copiar, criar, ler


def pasta(path, feitas, executar):
    """Cria a cadeia de pastas ABAIXO de DAM_G2 (que é da Anion e já existe)."""
    atual = DAM_G2
    for seg in path[len(DAM_G2):].strip("/").split("/"):
        atual += "/" + seg
        if atual in feitas:
            continue
        r = criar(atual, {"jcr:primaryType": "sling:Folder", "jcr:content/jcr:primaryType": "nt:unstructured",
                          "jcr:content/jcr:title": seg}, executar)
        if r != "ja-nosso":
            print(f"  pasta {r}: {atual[len(DAM_G2):]}")
        feitas.add(atual)


def confere(dest, sha):
    st, j = ler(dest, ".3.json")
    if st != 200 or j.get("jcr:primaryType") != "dam:Asset":
        return f"HTTP {st} / tipo {j and j.get('jcr:primaryType')}"
    c = j.get("jcr:content", {})
    if (c.get("metadata") or {}).get("dam:sha1") != sha:
        return "sha1 diferente"
    if "original" not in (c.get("renditions") or {}):
        return "sem rendition original"
    return ""


def main():
    executar, so_conferir = "--executar" in sys.argv, "--conferir" in sys.argv
    linhas = list(csv.DictReader(open(DADOS / "mapa_assets.csv")))
    unicos = {}
    for l in linhas:
        if not l["nota"]:
            unicos[l["destino"]] = l
    if "--pasta" in sys.argv:
        so = sys.argv[sys.argv.index("--pasta") + 1]
        unicos = {d: l for d, l in unicos.items() if d.startswith(f"{DAM_G2}/{so}/")}
    print(f"{len(unicos)} assets; {'EXECUTANDO' if executar else 'conferindo' if so_conferir else 'dry-run'}")
    st, _ = ler(DAM_G2)
    if st != 200:
        print(f"[erro] {DAM_G2}: HTTP {st}"); sys.exit(1)
    feitas, cont, ruins = set(), {"criado": 0, "ja-nosso": 0, "dry": 0}, []
    for i, (dest, l) in enumerate(sorted(unicos.items()), 1):
        if not so_conferir:
            pasta(dest.rsplit("/", 1)[0], feitas, executar)
            r = copiar(l["origem"], dest, executar)
            cont[r] += 1
            if r == "criado":
                print(f"  [{i}/{len(unicos)}] {dest[len(DAM_G2):]}  ({int(l['bytes']) / 1e6:.1f} MB)")
        if executar or so_conferir:
            e = confere(dest, l["sha1"])
            if e:
                ruins.append((dest, e)); print(f"  [CONFERIR] {dest}: {e}")
    print(cont, "| com problema:", len(ruins))
    sys.exit(1 if ruins else 0)


if __name__ == "__main__":
    main()
