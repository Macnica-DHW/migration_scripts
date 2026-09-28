"""canonical.py — "SEO > Canonical Url" (`cq:canonicalUrl`) de toda página sob global2/.../semiconductors.

Sem argumento é SOMENTE LEITURA: lê a propriedade de todas as páginas (landing inclusive), classifica e
grava dados/golive/canonical.csv. Regra do site (576 das 584 páginas do global2 que têm o campo): canonical =
o próprio caminho JCR da página, sem `.html` — a mesma do scripts-hazael/aem_fix_canonical.py.

O campo é OPCIONAL: o diálogo diz "If not set the page's url will be its canonical url", e a tela confirma —
com ou sem a propriedade o <link rel="canonical"> sai igual. Ausente não é defeito de tela; preencher é
convenção do projeto. ERRADO (apontando para copia-teste, gwi ou outra página) é que tira a página do índice.

  --executar   grava `cq:canonicalUrl` = o próprio caminho, SÓ em página nossa (debaixo do que o manifesto
               criou — `_comum.alterar` recusa o resto) e só onde falta ou está errado. Relê a página ao vivo
               antes de cada gravação. Página da Anion NUNCA é gravada por aqui: sai no CSV como `anion`.
  --render     além da propriedade, baixa o HTML (wcmmode=disabled) e confere o canonical RENDERIZADO:
               1 no <head> apontando para a própria página, 0 no <body>. XF com master `components/page`
               embute um documento inteiro e põe um 2º canonical (o do XF) no corpo.
"""
import argparse
import collections
import csv
import re
from concurrent.futures import ThreadPoolExecutor

from _comum import BASE, DADOS, G, NOSSAS, alterar, eh_nossa, ler, manifesto, retrato_global2, sessao, url

PROPS = ("jcr:path jcr:createdBy jcr:content/cq:canonicalUrl jcr:content/cq:lastModified "
         "jcr:content/cq:lastModifiedBy jcr:content/cq:lastReplicationAction")


