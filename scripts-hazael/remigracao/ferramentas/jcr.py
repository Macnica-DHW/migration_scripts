#!/usr/bin/env python3
"""
jcr.py <rel> [gwi|dest|ambos] [--filtro texto] — árvore do jcr:content de uma página, enxuta. SOMENTE LEITURA.

Para o revisor da conferência visual: mostra, indentado, cada nó com o
resourceType (só o último segmento), width/offset do cq:responsive, styleIds,
flags do imagetext, id, e os primeiros 70 caracteres de texto. É o que se
precisa para explicar, no JCR, o que o print mostra.

  python3 remigracao/ferramentas/jcr.py /canon dest
  python3 remigracao/ferramentas/jcr.py /canon gwi --filtro "Evaluation Kit"
"""
import re, sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import build_session, get_json, CONFIG, normalize_name

G = "/content/macnicagwi/americas/mai/en/products/semiconductors"
D = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
PROPS = ("assetPositionLargeScreen", "isText", "isButton", "isHeading", "id", "type",
         "alignment", "listFrom", "maxItems", "orderBy", "layout", "fileReference",
         "fragmentVariationPath", "fragmentPath", "linkURL", "link", "backgroundColor")


def txt(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v))).strip()


def mostra(no, nome, nivel, linhas):
    rt = str(no.get("sling:resourceType", "")).split("/")[-1]
    partes = [f"{'  ' * nivel}{nome} [{rt}]"]
    resp = no.get("cq:responsive", {}).get("default", {}) if isinstance(no.get("cq:responsive"), dict) else {}
    if resp:
        partes.append("w=%s o=%s" % (resp.get("width", "-"), resp.get("offset", "-")))
    if no.get("cq:styleIds"):
        partes.append("styles=" + ",".join(no["cq:styleIds"]) if isinstance(no["cq:styleIds"], list) else f"styles={no['cq:styleIds']}")
    for p in PROPS:
        if p in no:
            partes.append(f"{p}={str(no[p])[:60]}")
    for p in ("jcr:title", "text", "heading", "title"):
        if p in no and not isinstance(no[p], dict):
            bruto = str(no[p])
            marca = " (ESPAÇADOR)" if p == "text" and not txt(bruto) else ""
            partes.append(f'{p}="{txt(bruto)[:70]}"{marca}')
            if p == "text":
                partes.append(f"html[{len(bruto)}]={bruto[:90]!r}")
    linhas.append("  ".join(partes))
    for k, v in no.items():
        if isinstance(v, dict) and k != "cq:responsive":
            mostra(v, k, nivel + 1, linhas)


def main():
    args = [a for a in sys.argv[1:]]
    filtro = None
    if "--filtro" in args:
        i = args.index("--filtro"); filtro = args[i + 1].lower(); del args[i:i + 2]
    rel = args[0].rstrip("/"); lado = args[1] if len(args) > 1 else "ambos"
    if rel == "": rel = ""
    s, auth = build_session(prompt_if_missing=False, verbose=False)
    base = CONFIG["base_url"]
    alvos = []
    if lado in ("gwi", "ambos"):
        alvos.append(("GWI", G + rel))
    if lado in ("dest", "ambos"):
        alvos.append(("DESTINO", D + "/".join(normalize_name(x) if x else x for x in rel.split("/"))))
    for rot, caminho in alvos:
        jcr, st = get_json(s, f"{base}{caminho}/jcr:content.infinity.json", auth)
        if st != 200 or not isinstance(jcr, dict):
            jcr, st = get_json(s, f"{base}{caminho}/jcr:content.50.json", auth)
        print(f"===== {rot} {caminho}  (HTTP {st})")
        if not isinstance(jcr, dict):
            continue
        print("  cq:template=%s  pageTitle=%r  jcr:title=%r" % (
            str(jcr.get("cq:template", "")).split("/")[-1], jcr.get("pageTitle"), jcr.get("jcr:title")))
        linhas = []
        for k, v in jcr.items():
            if isinstance(v, dict):
                mostra(v, k, 1, linhas)
        if filtro:
            idx = [i for i, l in enumerate(linhas) if filtro in l.lower()]
            ver = sorted({j for i in idx for j in range(max(0, i - 6), min(len(linhas), i + 7))})
            linhas = [linhas[j] for j in ver]
        print("\n".join(linhas))


if __name__ == "__main__":
    main()
