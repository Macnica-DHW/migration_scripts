#!/usr/bin/env python3
"""censo_mobile_jcr.py <raiz> [--saida nome] [--pular FAMÍLIA ...] [--incluir-testes] — as duas causas CONHECIDAS de
página não-pronta para celular, lidas no JCR de toda página VIVA sob a raiz. SOMENTE LEITURA (só GET).

  A. flexcontainer com BOTÃO dentro e sem 【Design for SP】 (1 Column 1719484596357 / 2 Columns 1719484597737):
     as colunas não empilham abaixo de 1050px — o 2º botão sai da tela (tq-systems, 21/09/2026).
  B. container filho direto de root/container com `cq:responsive/default` de largura < 12 e SEM variante `phone`:
     a grade estreita vale também no celular e espreme o corpo inteiro.
  C. (informativo) flexcontainer SEM botão e sem Design for SP — colunas de texto/imagem que também não empilham.

Fica fora: página soft-deleted; página de TESTE, ou seja, com um trecho do caminho que é/começa/termina com "test"
ou "testing" como palavra (test-277-…, sony-test, anion-test-folder, testing-properties). "latest", "contest" etc.
NÃO contam como teste. --incluir-testes desliga esse filtro.
--pular FAMÍLIA …: pula as famílias (1º nível sob a raiz) cujo nome COMEÇA com um dos valores. Nada é pulado por
padrão. Em 21/09 a rodada pulou `tq-systems*`; hoje a tq-systems do global2 tem 143 páginas da whitelist, e pular
sem pedir esconde um terço do escopo. O resumo sempre diz quantas páginas ficaram fora e por quê.
Não substitui a medição na tela (conferir_mobile.py): pega só o que já se sabe procurar.

    python3 remigracao/ferramentas/censo_mobile_jcr.py /content/macnicaglobal2/americas/mai/en/products/boards-modules
    python3 remigracao/ferramentas/censo_mobile_jcr.py <raiz> --pular tq-systems --saida boards-sem-tq
"""
import argparse, collections, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "golive"))
from _comum import BASE, DADOS, ler, sessao  # noqa: E402

RT_FLEX = "macnicaglobal2/components/content/flexcontainer"
RT_BOTAO = "macnicaglobal2/components/content/button"
RT_CONTAINER = "macnicaglobal2/components/content/container"
SP = {"1719484596357", "1719484597737"}
TESTE = re.compile(r"(^|-)test(ing)?(-|$)", re.I)       # "test" como palavra num trecho do caminho, não "latest"


def eh_teste(rel):
    return any(TESTE.search(seg) for seg in rel.strip("/").split("/"))


def qb(**kw):
    kw.setdefault("p.limit", "-1"); kw.setdefault("p.hits", "selective")
    return sessao.get(BASE + "/bin/querybuilder.json", params=kw, timeout=400).json()["hits"]


def ids(v):
    return set(v if isinstance(v, list) else [v] if isinstance(v, str) else [])


def conta(no, rt):
    return sum((v.get("sling:resourceType") == rt) + conta(v, rt) for v in no.values() if isinstance(v, dict))