def paginas():
    """{caminho: hit} de toda página sob G, mais a própria G (o `path` do querybuilder não devolve a raiz)."""
    r = sessao.get(BASE + "/bin/querybuilder.json", timeout=180, allow_redirects=False, params={
        "path": G, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective", "p.properties": PROPS})
    pgs = {h["jcr:path"]: h for h in r.json()["hits"]}
    st, j = ler(G, ".1.json")
    if st == 200 and G not in pgs:
        pgs[G] = {"jcr:path": G, "jcr:createdBy": j.get("jcr:createdBy"), "jcr:content": j.get("jcr:content") or {}}
    return pgs


def classe(p, v):
    if v is None:
        return "ausente"
    if v == p:
        return "ok"
    if "/copia-teste/" in v or "/gwi/" in v:
        return "ERRADO-origem"
    return "ERRADO-outro"


def render(p):
    r = sessao.get(url(p, ".html"), params={"wcmmode": "disabled"}, timeout=120, allow_redirects=False)
    h = r.text if r.status_code == 200 else ""
    fim = h.find("</head>")
    can = [(m.start() < fim, re.search(r'href="([^"]*)"', m.group(0)).group(1))
           for m in re.finditer(r'<link[^>]+rel="canonical"[^>]*>', h)]
    return p, r.status_code, [c for e, c in can if e], [c for e, c in can if not e]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()

    raizes = [m["destino"] for m in manifesto() if m["status"] in (200, 201) and m["destino"].startswith(G + "/")]
    nossa = lambda p: any(p == r or p.startswith(r + "/") for r in raizes)
    antes = retrato_global2()
    pgs = paginas()
    linhas = []
    for p in sorted(pgs):
        v = (pgs[p].get("jcr:content") or {}).get("cq:canonicalUrl")
        linhas.append({"pagina": p, "dono": "nosso" if nossa(p) else "anion", "criador": pgs[p].get("jcr:createdBy"),
                       "canonical": v, "classe": classe(p, v), "acao": ""})

    print(f"páginas sob {G} (com a landing): {len(linhas)}")
    for dono in ("nosso", "anion"):
        print(f"   {dono:6}", dict(collections.Counter(l["classe"] for l in linhas if l["dono"] == dono)))
    for l in linhas:
        if l["classe"].startswith("ERRADO"):
            print(f"   [{l['classe']}] {l['pagina']}\n        -> {l['canonical']}")

    gravar = [l for l in linhas if l["dono"] == "nosso" and l["classe"] != "ok"]
    print(f"\na gravar (nossas, ausente ou errado): {len(gravar)}   modo: {'ESCRITA' if a.executar else 'dry-run'}")
    for l in gravar:
        p = l["pagina"]
        st, jc = ler(p + "/jcr:content")                                   # relido AO VIVO antes de gravar
        if st != 200 or not eh_nossa((jc or {}).get("jcr:createdBy"), NOSSAS):
            l["acao"] = f"PULADA (HTTP {st}, criada por {(jc or {}).get('jcr:createdBy')})"
            print("  ", l["acao"], p)
            continue
        if jc.get("cq:canonicalUrl") == p:
            l["acao"] = "ja-ok"
            continue
        l["acao"] = alterar(p + "/jcr:content", {"cq:canonicalUrl": p}, a.executar)
    print("  ", dict(collections.Counter(l["acao"] for l in gravar)))

    if a.executar:
        depois, pgs2 = retrato_global2(), paginas()
        ruins = [p for p in (l["pagina"] for l in gravar) if (pgs2[p].get("jcr:content") or {}).get("cq:canonicalUrl") != p]
        print(f"\nrelido: {len(gravar) - len(ruins)}/{len(gravar)} com canonical = próprio caminho; ainda ruins: {ruins}")
        # o AEM carimba cq:lastModified sozinho ao gravar em jcr:content: o carimbo TEM de mudar nas gravadas e só nelas
        feitas = {l["pagina"] for l in gravar if l["acao"] == "alterado"}
        fora = sorted(p for p in antes if antes[p] != depois.get(p) and p not in feitas)
        print(f"retrato do global2: {len(antes)} -> {len(depois)} páginas; sumiram {len(set(antes) - set(depois))}; "
              f"carimbo mudou fora das {len(feitas)} gravadas em {len(fora)} (é outro ator — a Anion edita em paralelo): "
              f"{[(p[len(G):], depois[p][2]) for p in fora[:5]]}")
        for l in linhas:
            l["canonical_depois"] = (pgs2.get(l["pagina"], {}).get("jcr:content") or {}).get("cq:canonicalUrl")

    if a.render:
        with ThreadPoolExecutor(6) as ex:
            res = {p: (st, head, body) for p, st, head, body in ex.map(render, [l["pagina"] for l in linhas])}
        for l in linhas:
            st, head, body = res[l["pagina"]]
            l["render_head"], l["render_body"] = " | ".join(head), " | ".join(body)
            l["render"] = (f"HTTP {st}" if st != 200 else "ok" if head == [l["pagina"] + ".html"] and not body else
                           "2o-canonical-no-body" if head == [l["pagina"] + ".html"] else "HEAD-ERRADO")
        print("\nrender:")
        for dono in ("nosso", "anion"):
            print(f"   {dono:6}", dict(collections.Counter(l["render"] for l in linhas if l["dono"] == dono)))
        print("   alvo do canonical no <body>:", dict(collections.Counter(l["render_body"] for l in linhas if l["render_body"])))

    DADOS.mkdir(parents=True, exist_ok=True)
    with open(DADOS / "canonical.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(max(linhas, key=len)))
        w.writeheader()
        w.writerows(linhas)
    print(f"\nCSV: {DADOS / 'canonical.csv'}")


if __name__ == "__main__":
    main()
