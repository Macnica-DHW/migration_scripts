"""censo_links_alvos.py — depois do censo_links.py: cada alvo interno distinto existe HOJE? e vai existir
no global2 depois da cópia (irmã na árvore / mesmo caminho sob macnicaglobal2)? SOMENTE LEITURA (GET no author).
Lê dados/links/refs.csv e paginas.csv; grava dados/links/alvos.csv."""
import csv, os, re, sys, json, collections
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
os.chdir(Path(__file__).resolve().parents[1] / "dados" / "links")
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
G2 = "/content/macnicaglobal2/americas/mai/en/products/semiconductors"
L = list(csv.DictReader(open("refs.csv")))
PAGS = {p["path"] for p in csv.DictReader(open("paginas.csv")) if p["status"] == "ok"}

def limpa(u): return re.sub(r"\.html(?=$|[?#])", "", u).split("#")[0].split("?")[0].rstrip("/")

def existe(path):
    """200 / 404 / 'soft-deleted' para página; 200/404 para o resto."""
    path = unquote(path)          # o JCR guarda "%20"; sem decodificar antes vira %2520 e dá 404 falso
    r = s.get(BASE + quote(path, safe="/:") + ("/jcr:content.json" if "/dam/" not in path else ".json"), timeout=40, allow_redirects=False)
    if r.status_code == 200 and "/dam/" not in path:
        try:
            j = r.json()
            if j.get("deleted") or j.get("deletedBy"): return "soft-deleted"
        except ValueError: pass
    if r.status_code == 404 and "/dam/" not in path:       # nó sem jcr:content (pasta)?
        r2 = s.get(BASE + quote(path, safe="/:") + ".json", timeout=40, allow_redirects=False)
        return "200-sem-jcr:content" if r2.status_code == 200 else 404
    return r.status_code

alvos = collections.defaultdict(set)
for l in L:
    if l["classe"].startswith(("pagina-", "PAGINA-", "DAM-", "XF-")):
        alvos[(l["classe"], limpa(l["url"]))].add(l["pagina"])

def linha(item):
    (cl, u), pgs = item
    agora = existe(u)
    futuro, depois = "", ""
    if cl == "pagina-global2":
        if u.startswith(G2):
            irma = T + u[len(G2):]
            futuro = "sim" if irma in PAGS else ("sim(maiusc)" if irma.lower() in {p.lower() for p in PAGS} else "NAO")
    elif cl.startswith("pagina-copia-teste(na"):
        futuro = "sim" if u in PAGS else "NAO-EXISTE-NA-ARVORE"
        depois = G2 + u[len(T):]
    elif cl == "DAM-copia-teste":
        depois = u.replace("/content/dam/copia-teste", "/content/dam/macnicaglobal2", 1)
        futuro = str(existe(depois))
    elif cl == "DAM-gwi":
        depois = u.replace("/content/dam/macnicagwi", "/content/dam/macnicaglobal2", 1)
        futuro = str(existe(depois))
    elif cl == "XF-copia-teste":
        depois = u.replace("/experience-fragments/copia-teste", "/experience-fragments/macnicaglobal2", 1)
        futuro = str(existe(depois))
    elif cl == "PAGINA-gwi":
        depois = u.replace("/content/macnicagwi", "/content/macnicaglobal2", 1)
        futuro = str(existe(depois))
    return cl, u, agora, futuro, depois, len(pgs), sorted(pgs)[0].replace(T, "")

with ThreadPoolExecutor(6) as ex:
    res = list(ex.map(linha, alvos.items()))
with open("alvos.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["classe", "alvo", "existe_agora", "futuro", "alvo_global2", "n_paginas", "exemplo"]); w.writerows(sorted(res))
for cl in sorted({r[0] for r in res}):
    sub = [r for r in res if r[0] == cl]
    print(f"\n== {cl}: {len(sub)} alvos distintos")
    print("   existe agora:", dict(collections.Counter(str(r[2]) for r in sub)))
    print("   futuro      :", dict(collections.Counter(str(r[3]) for r in sub)))