def paginas_vivas(raiz, pular=(), incluir_testes=False):
    """Páginas do escopo: vivas, sem as famílias de `pular` (prefixo) e, salvo pedido, sem páginas de teste.
    Devolve também quantas ficaram fora e por quê — nada é pulado em silêncio."""
    pgs = qb(path=raiz, type="cq:Page", **{"p.properties": "jcr:path jcr:content/deleted jcr:content/deletedBy"})
    fam = lambda p: (p[len(raiz):].strip("/").split("/")[0] or "(landing)")
    vivas, fora = set(), collections.Counter()
    for x in pgs:
        p, c = x["jcr:path"], x.get("jcr:content") or {}
        if c.get("deleted") or c.get("deletedBy"):
            fora["soft-deleted"] += 1
        elif any(fam(p).lower().startswith(f.lower()) for f in pular):
            fora[f"família pulada ({fam(p)})"] += 1
        elif not incluir_testes and eh_teste(p[len(raiz):]):
            fora["página de teste"] += 1
        else:
            vivas.add(p)
    return vivas, fam, fora


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz")
    ap.add_argument("--saida", help="sufixo do JSON em dados/golive (padrão: último trecho da raiz)")
    ap.add_argument("--pular", nargs="+", default=[], metavar="FAMÍLIA",
                    help="famílias (1º nível sob a raiz) a pular, por prefixo do nome; padrão: nenhuma")
    ap.add_argument("--incluir-testes", action="store_true", help="não pular páginas de teste")
    args = ap.parse_args()
    raiz = args.raiz.rstrip("/")
    saida = args.saida or raiz.rsplit("/", 1)[-1]
    vivas, fam, fora = paginas_vivas(raiz, args.pular, args.incluir_testes)
    flex = [x["jcr:path"] for x in qb(path=raiz, property="sling:resourceType", **{"property.value": RT_FLEX, "p.properties": "jcr:path"})]
    flex = [n for n in flex if n.split("/jcr:content")[0] in vivas]

    def um_flex(no):
        st, j = ler(no, ".infinity.json")
        if st != 200:
            return no, None, 0, st
        return no, ids(j.get("cq:styleIds")), conta(j, RT_BOTAO), st
    with ThreadPoolExecutor(6) as ex:
        fl = list(ex.map(um_flex, flex))

    def um_corpo(p):
        st, j = ler(p + "/jcr:content/root/container", ".3.json")
        ach = []
        for k, v in (j or {}).items():
            if isinstance(v, dict) and v.get("sling:resourceType") == RT_CONTAINER:
                resp = v.get("cq:responsive") or {}; d = resp.get("default") or {}
                if (str(d.get("width", "12")) != "12" or str(d.get("offset", "0")) != "0") and "phone" not in resp:
                    ach.append((k, d.get("width"), d.get("offset")))
        return p, st, ach
    with ThreadPoolExecutor(6) as ex:
        corpos = list(ex.map(um_corpo, sorted(vivas)))

    A = [(n, s, b) for n, s, b, st in fl if s is not None and b and not (s & SP)]
    C = [(n, s) for n, s, b, st in fl if s is not None and not b and not (s & SP)]
    B = [(p, a) for p, st, a in corpos if a]
    erros = [(n, st) for n, s, b, st in fl if s is None] + [(p, st) for p, st, a in corpos if st not in (200, 404)]
    pA, pB, pC = {n.split("/jcr:content")[0] for n, _, _ in A}, {p for p, _ in B}, {n.split("/jcr:content")[0] for n, _ in C}
    print(f"{raiz}\n  {len(vivas)} páginas vivas no escopo; {len(flex)} flexcontainers nelas; erros de leitura: {len(erros)} {erros[:3]}")
    print(f"  fora do escopo: {sum(fora.values())} " + (str(dict(fora)) if fora else ""))
    print(f"  A. botões lado a lado no celular     : {len(A):4} flexcontainers em {len(pA):4} páginas")
    print(f"  B. corpo em grade estreita sem phone : {len(B):4} páginas")
    print(f"  C. colunas SEM botão que não empilham: {len(C):4} flexcontainers em {len(pC):4} páginas")
    print(f"\n  {'família':30} {'vivas':>5} {'A':>5} {'B':>5} {'C':>5}")
    for f in sorted({fam(p) for p in vivas}):
        v = [p for p in vivas if fam(p) == f]
        print(f"  {f[:30]:30} {len(v):5} {sum(p in pA for p in v):5} {sum(p in pB for p in v):5} {sum(p in pC for p in v):5}")
    print("\n  botões por flexcontainer em A:", dict(collections.Counter(b for _, _, b in A)), "| styles:", collections.Counter(tuple(sorted(s)) for _, s, _ in A).most_common(4))
    print("  grades em B:", collections.Counter((w, o) for _, a in B for _, w, o in a).most_common(5))
    json.dump({"raiz": raiz, "pular": args.pular, "incluir_testes": args.incluir_testes, "fora": dict(fora),
               "vivas": sorted(vivas), "A": [n for n, _, _ in A], "B": [[p, x] for p, x in B], "C": [n for n, _ in C]},
              open(DADOS / f"censo_mobile_jcr_{saida}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
