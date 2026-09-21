"""Para as 35 colisões: quando/quem, e o quanto o conteúdo deles se parece com o nosso. SOMENTE LEITURA."""
import csv, json, re, sys, collections, difflib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
AQUI = Path(__file__).resolve().parents[2] / "dados" / "golive"
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
G = "/content/macnicaglobal2/americas/mai/en/products/semiconductors"
inv = json.load(open(AQUI / "inventario.json"))
col = list(csv.DictReader(open(AQUI / "colisoes.csv")))
def jc(p):
    r = s.get(BASE + quote(p, safe="/:") + "/jcr:content.infinity.json", timeout=60, allow_redirects=False)
    return r.json() if r.status_code == 200 else {}
def perfil(j):
    rts, textos = collections.Counter(), []
    def d(n):
        rt = str(n.get("sling:resourceType", "")).split("/")[-1]
        if rt: rts[rt] += 1
        for k, v in n.items():
            if isinstance(v, dict): d(v)
            elif k in ("text", "jcr:title", "heading", "title") and isinstance(v, str):
                t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", v)).strip()
                if t: textos.append(t)
    d(j.get("root", {}))
    return rts, " ".join(textos)
def um(c):
    a, b = jc(c["nossa"]), jc(c["global2"])
    (ra, ta), (rb, tb) = perfil(a), perfil(b)
    sim = difflib.SequenceMatcher(None, ta[:6000], tb[:6000]).ratio() if ta and tb else 0
    return c["global2"][len(G):], inv["g2"][c["global2"]].get("jcr:created", "")[4:21], c["g2_criador"].split("@")[0], c["g2_modificado"][4:21], c["g2_por"].split("@")[0], sum(ra.values()), sum(rb.values()), len(ta), len(tb), round(sim, 2), dict(rb.most_common(6))
with ThreadPoolExecutor(4) as ex: res = list(ex.map(um, col))
print(f"{'página global2':62} {'criada':17} {'por':10} {'modif.':17} {'por':10} nós(n/g2) txt(n/g2)  sim")
for r in sorted(res): print(f"{r[0][:62]:62} {r[1]:17} {r[2]:10} {r[3]:17} {r[4]:10} {r[5]:3}/{r[6]:<3}  {r[7]:5}/{r[8]:<5} {r[9]}")
print("\ncomponentes deles (exemplo):", res[1][10])
print("média de similaridade de texto:", round(sum(r[9] for r in res) / len(res), 2))
# landings
for nome, p in (("nossa", T), ("global2", G)):
    r = s.get(BASE + p + "/jcr:content.infinity.json", timeout=60).json()
    rts, t = perfil(r)
    print(f"\nLANDING {nome}: título={r.get('jcr:title')!r} modif={r.get('cq:lastModified','')[4:21]} por={r.get('cq:lastModifiedBy','').split('@')[0]} publ={r.get('cq:lastReplicationAction')} template={r.get('cq:template','').split('/')[-1]} nós={sum(rts.values())} txt={len(t)}  mixins={r.get('jcr:mixinTypes')}")
    print("   ", dict(rts.most_common(8)))
