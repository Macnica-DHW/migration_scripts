#!/usr/bin/env python3
"""
flex_sp_1coluna.py — liga o style 【Design for SP】= "1 Column" nos flexcontainers que seguram BOTÕES, para
o par de botões empilhar no celular. Dry-run por padrão.

Por que existe: em `macnicaglobal2/.../boards-modules/tq-systems` (172 páginas do script antigo) o par
"Contact Us for More Information | Request a Quote" vive num `flexcontainer` só com 【Spacing】= No Spacing
(1718800458698). Sem o "1 Column" (1719484596357 -> classe `sp-flex-direction-column`) as colunas NÃO
empilham abaixo de 1050px: a 375px o 2º botão fica inteiro fora da tela (x=370..715) e a página rola
340–418px de lado — 167 páginas (conferir_mobile.py, 21/09/2026). O CSS do style só vale em
`@media (max-width:1049px)`, então o desktop não muda. Pedido do Hazael em 21/09/2026.

O que grava: SÓ `cq:styleIds` do nó flexcontainer, como String[] (em parte dos nós o script antigo gravou
string solta), mantendo o que já estava e acrescentando o "1 Column". Nada mais na página.

Página soft-deleted (`deleted`/`deletedBy` no jcr:content) fica de fora: em tq-systems são 30 sobras do
clone antigo (nome com maiúscula, gêmea minúscula viva) — inclusive as 28 `mai-page-content` com o corpo
em grade 8/2, as únicas em que só o "1 Column" não bastava (ver grade_phone_12.py).

Travas: só dentro das RAÍZES abaixo (autorização explícita, árvore por árvore); o nó tem de ser
flexcontainer, conter botão e é relido AO VIVO antes de gravar; backup do valor anterior de cada nó em
dados/golive/flex_sp_1coluna_backup_<data>.json; `--restaurar <backup>` devolve tudo.

    python3 flex_sp_1coluna.py <raiz>                           # dry-run: lista
    python3 flex_sp_1coluna.py <raiz> --paginas /a /b --executar
    python3 flex_sp_1coluna.py <raiz> --lista arquivo.txt --executar   # a lista do dry-run
    python3 flex_sp_1coluna.py <raiz> --restaurar dados/golive/flex_sp_1coluna_backup_....json --executar
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "golive"))
from _comum import BASE, DADOS, aborta, ler, sessao, url  # noqa: E402

RAIZES = ("/content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems",)
RT_FLEX = "macnicaglobal2/components/content/flexcontainer"
RT_BOTAO = "macnicaglobal2/components/content/button"
S_SP_1COL = "1719484596357"
S_SP_2COL = "1719484597737"


def lista(v):
    return list(v) if isinstance(v, list) else ([v] if isinstance(v, str) and v else [])


def tem_botao(no):
    return any(isinstance(v, dict) and (v.get("sling:resourceType") == RT_BOTAO or tem_botao(v)) for v in no.values())


def candidatos(raiz):
    h = sessao.get(BASE + "/bin/querybuilder.json", timeout=180, params={
        "path": raiz, "property": "sling:resourceType", "property.value": RT_FLEX,
        "p.limit": "-1", "p.hits": "selective", "p.properties": "jcr:path"}).json()["hits"]
    return sorted(x["jcr:path"] for x in h)


def grava(no, ids):
    r = sessao.post(url(no), timeout=60, data={"cq:styleIds": ids, "cq:styleIds@TypeHint": "String[]", "_charset_": "utf-8"})
    return r.status_code


def main():
    args = sys.argv[1:]
    executar = "--executar" in args
    raiz = args[0].rstrip("/")
    if raiz not in RAIZES:
        aborta(f"raiz não autorizada: {raiz}  (autorizadas: {RAIZES})")

    if "--restaurar" in args:
        bk = json.load(open(args[args.index("--restaurar") + 1]))
        for no, antes in bk["nos"].items():
            if not no.startswith(raiz + "/"):
                aborta(f"backup com nó fora da raiz: {no}")
            print(f"  {no[len(raiz):]}  -> {antes}", "" if not executar else grava(no, lista(antes)))
        print(f"{len(bk['nos'])} nós", "restaurados" if executar else "[dry-run]")
        return

    so = None
    if "--paginas" in args:
        i = args.index("--paginas"); so = {p for p in args[i + 1:] if not p.startswith("--")}
    if "--lista" in args:
        so = {l.split()[0] for l in open(args[args.index("--lista") + 1]) if l.strip() and not l.startswith("#")}

    plano, fora, mortas = {}, [], {}
    for no in candidatos(raiz):
        pag = no.split("/jcr:content")[0][len(raiz):] or "/"
        if so is not None and pag not in so:
            continue
        if pag not in mortas:                       # soft-delete: página invisível no console, com gêmea viva
            _, c = ler(no.split("/jcr:content")[0] + "/jcr:content")
            mortas[pag] = bool(c and (c.get("deleted") or c.get("deletedBy")))
        if mortas[pag]:
            fora.append((pag, "página soft-deleted — não mexo", "")); continue
        st, j = ler(no, ".infinity.json")
        if st != 200 or j.get("sling:resourceType") != RT_FLEX:
            aborta(f"HTTP {st} / tipo inesperado em {no}")
        ids = lista(j.get("cq:styleIds"))
        if not tem_botao(j):
            fora.append((pag, "sem botão dentro", ids)); continue
        if S_SP_1COL in ids:
            fora.append((pag, "já tem 1 Column", ids)); continue
        if S_SP_2COL in ids:
            fora.append((pag, "tem '2 Columns' escolhido por alguém — não mexo", ids)); continue
        plano[no] = (j.get("cq:styleIds"), [x for x in ids if x] + [S_SP_1COL])

    for no, (antes, depois) in plano.items():
        print(f"  {no[len(raiz):]}\n      {antes!r} -> {depois}")
    for f in fora:
        print("  [fica]", *f)
    print(f"\n{len(plano)} flexcontainers em {len({n.split('/jcr:content')[0] for n in plano})} páginas mudam; {len(fora)} ficam")
    if not executar:
        with open(DADOS / "flex_sp_1coluna_dry.txt", "w") as f:
            f.write("".join(sorted({(n.split("/jcr:content")[0][len(raiz):] or "/") + "\n" for n in plano})))
        print("  [dry-run] nada gravado. Lista de páginas em dados/golive/flex_sp_1coluna_dry.txt")
        return

    bk = DADOS / f"flex_sp_1coluna_backup_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json"
    json.dump({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "raiz": raiz,
               "nos": {n: a for n, (a, _) in plano.items()}}, open(bk, "w"), indent=1)
    print(f"  backup -> {bk}")
    falhas = 0
    for no, (_, depois) in plano.items():
        st = grava(no, depois)
        _, j = ler(no)
        certo = st in (200, 201) and j and j.get("cq:styleIds") == depois
        falhas += not certo
        if not certo:
            print(f"  [FALHA] HTTP {st} {no} -> {j and j.get('cq:styleIds')}")
    print(f"  gravados: {len(plano) - falhas}; falhas: {falhas}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
