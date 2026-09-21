"""XF no global2, grupos do usuário, e mapa asset->família. SOMENTE LEITURA."""
import csv, json, re, sys, collections
from pathlib import Path
from urllib.parse import quote, unquote
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"; G = "/content/macnicaglobal2/americas/mai/en/products/semiconductors"
def qb(**kw):
    kw.setdefault("p.limit", "-1"); kw.setdefault("p.hits", "selective")
    return s.get(BASE + "/bin/querybuilder.json", params=kw, timeout=120).json()
print("== grupos do usuário do cookie")
r = s.get(BASE + "/libs/granite/security/currentuser.json", params={"props": "declaredMemberOf,memberOf"}, timeout=40)
j = r.json(); print("  ", [m.get("authorizableId") for m in (j.get("memberOf") or j.get("declaredMemberOf") or [])][:25])
print("\n== XFs que as páginas do global2/semiconductors embutem")
h = qb(path=G, property="fragmentVariationPath", **{"property.operation": "exists", "p.properties": "jcr:path fragmentVariationPath"})["hits"]
print("  ", collections.Counter(x.get("fragmentVariationPath") for x in h).most_common(6) or "NENHUM")
print("\n== e no global2 americas/mai/en inteiro")
h = qb(path="/content/macnicaglobal2/americas/mai/en", property="fragmentVariationPath", **{"property.operation": "exists", "p.properties": "jcr:path fragmentVariationPath"})["hits"]
print("  ", collections.Counter(x.get("fragmentVariationPath") for x in h).most_common(8) or "NENHUM")
print("\n== resourceType / template do jcr:content de XF: global2 x nosso")
for p in ("/content/experience-fragments/macnicaglobal2/americas/mai/en/footer", "/content/experience-fragments/copia-teste/americas/mai/en/site/products-contact-block"):
    r = s.get(BASE + p + ".3.json", timeout=40).json()
    print("  ", p.split("experience-fragments")[1], "| allowedTemplates:", r.get("jcr:content", {}).get("cq:allowedTemplates"))
    for k, v in r.items():
        if isinstance(v, dict) and v.get("jcr:primaryType") == "cq:Page":
            c = v.get("jcr:content", {}); print(f"       {k}: rt={c.get('sling:resourceType')} template={c.get('cq:template')} variant={c.get('cq:xfVariantType')}")
for p in ("/content/experience-fragments/macnicaglobal2/americas/mai/en", "/content/experience-fragments/macnicaglobal2/americas/mai", "/content/experience-fragments/macnicaglobal2"):
    r = s.get(BASE + p + ".1.json", timeout=40).json(); print("   allowedTemplates em", p.split("experience-fragments")[1], "=", r.get("cq:allowedTemplates"), "|", (r.get("jcr:content") or {}).get("cq:allowedTemplates"), "| tipo:", r.get("jcr:primaryType"))

print("\n== nossos assets: de que pasta vêm e quantas FAMÍLIAS usam cada um")
L = [l for l in csv.DictReader(open(Path(__file__).resolve().parents[2] / "dados" / "links" / "refs.csv")) if l["classe"] in ("DAM-copia-teste", "DAM-gwi")]
fam_de = collections.defaultdict(set)
for l in L: fam_de[unquote(l["url"])].add((l["pagina"][len(T):].strip("/").split("/")[0]) or "(landing)")
print("   assets distintos:", len(fam_de), "| usados por 1 família:", sum(1 for v in fam_de.values() if len(v) == 1), "| por 2+:", sum(1 for v in fam_de.values() if len(v) > 1))
print("   compartilhados:", [(a.rsplit('/',1)[-1], sorted(v)) for a, v in fam_de.items() if len(v) > 1][:8])
print("   por pasta de origem:", collections.Counter(re.sub(r"^/content/dam/(copia-teste|macnicagwi)/americas/mai/public/en/", r"\1:", a).rsplit("/", 1)[0] for a in fam_de).most_common(12))
print("   por extensão:", collections.Counter(a.rsplit(".", 1)[-1].lower() for a in fam_de).most_common())
json.dump({a: sorted(v) for a, v in fam_de.items()}, open(Path(__file__).resolve().parents[2] / "dados" / "golive" / "assets_familias.json", "w"), indent=1)
