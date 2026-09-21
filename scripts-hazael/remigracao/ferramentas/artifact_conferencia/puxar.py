"""SOMENTE LEITURA: baixa jcr:content.20.json das duas árvores para cache local."""
import os as _os
PASTA_TRABALHO = _os.environ.get("CONF_SP") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_trabalho")
_os.makedirs(PASTA_TRABALHO, exist_ok=True)

import sys, os, json, hashlib, time
sys.path.insert(0,'/home/hazael/projects/migration_scripts/scripts-hazael')
sys.path.insert(0,'/home/hazael/projects/migration_scripts/scripts-bruno')
from aem_lib import build_session, CONFIG

SP = PASTA_TRABALHO + ""
s, tr = build_session(verbose=False)
B = CONFIG["base_url"]

def query(root):
    u = (B + "/bin/querybuilder.json?path=" + root +
         "&type=cq:Page&p.limit=-1&p.hits=selective&p.properties=jcr:path")
    r = s.get(u, timeout=60)
    return sorted(h["jcr:path"] for h in r.json()["hits"])

def puxar(paths, destino):
    os.makedirs(destino, exist_ok=True)
    ok = falha = 0
    for p in paths:
        f = os.path.join(destino, hashlib.md5(p.encode()).hexdigest() + ".json")
        if os.path.exists(f): ok += 1; continue
        r = s.get(B + p + "/jcr:content.20.json", timeout=45)
        if r.status_code == 200:
            json.dump(r.json(), open(f, "w")); ok += 1
        else:
            falha += 1; print("  ", r.status_code, p)
        time.sleep(0.05)
    return ok, falha

for root, nome in [("/content/copia-teste/americas/mai/en/products/semiconductors-remigration", "remig"),
                   ("/content/macnicaglobal2/americas/mai/en/products/semiconductors", "g2")]:
    ps = query(root)
    json.dump(ps, open(f"{SP}/{nome}_paths.json", "w"))
    ok, falha = puxar(ps, f"{SP}/{nome}cache")
    print(f"{nome}: {len(ps)} páginas, {ok} baixadas, {falha} falhas")
