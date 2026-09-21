import os as _os
PASTA_TRABALHO = _os.environ.get("CONF_SP") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_trabalho")
_os.makedirs(PASTA_TRABALHO, exist_ok=True)

import sys, json, hashlib, os, csv, re
sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/ferramentas")
import fundo_grupo as FG
SP = PASTA_TRABALHO + ""
RAIZ = "/home/hazael/projects/migration_scripts/scripts-hazael/remigracao"
REM = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
GWI = "/content/macnicagwi/americas/mai/en/products/semiconductors"
HERO = {"textwithimage", "image", "carousel", "embed"}
paths = json.load(open(SP + "/remig_paths.json"))
arq = json.load(open(RAIZ + "/dados/arquetipos.json"))
# mapeamento destino -> origem (o driver normaliza nomes; o CSV tem o par real)
mapa = {r["destino"]: r["origem"] for r in csv.DictReader(open(RAIZ + "/dados/remigracao_atual.csv"))}
# páginas já conferidas na tela
# "vista" = só o que está sob um título "Vistas…" do CONFERIDAS.md. O arquivo também tem a
# seção "Faltam (nenhum olho até hoje)": ler todo caminho entre crases marcava 130 de 135.
conferidas, _secao = set(), ""
for _ln in open(RAIZ + "/CONFERIDAS.md"):
    if _ln.startswith("## "): _secao = _ln[3:].strip().lower()
    for _p in re.findall(r"`(/[^`\s]+)`", _ln):
        if _secao and not _secao.startswith("faltam"): conferidas.add(_p.rstrip("/"))
# páginas com o fundo cinza da R53 (lista do Hazael), pelo caminho do GWI
fundo_lista = {l.split("#")[0].split()[0] for l in open(RAIZ + "/dados/fundo_cinza_paginas.txt") if l.split("#")[0].strip()}
def load(p):
    f = os.path.join(SP + "/remigcache", hashlib.md5(p.encode()).hexdigest() + ".json")
    return json.load(open(f)) if os.path.exists(f) else None
linhas = []
for p in paths:
    rel = p[len(REM):] or "/"
    origem = mapa.get(p) or (GWI + rel if rel != "/" else GWI)
    d = load(p) or {}
    cont = d.get("root", {}).get("container") or {}
    secs = [v for k, v in cont.items() if isinstance(v, dict) and k != "cq:responsive"]
    bandas = sum(1 for s in secs if s.get("backgroundColor"))
    vered = "sem spec"; clean = False; share = set()
    for s in secs:
        t = {r for r, _ in FG.blocos(s, [])}
        if t & {"table", "tabs"}:
            c = []
            if t & HERO: c.append("herói")
            if t & {"experiencefragment", "form"}: c.append("CTA")
            if not c: clean = True
            else: share.update(c)
    if clean: vered = "pintável já"
    elif share: vered = "divide com " + "+".join(sorted(share, reverse=True))
    a = arq.get(origem, "")
    linhas.append({
        "rel": rel, "dest": p, "orig": origem,
        "arq": a.split(".")[0] if a else "", "arqNome": a,
        "secoes": len(secs), "bandas": bandas, "spec": vered,
        "titulo": d.get("jcr:title", ""),
        "conferida": rel.rstrip("/") in conferidas,
        "fundo": origem[len(GWI):] in fundo_lista,
    })
json.dump(linhas, open(SP + "/paginas.json", "w"), ensure_ascii=False, indent=0)
from collections import Counter
print(f"{len(linhas)} páginas")
print("arquétipos:", dict(Counter(l['arq'] for l in linhas)))
print("conferidas:", sum(l['conferida'] for l in linhas))
print("spec:", dict(Counter(l['spec'] for l in linhas)))
print("origem via CSV:", sum(1 for l in linhas if l['dest'] in mapa), " via substituição:", sum(1 for l in linhas if l['dest'] not in mapa))
print("exemplo:", json.dumps(linhas[3], ensure_ascii=False))
