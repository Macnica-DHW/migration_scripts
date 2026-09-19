#!/usr/bin/env python3
"""
Vão vertical ESTRUTURAL entre componentes consecutivos, calculado do payload — OFFLINE.

Neste design system não há margem entre irmãos: o vão entre dois componentes
é a soma dos paddings dos containers que se fecham e se abrem entre eles, mais
a margem própria de alguns componentes. Dá para calcular sem renderizar — e,
portanto, comparar duas versões do motor sobre as 136 páginas antes de gravar
(o "medir em lote antes/depois" que o aberto G pedia).

  padding T/B do container (desktop):  padrão 50 | Small 30 | Large 70 | None 0
  margem própria:  .cmp-table 20/20   .cmp-textwithimage 30/30
                   .link-button 40/0  ul.cmp-list__list 55/55  .anchor-link__list 0/60

Não é pixel de tela (ignora padding interno de título, line-height, imagem):
serve para COMPARAR versões e achar fronteira cara, não para substituir o
measure.py.

COMO RODAR (de scripts-hazael/)
  python3 remigracao/ferramentas/vaos_estruturais.py --cache <jcr_cache.pkl>                  # histograma do motor atual
  python3 remigracao/ferramentas/vaos_estruturais.py --cache <pkl> --antes /tmp/antes.py      # antes x depois, por transição
  python3 remigracao/ferramentas/vaos_estruturais.py --cache <pkl> --ver /altera/agilex       # a página, componente a componente
"""
import argparse, collections, copy, importlib.util, pickle, re, sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))

PAD = {"1717498052331": 30, "1717498056876": 0, "1717498050826": 70}
MARGEM = {"table": (20, 20), "textwithimage": (30, 30), "button": (40, 0), "list": (55, 55), "anchorlink": (0, 60)}
CONTAINERS = ("container", "flexcontainer", "flexcontaineritem", "responsivegrid", "tabs")


def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def montar(AL, j, o):
    page = AL.extract_tree(copy.deepcopy(j), o)
    if hasattr(AL, "inserir_titulo_da_pagina"):
        AL.inserir_titulo_da_pagina(page, o)
    elif AL.precisa_title_vazio(page):
        cab = AL.Section(o, -1, role="header"); cab.pad_tb = "small"
        l = AL.Row("single"); c = AL.Column(o, width=12); c.blocks = [AL.Block("title_vazio", o)]
        l.columns = [c]; cab.rows = [l]; page.sections.insert(0, cab)
    for b in page.blocks:
        if b.kind in ("related", "productlist") and not b.props.get("pages"):
            b.props["pages"] = ["/x/placeholder"]
    from aem_lib import CONFIG
    payload, _ = AL.build_layout_payload(page, link_de=CONFIG['gwi_prefix'],
                                         link_para=CONFIG['global2_prefix'],
                                         reescrever_listas=False)
    return payload


def arvore(payload):
    """payload achatado -> {caminho: {'rt', 'styles', 'filhos': [...]}} na ordem de emissão."""
    nos = {}
    for k in payload:
        if not k.endswith("/sling:resourceType"):
            continue
        p = k[:-len("/sling:resourceType")]
        nos[p] = {"rt": payload[k].rsplit("/", 1)[-1], "filhos": [],
                  "styles": [x for x in (payload.get(p + "/cq:styleIds") or []) if x],
                  "rotulo": re.sub(r"<[^>]+>", " ", str(payload.get(p + "/jcr:title") or payload.get(p + "/text") or ""))[:40].strip()}
    for p in nos:
        pai = p.rsplit("/", 1)[0]
        if pai in nos:
            nos[pai]["filhos"].append(p)
    return nos


def vaos(payload):
    """[(rt_anterior, rt, vão, rótulo)] em ordem de documento. Coluna de flex: só a 1ª conta na vertical."""
    nos = arvore(payload)
    raiz = "jcr:content/root/container"
    out, estado = [], {"ant": None, "pend": 0}

    def pad(n):
        if n["rt"] != "container":
            return 0
        for s in n["styles"]:
            if s in PAD:
                return PAD[s]
        return 50

    def anda(p, topo=False):
        n = nos[p]
        if n["rt"] in CONTAINERS:
            if not topo:
                estado["pend"] += pad(n)
            filhos = n["filhos"]
            if n["rt"] == "flexcontainer":
                filhos = filhos[:1]          # itens lado a lado: a vertical é a do 1º
            if n["rt"] == "tabs":
                filhos = filhos[:1]          # só o painel aberto
            for f in filhos:
                anda(f)
            if not topo:
                estado["pend"] += pad(n)
            return
        mt, mb = MARGEM.get(n["rt"], (0, 0))
        if estado["ant"] is not None:
            out.append((estado["ant"], n["rt"], estado["pend"] + mt, n["rotulo"]))
        estado["ant"], estado["pend"] = n["rt"], mb

    if raiz in nos:
        anda(raiz, topo=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--antes", help=".py com a versão ANTIGA do motor, para comparar")
    ap.add_argument("--depois", default=str(_RAIZ / "scripts-bruno" / "aem_layout.py"))
    ap.add_argument("--ver", nargs="*", default=[])
    a = ap.parse_args()
    jcrs = pickle.load(open(a.cache, "rb"))
    versoes = [("depois", carregar("al_new", a.depois))]
    if a.antes:
        versoes.insert(0, ("antes", carregar("al_old", a.antes)))
    hist = {v: collections.Counter() for v, _ in versoes}
    trans = {v: collections.defaultdict(list) for v, _ in versoes}
    for o, j in jcrs.items():
        rel = o.split("semiconductors", 1)[1] or "/"
        for v, AL in versoes:
            vs = vaos(montar(AL, j, o))
            for ant, rt, g, rot in vs:
                hist[v][g] += 1
                trans[v][(ant, rt)].append(g)
            if any(rel.endswith(x) for x in a.ver):
                print(f"\n##### {rel}  [{v}]")
                for ant, rt, g, rot in vs:
                    print(f"   {g:4}px  {ant:>14} -> {rt:14} {rot}")
    print("\nHISTOGRAMA do vão estrutural (px: quantas transições)")
    todos = sorted(set().union(*[set(h) for h in hist.values()]))
    print("   px   " + "  ".join(f"{v:>7}" for v, _ in versoes))
    for g in todos:
        print(f"  {g:4}  " + "  ".join(f"{hist[v][g]:7}" for v, _ in versoes))
    print("\nPOR TRANSIÇÃO (n, mediana, máx)")
    chaves = sorted(set().union(*[set(t) for t in trans.values()]), key=lambda k: -max(len(trans[v].get(k, [])) for v, _ in versoes))
    for k in chaves[:40]:
        lin = f"  {k[0]:>14} -> {k[1]:14}"
        for v, _ in versoes:
            xs = sorted(trans[v].get(k, []))
            lin += f"   {v}: n={len(xs):4} med={xs[len(xs)//2] if xs else '-':>4} max={xs[-1] if xs else '-':>4}"
        print(lin)


if __name__ == "__main__":
    main()
