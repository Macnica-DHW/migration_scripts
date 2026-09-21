"""Sobreposição de assets com o DAM do global2 + carimbos de edição manual. SOMENTE LEITURA."""
import csv, json, re, sys, collections
from pathlib import Path
from urllib.parse import unquote
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
AQUI = Path(__file__).resolve().parents[2] / "dados" / "golive"
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
def qb(**kw):
    kw.setdefault("p.limit", "-1"); kw.setdefault("p.hits", "selective")
    return s.get(BASE + "/bin/querybuilder.json", params=kw, timeout=180).json()["hits"]
g2 = [h["jcr:path"] for h in qb(path="/content/dam/macnicaglobal2", type="dam:Asset", **{"p.properties": "jcr:path"})]
print(f"DAM global2 inteiro: {len(g2)} assets;  em americas/mai: {sum(1 for p in g2 if '/americas/mai/' in p)}")
print("   por pasta (3 níveis abaixo de americas/mai/en):", collections.Counter("/".join(p.split("/")[7:10]) for p in g2 if "/americas/mai/en/" in p).most_common(10))
norm = lambda n: re.sub(r"[^a-z0-9.]+", "-", unquote(n).lower())
por_nome = collections.defaultdict(list)
for p in g2: por_nome[norm(p.rsplit("/", 1)[-1])].append(p)
fam = json.load(open(AQUI / "assets_familias.json"))
ja = {a: por_nome[norm(a.rsplit("/", 1)[-1])] for a in fam if norm(a.rsplit("/", 1)[-1]) in por_nome}
print(f"\nnossos 289 assets: {len(ja)} têm arquivo de MESMO NOME já no DAM do global2")
print("   por família nossa:", collections.Counter(fam[a][0] for a in ja).most_common())
for a, ps in list(ja.items())[:6]: print("     ", a.rsplit("/", 1)[-1], "->", [p.replace("/content/dam/macnicaglobal2", "<damg2>") for p in ps][:2])
json.dump(ja, open(AQUI / "assets_ja_no_global2.json", "w"), indent=1)

print("\n== carimbo de edição MANUAL (jcr:lastModified no nó do componente) na nossa árvore")
h = qb(path=T, property="jcr:lastModified", **{"property.operation": "exists", "p.properties": "jcr:path jcr:lastModified jcr:lastModifiedBy sling:resourceType"})
h = [x for x in h if "/jcr:content/" in x["jcr:path"]]
print(f"   {len(h)} nós em {len({x['jcr:path'].split('/jcr:content')[0] for x in h})} páginas")
print("   por dia:", collections.Counter(x.get("jcr:lastModified", "")[:10] for x in h).most_common(6))
print("   por componente:", collections.Counter(str(x.get("sling:resourceType", "")).split("/")[-1] for x in h).most_common(6))
print("   por usuário:", collections.Counter(x.get("jcr:lastModifiedBy", "") for x in h).most_common(4))
print("   páginas:", collections.Counter(x["jcr:path"].split("/jcr:content")[0][len(T):] for x in h).most_common(12))
