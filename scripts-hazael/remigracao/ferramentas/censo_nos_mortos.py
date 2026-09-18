#!/usr/bin/env python3
"""
Censo de nós da página FORA das regiões `editable` da structure do template.
SOMENTE LEITURA.

Em template editável do AEM, um container travado renderiza os filhos da
STRUCTURE; da página só entra o que estiver sob um nó `editable=true`. Nó da
página fora dessas regiões existe no JCR e nunca chega à tela (R9 em
REGRAS-disposicao.md). Este script lista, por página, esses nós e diz se têm
conteúdo — é o que decide se a migração ressuscitaria algo invisível.

COMO RODAR (da pasta scripts-hazael, com o .env da raiz preenchido)
  python3 remigracao/ferramentas/censo_nos_mortos.py                 # escopo todo
  python3 remigracao/ferramentas/censo_nos_mortos.py --so /analog-devices
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts-bruno"))
from aem_lib import CONFIG, build_session, crawl_tree, get_json  # noqa: E402
import aem_layout as AL  # noqa: E402

GWI_ROOT = "/content/macnicagwi/americas/mai/en/products/semiconductors"


def editaveis(struct):
    ed, todos = set(), set()

    def walk(n, p):
        for k, v in n.items():
            if not isinstance(v, dict) or k == "cq:responsive":
                continue
            cp = f"{p}/{k}"
            todos.add(cp)
            if str(v.get("editable", "")).lower() == "true":
                ed.add(cp)
            walk(v, cp)
    walk(struct.get("root", {}), "root")
    return ed, todos


def mortos(jcr, ed, todos):
    out = []

    def walk(n, p):
        for k, v in n.items():
            if not isinstance(v, dict) or k == "cq:responsive":
                continue
            cp = f"{p}/{k}"
            if cp in ed:
                continue
            if cp in todos:
                walk(v, cp)
                continue
            out.append((cp, AL.rt_of(v) or "", AL.tem_conteudo_renderizavel(v)))
    walk(jcr.get("root", {}), "root")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--origem", default=GWI_ROOT)
    ap.add_argument("--so", default=None)
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    args = ap.parse_args()

    session, auth = build_session(verbose=False)
    paginas = crawl_tree(session, args.base_url, args.origem, auth,
                         only_pages=True, quiet=True)
    if args.so:
        alvo = args.origem.rstrip("/") + "/" + args.so.strip("/")
        paginas = [p for p in paginas if p == alvo or p.startswith(alvo + "/")]

    cache, por_tipo, com_conteudo = {}, Counter(), 0
    for origem in paginas:
        jcr, st = get_json(session, f"{args.base_url}{origem}/jcr:content.infinity.json", auth)
        if st != 200 or not isinstance(jcr, dict):
            print(f"  [erro {st}] {origem}")
            continue
        tpl = jcr.get("cq:template") or ""
        if tpl not in cache:
            struct, st2 = get_json(session, f"{args.base_url}{tpl}/structure/jcr:content.infinity.json", auth)
            cache[tpl] = editaveis(struct if st2 == 200 and isinstance(struct, dict) else {})
        ed, todos = cache[tpl]
        m = [x for x in mortos(jcr, ed, todos) if x[2]]
        if m:
            com_conteudo += 1
            print(f"  {origem[len(args.origem):] or '/'}  [{tpl.rsplit('/', 1)[-1]}]")
            for cp, rt, _ in m:
                por_tipo[(tpl.rsplit('/', 1)[-1], rt.rsplit('/', 1)[-1])] += 1
                print(f"      {cp}  [{rt.rsplit('/', 1)[-1]}]")
    print(f"\n  páginas: {len(paginas)}   com nó morto COM conteúdo: {com_conteudo}")
    for (tpl, rt), n in por_tipo.most_common():
        print(f"    {n:4}  {tpl} :: {rt}")
    print("\n  regiões editáveis por template:")
    for tpl, (ed, _t) in cache.items():
        print(f"    {tpl.rsplit('/', 1)[-1]}: {sorted(ed)}")


if __name__ == "__main__":
    main()
