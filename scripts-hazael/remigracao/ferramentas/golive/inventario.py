"""inventario.py — páginas dos dois lados + colisões. SOMENTE LEITURA."""
import csv, json, re, sys, collections
from pathlib import Path
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
AQUI = Path(__file__).resolve().parents[2] / "dados" / "golive"
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
G = "/content/macnicaglobal2/americas/mai/en/products/semiconductors"
PROPS = ("jcr:path jcr:createdBy jcr:created jcr:content/jcr:title jcr:content/cq:lastModified jcr:content/cq:lastModifiedBy "
         "jcr:content/cq:lastReplicationAction jcr:content/cq:lastReplicationAction_publish jcr:content/cq:lastReplicated jcr:content/cq:template jcr:content/deleted "
         "jcr:content/sling:resourceType jcr:content/jcr:mixinTypes jcr:content/cq:tags jcr:content/cq:canonicalUrl jcr:content/sling:vanityPath")
def paginas(raiz):
    r = s.get(BASE + "/bin/querybuilder.json", params={"path": raiz, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective", "p.properties": PROPS}, timeout=120)
    hits = r.json()["hits"]
    # a raiz não vem no path= do querybuilder? vem (path é descendant-or-self para type), mas garante:
    return {h["jcr:path"]: h for h in hits}
nos, g2 = paginas(T), paginas(G)
json.dump({"nos": nos, "g2": g2}, open(AQUI / "inventario.json", "w"), indent=1)
print(f"copia-teste: {len(nos)} páginas | global2/semiconductors: {len(g2)} páginas")
c = lambda h, k: (h.get("jcr:content") or {}).get(k, "")
print("\n== global2: por família (1º segmento) — páginas, criadores, última modificação, publicadas")
fam = collections.defaultdict(list)
for p, h in g2.items():
    rel = p[len(G):].strip("/"); fam[rel.split("/")[0] if rel else "(landing)"].append(h)
for f, hs in sorted(fam.items()):
    cri = collections.Counter(h.get("jcr:createdBy", "").split("@")[0] for h in hs)
    mod = max((c(h, "cq:lastModified") for h in hs), key=lambda d: d[11:15] + d[4:10] if d else "")
    pub = sum(1 for h in hs if "Activate" in (c(h, "cq:lastReplicationAction"), c(h, "cq:lastReplicationAction_publish")))
    print(f"   {f:26} {len(hs):3} pág  criadas por {dict(cri)}  publ={pub}")
print("\n== nossas famílias")
nf = collections.Counter((p[len(T):].strip("/").split("/")[0] or "(landing)") for p in nos)
print("  ", dict(nf))
print("\n== COLISÕES (mesmo caminho relativo, ignorando maiúsculas)")
g2low = {p[len(G):].lower(): p for p in g2}
col = [(p, g2low[p[len(T):].lower()]) for p in nos if p[len(T):].lower() in g2low]
print(f"   {len(col)} páginas nossas já têm homônima no global2")
for f, n in collections.Counter((a[len(T):].strip('/').split('/')[0] or '(landing)') for a, b in col).items(): print(f"     {f}: {n}")
dif = [(a[len(T):], b[len(G):]) for a, b in col if a[len(T):] != b[len(G):]]
print("   com grafia diferente:", dif[:10])
with open(AQUI / "colisoes.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["nossa", "global2", "g2_criador", "g2_modificado", "g2_por", "g2_publicada"])
    for a, b in col: w.writerow([a, b, g2[b].get("jcr:createdBy"), c(g2[b], "cq:lastModified"), c(g2[b], "cq:lastModifiedBy"), c(g2[b], "cq:lastReplicationAction")])
print("\n== famílias do global2 que NÃO são nossas:", sorted(set(fam) - set(nf)))
print("== páginas do global2 nas famílias em colisão que NÃO existem do nosso lado:")
nlow = {p[len(T):].lower() for p in nos}
for p in sorted(g2):
    rel = p[len(G):]
    if rel.strip("/").split("/")[0] in nf and rel.lower() not in nlow: print("    ", rel)
