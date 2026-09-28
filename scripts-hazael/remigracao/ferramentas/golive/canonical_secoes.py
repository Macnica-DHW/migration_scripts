#!/usr/bin/env python3
"""canonical_secoes.py <seção>... [--executar] [--render] — "SEO > Canonical Url" (`cq:canonicalUrl`) nas páginas
NOSSAS (criadas OU editadas por último pelo Valter ou pelo Bruno) de seções quaisquer do global2/…/mai/en.

Pedido do Hazael em 21/09/2026: "for pages with Valter and Bruno as authors in global2's solutions, boards-modules,
semiconductors and services, are there pages missing their SEO Canonical Url? If yes, they should be set."

Regra do site (576 das 584 páginas do global2 que têm o campo): canonical = o próprio caminho JCR, sem `.html`.
Ausente NÃO é defeito de tela (o AEM renderiza a própria página), é convenção; ERRADO é que tira do índice.

Sem `--executar` é SOMENTE LEITURA: classifica cada página e grava dados/golive/canonical_secoes_<data>.csv.
  nossa      = jcr:createdBy ou cq:lastModifiedBy em NOS; ou exceção listada em EXCECOES (com o porquê)
  pulada     = soft-deleted (`deleted`), página de redirect, ou de outra pessoa (sai no CSV, nunca é gravada)
`--executar` grava `cq:canonicalUrl` = o próprio caminho SÓ nas nossas onde falta, uma a uma: relê a página ao
vivo, backup do jcr:content inteiro em dados/golive/backup_canonical/, POST pela trava do aem_lib com o caminho
EXATO em allow_extra, relê e confere. Nenhum POST sai para URL com `macnicagwi`.
`--render` baixa o HTML (wcmmode=disabled) das nossas e confere o canonical renderizado: 1 no <head> = a própria
página + .html; o que houver no <body> é o 2º canonical do XF embutido (item em aberto, não é daqui).

  python3 canonical_secoes.py solutions products/boards-modules products/semiconductors services
  python3 canonical_secoes.py solutions services --executar --render
"""
import argparse
import csv
import datetime
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, contas_nossas, post_node  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
BACKUPS = DADOS / "backup_canonical"
MAI = "/content/macnicaglobal2/americas/mai/en"
# Contas "nossas" (aem_lib.CONTAS_NOSSAS: valter.toffolo e bruno.jaques). Padrão: as duas; quem roda escolhe na
# linha de comando com AEM_CONTAS_NOSSAS=valter|bruno|ambas.
NOS = contas_nossas()
# páginas cujo último editor virou `reference-adjustment-service` no move /technology -> /solutions (21/09/2026);
# antes do move o editor era o Valter (dados desta sessão: technology_paginas.json + árvore impressa)
EXCECOES = {f"{MAI}/solutions": "casca do ohashi preenchida pelo Valter (direto.py); editor virou reference-adjustment-service no move",
            f"{MAI}/solutions/imaging-and-vision": "casca do ohashi preenchida pelo Valter (direto.py, 6 backups); editor virou reference-adjustment-service no move"}
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE   # cookie só vai para o author
sessao, auth = build_session(prompt_if_missing=False, verbose=False)


def u(path, sufixo=""):
    return BASE + quote(path, safe="/:") + sufixo


def ler(path, sufixo=".json"):
    r = sessao.get(u(path, sufixo), timeout=120, allow_redirects=False)
    try:
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError:
        return r.status_code, None


def conteudo_inteiro(pagina):
    st, jc = ler(pagina + "/jcr:content", ".infinity.json")
    if not isinstance(jc, dict):                     # HTTP 300: lista de profundidades
        st, jc = ler(pagina + "/jcr:content", ".50.json")
    return st, jc


