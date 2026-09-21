#!/usr/bin/env python3
"""censo_links.py — censo AO VIVO de toda referência (link/asset/XF) gravada no JCR de
semiconductors-remigration e dos XFs que as páginas embutem. SOMENTE LEITURA (só GET, só no author).

Saídas (em remigracao/dados/links/): refs.csv (uma linha por referência) e paginas.csv.
"""
import csv, html, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session

AQUI = Path(__file__).resolve().parents[1] / "dados" / "links"
# uso: censo_links.py [raiz] [prefixo-de-saida]   — sem argumentos: a árvore revisada, refs.csv/paginas.csv
_args = [a for a in sys.argv[1:] if not a.startswith("-")]
RAIZ = _args[0].rstrip("/") if _args else "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
PREFIXO = (_args[1] + "_") if len(_args) > 1 else ""
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE   # cookie só vai para o author

sessao, auth = build_session()


def get(path_e_sufixo):
    r = sessao.get(BASE + quote(path_e_sufixo, safe="/:.?=&%"), timeout=60, allow_redirects=False)
    return r


def fundo(path):
    """JSON completo de `path`, contornando o HTTP 300 (profundidade recusada): busca na maior
    profundidade aceita e re-busca, um a um, os nós que ficaram na borda."""
    r = get(f"{path}.infinity.json")
    if r.status_code == 200:
        return r.json(), 0
    if r.status_code != 300:
        return None, r.status_code
    ds = [int(m.group(1)) for o in r.json() if (m := re.search(r"\.(\d+)\.json$", str(o)))]
    d = max(ds)
    r = get(f"{path}.{d}.json")
    if r.status_code != 200:
        return None, r.status_code
    j = r.json()
    cortes = 0

    def desce(no, p, nivel):
        nonlocal cortes
        for k, v in list(no.items()):
            if isinstance(v, dict):
                if nivel + 1 >= d:
                    sub, _ = fundo(f"{p}/{k}")
                    if sub is not None:
                        no[k] = sub; cortes += 1
                else:
                    desce(v, f"{p}/{k}", nivel + 1)
    desce(j, path, 0)
    return j, cortes


ATTR_RE = re.compile(r'\b(href|src|data-src|poster|action)\s*=\s*(["\'])(.*?)\2', re.I | re.S)
URLISH = re.compile(r"^(/content/|/etc/|/conf/|https?://|//|mailto:|tel:|www\.)", re.I)
# propriedades que são metadado do AEM, não referência de conteúdo
IGNORAR = {"sling:resourceType", "sling:resourceSuperType", "jcr:primaryType", "jcr:mixinTypes", "cq:template",
           "jcr:createdBy", "cq:lastModifiedBy", "jcr:lastModifiedBy", "jcr:uuid", "cq:lastReplicatedBy",
           "cq:lastReplicationAction", "cq:policy"}


def refs_de(no, caminho, saida):
    for k, v in no.items():
        if isinstance(v, dict):
            refs_de(v, f"{caminho}/{k}", saida)
            continue
        if k in IGNORAR:
            continue
        for s in (v if isinstance(v, list) else [v]):
            if not isinstance(s, str) or not s:
                continue
            if "<" in s and ("href" in s or "src" in s or "action" in s):
                for m in ATTR_RE.finditer(s):
                    saida.append((caminho, k, m.group(1).lower(), html.unescape(m.group(3)).strip()))
            elif URLISH.match(s.strip()) and "\n" not in s and len(s) < 600:
                saida.append((caminho, k, "prop", s.strip()))


def classe(u):
    l = u.lower()
    if l.startswith("#"): return "ancora"
    if l.startswith(("mailto:", "tel:")): return "mailto/tel"
    if l.startswith("javascript:"): return "javascript"
    if "adobeaemcloud.com" in l: return "URL-DE-AUTHOR"
    if re.match(r"^(https?:)?//(www\.)?macnica\.com", l): return "publico-macnica.com"
    if l.startswith(("http://", "https://", "//", "www.")): return "externo"
    if l.startswith("/content/dam/macnicagwi"): return "DAM-gwi"
    if l.startswith("/content/dam/copia-teste"): return "DAM-copia-teste"
    if l.startswith("/content/dam/macnicaglobal2"): return "DAM-global2"
    if l.startswith("/content/dam/"): return "DAM-outro"
    if l.startswith("/content/experience-fragments/copia-teste"): return "XF-copia-teste"
    if l.startswith("/content/experience-fragments/macnicaglobal2"): return "XF-global2"
    if l.startswith("/content/experience-fragments/"): return "XF-outro"
    if l.startswith("/content/macnicagwi"): return "PAGINA-gwi"
    if l.startswith(RAIZ.lower()): return "pagina-copia-teste(na arvore)"
    if l.startswith("/content/copia-teste"): return "pagina-copia-teste(FORA da arvore)"
    if l.startswith("/content/macnicaglobal2"): return "pagina-global2"
    if l.startswith("/content/cq:tags") or l.startswith("/content/_cq_tags"): return "tag"
    if l.startswith("/content/"): return "content-outro"
    if l.startswith("/"): return "relativo-raiz"
    return "outro"


def main():
    # 1. páginas
    r = get(f"/bin/querybuilder.json?path={RAIZ}&type=cq:Page&p.limit=-1&p.hits=selective&p.properties=jcr:path")
    paginas = sorted(h["jcr:path"] for h in r.json()["hits"])
    if RAIZ not in paginas:
        paginas.insert(0, RAIZ)
    print(f"{len(paginas)} páginas sob {RAIZ}", file=sys.stderr)

    def uma(p):
        j, info = fundo(f"{p}/jcr:content")
        if j is None:
            return p, None, info, []
        out = []
        refs_de(j, "jcr:content", out)
        return p, j, info, out

    linhas, meta, xfs = [], [], set()
    with ThreadPoolExecutor(4) as ex:
        for p, j, info, out in ex.map(uma, paginas):
            if j is None:
                meta.append((p, f"HTTP {info}", "", "", "", 0)); continue
            meta.append((p, "ok", f"cortes300={info}", j.get("jcr:title", ""), j.get("cq:lastModifiedBy", ""), len(out)))
            for no, prop, tipo, u in out:
                linhas.append(("pagina", p, no, prop, tipo, u, classe(u)))
                if u.startswith("/content/experience-fragments/"):
                    xfs.add(u)

    # 2. XFs embutidos (o conteúdo deles aparece em toda página que os embute)
    for x in sorted(xfs):
        j, info = fundo(f"{x}/jcr:content")
        if j is None:
            meta.append((x, f"XF HTTP {info}", "", "", "", 0)); continue
        out = []
        refs_de(j, "jcr:content", out)
        meta.append((x, "ok-XF", f"cortes300={info}", j.get("jcr:title", ""), j.get("cq:lastModifiedBy", ""), len(out)))
        for no, prop, tipo, u in out:
            linhas.append(("XF", x, no, prop, tipo, u, classe(u)))

    with open(AQUI / f"{PREFIXO}refs.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["onde", "pagina", "no", "prop", "tipo", "url", "classe"]); w.writerows(linhas)
    with open(AQUI / f"{PREFIXO}paginas.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["path", "status", "info", "titulo", "lastModifiedBy", "n_refs"]); w.writerows(meta)
    print(f"{len(linhas)} referências; {len(xfs)} XFs distintos -> refs.csv / paginas.csv", file=sys.stderr)


if __name__ == "__main__":
    main()
