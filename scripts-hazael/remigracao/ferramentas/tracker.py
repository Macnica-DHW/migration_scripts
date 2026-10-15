#!/usr/bin/env python3
"""
tracker.py — blacklist/whitelist dos site-migration-trackers, sempre com GET FRESCO. SOMENTE LEITURA.

  blacklist = páginas aprovadas (✔) por alguém depois da revisão manual: NENHUM script/agente grava nelas.
  whitelist = o resto do mapa do site (ninguém aprovou ainda); encolhe conforme aprovam — buscar logo antes de agir.

São dois trackers desde 15/10/2026, um por site, com o mesmo token:
  mai  https://site-migration-tracker.mdhw.dev       /content/macnicaglobal2/americas/mai/en/... (533 páginas)
  dhw  https://dhw-site-migration-tracker.mdhw.dev   /content/macnicaglobal2/americas/dhw/...    (321 páginas)

    python3 remigracao/ferramentas/tracker.py status /products/boards-modules/iei /dhw/pt/quem-somos
    python3 remigracao/ferramentas/tracker.py listar whitelist --prefixo /products/boards-modules
    python3 remigracao/ferramentas/tracker.py listar whitelist --site dhw --prefixo /dhw/tq-systems
    python3 remigracao/ferramentas/tracker.py listar blacklist --json /tmp/bl.json
    python3 remigracao/ferramentas/tracker.py resumo                 # os dois trackers (--site mai|dhw: só um)

Caminho: absoluto (/content/...) ou URL; ou relativo como o tracker do site o mostra: /dhw/... é do DHW (relativo
a /content/macnicaglobal2/americas), qualquer outro é do MAI (relativo a /content/macnicaglobal2/americas/mai/en).
`status` acha o site de cada caminho sozinho; `listar` e `--prefixo` usam o caminho relativo do tracker escolhido.
Vai SÓ o MIGRATION_TRACKER_TOKEN (do .env) para os trackers — nunca o cookie do AEM. Os trackers são a ÚNICA
fonte da trava de escrita do aem_lib, que protege a união das duas blacklists (o paginas_protegidas.txt foi
aposentado em 02/10/2026).
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import requests

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import _env  # noqa: E402  (importar o aem_lib carrega o .env)

# site -> (API do tracker, raiz do caminho relativo `path` nas listas dele)
TRACKERS = {
    "mai": ("https://site-migration-tracker.mdhw.dev/api", "/content/macnicaglobal2/americas/mai/en"),
    "dhw": ("https://dhw-site-migration-tracker.mdhw.dev/api", "/content/macnicaglobal2/americas"),
}
MAI = TRACKERS["mai"][1]
DHW = "/content/macnicaglobal2/americas/dhw"
# profundidade das seções do `resumo`: /products/boards-modules no MAI, /dhw/pt/quem-somos no DHW
NIVEL_SECAO = {"mai": 3, "dhw": 4}


def baixar(lista, site="mai"):
    api = TRACKERS[site][0]
    tok = _env("MIGRATION_TRACKER_TOKEN").strip()
    if not tok:
        sys.exit("MIGRATION_TRACKER_TOKEN vazio no .env — sem ele não há lista (e nada pode ser gravado)")
    r = requests.get(f"{api}/{lista}", headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("count") != len(d.get("pages", [])):
        sys.exit(f"resposta suspeita de {api}/{lista}: count={d.get('count')} x {len(d.get('pages', []))} páginas")
    return d


def absoluto(p):
    p = p.strip().rstrip("/")
    if p.startswith("http"):
        p = "/content/" + p.split("/content/", 1)[1]
    p = p.split("?")[0].removesuffix(".html")
    if p.startswith("/content/"):
        return p
    p = p if p.startswith("/") else "/" + p
    if p == "/dhw" or p.startswith("/dhw/"):          # caminho do tracker DHW
        return TRACKERS["dhw"][1] + p
    return MAI + p


def site_de(c):
    """O tracker de um caminho absoluto (fora do DHW, o do MAI, como antes)."""
    return "dhw" if c == DHW or c.startswith(DHW + "/") else "mai"


def relativo(c):
    raiz = TRACKERS[site_de(c)][1]
    return c[len(raiz):] if c.startswith(raiz + "/") else c


def status(args):
    caminhos = [absoluto(c) for c in args.caminhos]
    listas = {}
    for site in sorted({site_de(c) for c in caminhos}, key=list(TRACKERS).index):
        bl, wl = baixar("blacklist", site), baixar("whitelist", site)
        print(f"tracker {site} às {bl['generated_at']}: blacklist {bl['count']}, whitelist {wl['count']}")
        listas[site] = ({p["aem_path"]: p for p in bl["pages"]}, {p["aem_path"]: p for p in wl["pages"]})
    for c in caminhos:
        B, W = listas[site_de(c)]
        if c in B:
            quem = ", ".join(f"{a['name']} {a['approved_at'][:16]}" for a in B[c].get("approved_by", []))
            st = f"BLACKLIST (aprovada: {quem}) — só leitura"
        elif c in W:
            st = "whitelist (não aprovada) — pode gravar, com backup antes"
        else:
            st = "fora do mapa do site (nem blacklist nem whitelist) — perguntar antes de gravar"
        print(f"  {site_de(c)} {relativo(c)}: {st}")


def listar(args):
    d = baixar(args.lista, args.site)
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
    print(f"# {len(pags)} de {d['count']} ({args.site}, {d['generated_at']})", file=sys.stderr)


def resumo(args):
    for site in (TRACKERS if args.site == "todos" else [args.site]):
        bl, wl = baixar("blacklist", site), baixar("whitelist", site)
        print(f"tracker {site} às {bl['generated_at']}: blacklist {bl['count']} aprovadas, "
              f"whitelist {wl['count']} não aprovadas")
        sec = collections.Counter()
        for nome, d in (("aprovadas", bl), ("não aprovadas", wl)):
            for p in d["pages"]:
                sec[("/".join(p["path"].split("/")[:NIVEL_SECAO[site]]) or "/", nome)] += 1
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
    l.add_argument("--site", choices=list(TRACKERS), default="mai", help="qual tracker (padrão: %(default)s)")
    l.add_argument("--prefixo", help="filtra pelo caminho relativo (ex.: /products/boards-modules, /dhw/pt)")
    l.add_argument("--json", help="grava a lista (filtrada) neste arquivo em vez de imprimir")
    l.set_defaults(f=listar)
    r = sub.add_parser("resumo")
    r.add_argument("--site", choices=[*TRACKERS, "todos"], default="todos", help="qual tracker (padrão: %(default)s)")
    r.set_defaults(f=resumo)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