def paginas(secao):
    raiz = f"{MAI}/{secao.strip('/')}"
    if "macnicagwi" in raiz:
        sys.exit("[erro] seção do GWI")
    r = sessao.get(BASE + "/bin/querybuilder.json", timeout=300, params={
        "path": raiz, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective",
        "p.properties": "jcr:path jcr:createdBy jcr:content/cq:lastModifiedBy jcr:content/cq:canonicalUrl jcr:content/deleted jcr:content/cq:redirectTarget"})
    hits = {h["jcr:path"]: h for h in r.json()["hits"]}
    st, j = ler(raiz, ".1.json")
    if st != 200:
        sys.exit(f"[erro] HTTP {st} em {raiz}")
    hits[raiz] = {"jcr:path": raiz, "jcr:createdBy": j.get("jcr:createdBy"), "jcr:content": j.get("jcr:content") or {}}
    return raiz, hits


def classifica(h):
    p, jc = h["jcr:path"], h.get("jcr:content") or {}
    criador, editor, v = h.get("jcr:createdBy"), jc.get("cq:lastModifiedBy"), jc.get("cq:canonicalUrl")
    if jc.get("deleted"):
        dono = "pulada:soft-deleted"
    elif jc.get("cq:redirectTarget"):
        dono = "pulada:redirect"
    elif criador and criador.endswith("@anionmarketing.com") and editor in NOS:
        dono = "pulada:anion-criou-nos-editamos"          # página da Anion; decisão do Hazael, nunca gravada por aqui
    elif criador in NOS or editor in NOS:
        dono = "nossa"
    elif p in EXCECOES:
        dono = "nossa:excecao"
    else:
        dono = "pulada:outra-pessoa"
    estado = "ausente" if not v else ("ok" if v == p else ("ERRADO-origem" if ("/copia-teste/" in v or "macnicagwi" in v) else "ERRADO-outro"))
    return {"pagina": p, "dono": dono, "criador": criador, "editor": editor, "canonical": v or "", "estado": estado, "acao": "",
            "porque": EXCECOES.get(p, "") if dono == "nossa:excecao" else ""}


def render(p):
    r = sessao.get(u(p, ".html"), params={"wcmmode": "disabled"}, timeout=120, allow_redirects=False)
    h = r.text if r.status_code == 200 else ""
    fim = h.find("</head>")
    can = [(m.start() < fim, re.search(r'href="([^"]*)"', m.group(0)).group(1)) for m in re.finditer(r'<link[^>]+rel="canonical"[^>]*>', h)]
    head, body = [c for e, c in can if e], [c for e, c in can if not e]
    return p, r.status_code, head, body, ("ok" if r.status_code == 200 and head == [p + ".html"] else "DIVERGE")


