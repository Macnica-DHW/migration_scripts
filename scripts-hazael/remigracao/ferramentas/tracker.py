#!/usr/bin/env python3
"""
tracker.py — blacklist/whitelist do site-migration-tracker, sempre com GET FRESCO. SOMENTE LEITURA.

  blacklist = páginas aprovadas (✔) por alguém depois da revisão manual: NENHUM script/agente grava nelas.
  whitelist = o resto do mapa do site (ninguém aprovou ainda); encolhe conforme aprovam — buscar logo antes de agir.

    python3 remigracao/ferramentas/tracker.py status /products/boards-modules/iei /about-us/company-profile
    python3 remigracao/ferramentas/tracker.py listar whitelist --prefixo /products/boards-modules
    python3 remigracao/ferramentas/tracker.py listar blacklist --json /tmp/bl.json
    python3 remigracao/ferramentas/tracker.py resumo

Caminho: relativo a /content/macnicaglobal2/americas/mai/en (ex.: /about-us) ou absoluto (/content/...).
Vai SÓ o MIGRATION_TRACKER_TOKEN (do .env) para o tracker — nunca o cookie do AEM. A trava de escrita do aem_lib
também soma o paginas_protegidas.txt (raiz do projeto): `status` mostra as duas fontes.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import requests

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import _env, carregar_protegidas  # noqa: E402  (importar o aem_lib carrega o .env)

API = "https://site-migration-tracker.mdhw.dev/api"
MAI = "/content/macnicaglobal2/americas/mai/en"


def baixar(lista):
    tok = _env("MIGRATION_TRACKER_TOKEN").strip()
    if not tok:
        sys.exit("MIGRATION_TRACKER_TOKEN vazio no .env — sem ele não há lista (e nada pode ser gravado)")
    r = requests.get(f"{API}/{lista}", headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("count") != len(d.get("pages", [])):
        sys.exit(f"resposta suspeita de /api/{lista}: count={d.get('count')} x {len(d.get('pages', []))} páginas")
    return d


def absoluto(p):
    p = p.strip().rstrip("/")
    if p.startswith("http"):
        p = "/content/" + p.split("/content/", 1)[1]
    p = p.removesuffix(".html").split("?")[0]
    return p if p.startswith("/content/") else MAI + (p if p.startswith("/") else "/" + p)


def status(args):
    bl, wl = baixar("blacklist"), baixar("whitelist")
    print(f"tracker às {bl['generated_at']}: blacklist {bl['count']}, whitelist {wl['count']}")
    B = {p["aem_path"]: p for p in bl["pages"]}
    W = {p["aem_path"]: p for p in wl["pages"]}
    try:
        locais = set(carregar_protegidas())
    except Exception:  # noqa: BLE001
        locais = set()
    for c in map(absoluto, args.caminhos):
        if c in B:
            quem = ", ".join(f"{a['name']} {a['approved_at'][:16]}" for a in B[c].get("approved_by", []))
            st = f"BLACKLIST (aprovada: {quem}) — só leitura"
        elif c in W:
            st = "whitelist (não aprovada) — pode gravar, com backup antes"
        else:
            st = "fora do mapa do site (nem blacklist nem whitelist) — perguntar antes de gravar"
        if c in locais:
            st += "  + está no paginas_protegidas.txt (a trava do aem_lib barra)"
        print(f"  {c[len(MAI):] if c.startswith(MAI) else c}: {st}")


def listar(args):
    d = baixar(args.lista)
    pags = [p for p in d["pages"] if not args.prefixo or p["path"].startswith(args.prefixo)]
    if args.json:
        Path(args.json).write_text(json.dumps({**d, "pages": pags}, indent=1, ensure_ascii=False))
        print(f"{len(pags)} páginas -> {args.json}")
        return
    for p in pags:
        extra = ""
        if args.lista == "blacklist":
            extra = "  [" + ", ".join(f"{a['name']} {a['approved_at'][:10]}" for a in p.get("approved_by", [])) + "]"
        print(f"{p['path']}{extra}")
    print(f"# {len(pags)} de {d['count']} ({d['generated_at']})", file=sys.stderr)


def resumo(args):
    bl, wl = baixar("blacklist"), baixar("whitelist")
    print(f"tracker às {bl['generated_at']}: blacklist {bl['count']} aprovadas, whitelist {wl['count']} não aprovadas")
    sec = collections.Counter()
    for nome, d in (("aprovadas", bl), ("não aprovadas", wl)):
        for p in d["pages"]:
            sec[("/".join(p["path"].split("/")[:3]) or "/", nome)] += 1
    for s in sorted({k[0] for k in sec}):
        print(f"  {s:<55} aprovadas {sec[(s, 'aprovadas')]:>4}   não aprovadas {sec[(s, 'não aprovadas')]:>4}")
    quem = collections.Counter(a["name"] for p in bl["pages"] for a in p.get("approved_by", []))
    print("aprovações por pessoa:", dict(quem))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status")
    s.add_argument("caminhos", nargs="+")
    s.set_defaults(f=status)
    l = sub.add_parser("listar")
    l.add_argument("lista", choices=["blacklist", "whitelist"])
    l.add_argument("--prefixo", help="filtra pelo caminho relativo (ex.: /products/boards-modules)")
    l.add_argument("--json", help="grava a lista (filtrada) neste arquivo em vez de imprimir")
    l.set_defaults(f=listar)
    r = sub.add_parser("resumo")
    r.set_defaults(f=resumo)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
