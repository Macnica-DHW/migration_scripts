"""DAM, XF e permissões do lado global2. SOMENTE LEITURA."""
import csv, json, re, sys, collections
from pathlib import Path
from urllib.parse import quote, unquote
R = Path("/home/hazael/projects/migration_scripts")
sys.path.insert(0, str(R / "scripts-hazael")); sys.path.insert(0, str(R / "scripts-bruno"))
from aem_lib import CONFIG, build_session
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE)
s, _ = build_session()
def g(p, suf=".1.json"):
    r = s.get(BASE + quote(unquote(p), safe="/:") + suf, timeout=60, allow_redirects=False)
    try: return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError: return r.status_code, None
def filhos(p):
    st, j = g(p)
    return st, {k: v.get("jcr:primaryType") for k, v in (j or {}).items() if isinstance(v, dict) and k not in ("jcr:content", "rep:policy")}
print("== quem sou eu"); st, j = g("/libs/granite/security/currentuser", ".json"); print("  ", st, (j or {}).get("authorizableId"), (j or {}).get("home"))
print("\n== privilégios desta sessão (privileges-info), se o endpoint existir")
for p in ("/content/copia-teste/americas/mai/en/products/semiconductors-remigration", "/content/macnicaglobal2/americas/mai/en/products/semiconductors",
          "/content/macnicaglobal2/americas/mai/en/products/semiconductors/canon", "/content/dam/copia-teste/americas/mai", "/content/dam/macnicaglobal2/americas/mai/en/products/semiconductors",
          "/content/experience-fragments/macnicaglobal2/americas/mai/en/site", "/content/experience-fragments/copia-teste/americas/mai/en/site"):
    st, j = g(p, ".privileges-info.json"); print(f"   {st} {p}\n        {j}")
print("\n== DAM global2: árvore até semiconductors")
for p in ("/content/dam/macnicaglobal2", "/content/dam/macnicaglobal2/americas", "/content/dam/macnicaglobal2/americas/mai", "/content/dam/macnicaglobal2/americas/mai/en",
          "/content/dam/macnicaglobal2/americas/mai/en/products", "/content/dam/macnicaglobal2/americas/mai/en/products/semiconductors", "/content/dam/macnicaglobal2/americas/mai/public"):
    st, f = filhos(p); print(f"   {st} {p.replace('/content/dam/macnicaglobal2','<damg2>')}: {list(f)[:14]}{' …' if len(f) > 14 else ''} ({len(f)})")
for fam in ("canon", "design-gateway", "sony"):
    st, f = filhos(f"/content/dam/macnicaglobal2/americas/mai/en/products/semiconductors/{fam}")
    print(f"   {st} <damg2>/…/semiconductors/{fam}: {collections.Counter(f.values())}  ex: {list(f)[:4]}")
print("\n== XF global2")
for p in ("/content/experience-fragments/macnicaglobal2", "/content/experience-fragments/macnicaglobal2/americas", "/content/experience-fragments/macnicaglobal2/americas/mai", "/content/experience-fragments/macnicaglobal2/americas/mai/en", "/content/experience-fragments/macnicaglobal2/americas/mai/en/site", "/content/experience-fragments/copia-teste/americas/mai/en/site"):
    st, f = filhos(p); print(f"   {st} {p.replace('/content/experience-fragments','<xf>')}: {list(f)[:20]} ({len(f)})")