def gravar(l):
    p = l["pagina"]
    if "macnicagwi" in p or not p.startswith(MAI + "/"):
        return "recusado:fora-do-global2"
    st, h = ler(p, ".1.json")                        # relê AO VIVO imediatamente antes
    if st != 200:
        return f"recusado:HTTP-{st}"
    jc = h.get("jcr:content") or {}
    if jc.get("cq:canonicalUrl"):
        return "pulado:ja-tem:" + jc["cq:canonicalUrl"]
    if jc.get("deleted") or jc.get("cq:redirectTarget"):
        return "pulado:mudou-ao-vivo"
    if str(h.get("jcr:createdBy")).endswith("@anionmarketing.com"):
        return "recusado:pagina-da-anion"
    if not (h.get("jcr:createdBy") in NOS or jc.get("cq:lastModifiedBy") in NOS or p in EXCECOES):
        return "recusado:outra-pessoa-ao-vivo"
    st, inteiro = conteudo_inteiro(p)
    if st != 200 or not isinstance(inteiro, dict) or "root" not in inteiro:
        return f"recusado:backup-HTTP-{st}"
    BACKUPS.mkdir(parents=True, exist_ok=True)
    bk = BACKUPS / (p[len(MAI) + 1:].replace("/", "__") + f"__{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json")
    json.dump({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "pagina": p, "jcr_content": inteiro}, open(bk, "w"), ensure_ascii=False)
    st, txt = post_node(sessao, BASE, f"{p}/jcr:content", {"cq:canonicalUrl": p, "_charset_": "utf-8"}, auth, allow_extra=(f"{p}/jcr:content",))
    if st not in (200, 201):
        return f"FALHA:HTTP-{st}:{txt[:80]}"
    st, dep = ler(p + "/jcr:content", ".json")
    return "gravado" if (dep or {}).get("cq:canonicalUrl") == p else f"FALHA:releitura:{(dep or {}).get('cq:canonicalUrl')}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("secoes", nargs="+")
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    print("EXECUTANDO" if a.executar else "dry-run (somente leitura)")
    linhas = []
    for sec in a.secoes:
        raiz, hits = paginas(sec)
        ls = [classifica(h) for h in sorted(hits.values(), key=lambda h: h["jcr:path"])]
        nossas = [l for l in ls if l["dono"].startswith("nossa")]
        faltam = [l for l in nossas if l["estado"] == "ausente"]
        erradas = [l for l in nossas if l["estado"].startswith("ERRADO")]
        print(f"\n{raiz}: {len(ls)} páginas | nossas {len(nossas)} (soft-deleted {sum(l['dono'] == 'pulada:soft-deleted' for l in ls)}, "
              f"outra pessoa {sum(l['dono'] == 'pulada:outra-pessoa' for l in ls)}, redirect {sum(l['dono'] == 'pulada:redirect' for l in ls)}) "
              f"| nossas SEM canonical: {len(faltam)} | nossas ERRADAS: {len(erradas)}")
        for l in faltam + erradas:
            print(f"   {l['estado']:9} {l['pagina'][len(MAI):]:90} {str(l['criador']).split('@')[0]}/{str(l['editor']).split('@')[0]}"
                  + (f"   [exceção: {l['porque']}]" if l["porque"] else "") + (f"   valor: {l['canonical']}" if l["canonical"] else ""))
        for l in [l for l in ls if l["dono"] == "pulada:anion-criou-nos-editamos"]:
            print(f"   [DECISÃO] {l['pagina'][len(MAI):]} criada por {l['criador']} e editada por {str(l['editor']).split('@')[0]}: página da Anion, NÃO gravada (estado: {l['estado']})")
        linhas += ls
    faltam = [l for l in linhas if l["dono"].startswith("nossa") and l["estado"] == "ausente"]
    print(f"\nTOTAL a gravar: {len(faltam)}")
    if a.executar:
        for l in faltam:
            l["acao"] = gravar(l)
            print(f"   {l['acao']:28} {l['pagina'][len(MAI):]}")
        print("\nresumo:", {k: sum(1 for l in faltam if l["acao"].split(":")[0] == k) for k in {l["acao"].split(":")[0] for l in faltam}})
    if a.render:
        alvo = [l for l in linhas if l["dono"].startswith("nossa") and (a.executar and l["acao"] == "gravado" or not a.executar and l["estado"] == "ausente")]
        print(f"\nrender de {len(alvo)} páginas:")
        with ThreadPoolExecutor(4) as ex:
            for p, st, head, body, ok in ex.map(render, [l["pagina"] for l in alvo]):
                l = next(l for l in linhas if l["pagina"] == p)
                l["render"] = ok; l["render_head"] = " ".join(head); l["render_body"] = " ".join(body)
                print(f"   {ok:8} HTTP {st} head={head} body={len(body)}  {p[len(MAI):]}")
    DADOS.mkdir(parents=True, exist_ok=True)
    saida = DADOS / f"canonical_secoes_{datetime.datetime.now():%Y-%m-%d}.csv"
    with open(saida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["pagina", "dono", "criador", "editor", "canonical", "estado", "acao", "porque", "render", "render_head", "render_body"])
        w.writeheader(); w.writerows(linhas)
    print(f"\ncsv -> {saida}")


if __name__ == "__main__":
    main()
