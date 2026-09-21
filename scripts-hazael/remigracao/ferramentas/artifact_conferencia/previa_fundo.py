"""Prévia (só leitura): sequência de cor por seção que o motor emitiria."""
import os as _os
PASTA_TRABALHO = _os.environ.get("CONF_SP") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_trabalho")
_os.makedirs(PASTA_TRABALHO, exist_ok=True)

import sys, re, json
sys.path.insert(0,"/home/hazael/projects/migration_scripts/scripts-hazael")
sys.path.insert(0,"/home/hazael/projects/migration_scripts/scripts-bruno")
sys.path.insert(0,"/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/ferramentas")
import diff_payload as DP
from aem_lib import build_session, CONFIG
G="/content/macnicagwi/americas/mai/en/products/semiconductors"; SLOT="jcr:content/root/container"
INV=("container","flexcontainer","flexcontaineritem","responsivegrid")
rels=sys.argv[1:]
if rels==["--lista"]:
    rels=[l.split("#")[0].split()[0] for l in open("/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/dados/fundo_cinza_paginas.txt") if l.split("#")[0].strip()]
s,auth=build_session(verbose=False); cd,ca={}, {}
out={}
for rel in rels:
    try:
        payload,cont,page=DP.payload_novo(s,CONFIG["base_url"],auth,G+("" if rel=="/" else rel),cd,ca)
    except Exception as e:
        print(f"[ERRO] {rel}: {type(e).__name__}: {str(e)[:90]}",flush=True); continue
    if payload is None: print(f"[ERRO] {rel}: {page}",flush=True); continue
    secs=[]
    for k in payload:
        m=re.match(re.escape(SLOT)+r"/([^/]+)/sling:resourceType$",k)
        if m and m.group(1) not in secs: secs.append(m.group(1))
    seq=[]
    for sec in secs:
        pre=f"{SLOT}/{sec}/"
        tipos=[str(v).split("/")[-1] for k,v in payload.items() if k.startswith(pre) and k.endswith("/sling:resourceType")]
        nb=sum(1 for t in tipos if t not in INV)
        bg=payload.get(f"{SLOT}/{sec}/backgroundColor")
        tit=next((str(v) for k,v in payload.items() if k.startswith(pre) and k.endswith("/jcr:title") and str(v).strip()),"")
        seq.append(("G" if bg else "W", nb, "xf" if "experiencefragment" in tipos else "", tit[:26]))
    out[rel]=seq
    print(f"\n{rel}   ({len(secs)} seções)\n   "+"  ".join(f"{c}{n}{'['+x+']' if x else ''}" for c,n,x,_ in seq),flush=True)
    if len(rels)<=8:
        for c,n,x,t in seq: print(f"        {c} {n:3} {x:3} {t!r}")
json.dump(out,open(PASTA_TRABALHO + "/previa_fundo.json","w"),ensure_ascii=False)
