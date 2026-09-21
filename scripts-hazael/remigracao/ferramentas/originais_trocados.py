#!/usr/bin/env python3
"""
originais_trocados.py [--csv mapa_assets.csv | <asset>...] — a rendition `original` ainda é o arquivo do GWI? SOMENTE LEITURA.

POR QUE EXISTE (macnica-products/macnica-cv75, 21/09/2026): a foto da SoM saía
CORTADA em 4:3 no `textwithimage` — e a causa não era o componente. No DAM da
copia-teste a `original` de `macnica-cv75.jpg` tinha 540x405 / 58.598 bytes,
enquanto o `metadata` (540x565, `dam:size` 178.237, `dam:sha1` igual ao do GWI)
e as renditions web ainda descreviam a foto inteira: outro script regravou o
binário por cima DEPOIS do processamento (17:19 GMT, junto com a página dele).
O logo `macnica_Brand_LOGO_RGB_1.png` idem: 3156x983 -> 144x45. O servlet do
Image (`.coreimg.*`) serve a `original`, então a tela mostra o arquivo trocado;
olhar `metadata`/`dam:sha1` NÃO acusa nada.

O DAM da copia-teste é COMPARTILHADO: o que outro script troca ali muda as
NOSSAS páginas sem que ninguém grave nelas.

COMO CONFERE: tamanho de `renditions/original` (`:jcr:data`, 1 GET pequeno, sem
baixar o binário) contra (a) a coluna `bytes` do CSV do go-live, ou (b) o
`dam:size` do próprio metadata, ou (c) a `original` do mesmo caminho no DAM do
GWI (`--gwi`, quando o caminho é espelho).

  python3 remigracao/ferramentas/originais_trocados.py --csv remigracao/dados/golive/mapa_assets.csv
  python3 remigracao/ferramentas/originais_trocados.py --gwi /content/dam/copia-teste/.../macnica-cv75.jpg
"""
import csv, sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import build_session, get_json, CONFIG


def tamanho_original(s, auth, base, asset):
    d, st = get_json(s, f"{base}{asset}/jcr:content/renditions/original/jcr:content.json", auth)
    if st != 200 or not isinstance(d, dict):
        return None, None, None
    return d.get(":jcr:data"), d.get("jcr:lastModified"), str(d.get("jcr:lastModifiedBy", "")).split("@")[0]


def main():
    args = sys.argv[1:]
    gwi = "--gwi" in args
    esperado = {}
    if "--csv" in args:
        i = args.index("--csv")
        for r in csv.DictReader(open(args[i + 1])):
            if r["origem"].startswith(CONFIG["dam_target_prefix"]):
                esperado[r["origem"]] = int(r["bytes"]) if r.get("bytes") else None
        del args[i:i + 2]
    for a in args:
        if not a.startswith("--"):
            esperado.setdefault(a, None)
    if not esperado:
        sys.exit(__doc__)

    s, auth = build_session(prompt_if_missing=False, verbose=False)
    base = CONFIG["base_url"]
    if "author-" not in base:
        sys.exit(f"[erro] base_url inesperada: {base}")

    trocados = sem = 0
    for a, esp in sorted(esperado.items()):
        tam, quando, quem = tamanho_original(s, auth, base, a)
        if tam is None:
            sem += 1
            print(f"  [sem original] {a}")
            continue
        fonte = "csv"
        if gwi:
            esp, _q, _w = tamanho_original(s, auth, base, a.replace(
                CONFIG["dam_target_prefix"], CONFIG["dam_source_prefix"], 1))
            fonte = "gwi"
        if esp is None:
            md, _ = get_json(s, f"{base}{a}/jcr:content/metadata.json", auth)
            esp = int(md["dam:size"]) if isinstance(md, dict) and md.get("dam:size") else None
            fonte = "dam:size"
        if esp is not None and tam != esp:
            trocados += 1
            print(f"  [TROCADO] original={tam}b esperado({fonte})={esp}b  por {quem} em {quando}\n            {a}")
    print(f"\n  assets: {len(esperado)}   original trocada: {trocados}   sem original: {sem}")
    return 1 if trocados else 0


if __name__ == "__main__":
    sys.exit(main())
