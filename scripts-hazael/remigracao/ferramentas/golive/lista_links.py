"""
lista_links.py — SOMENTE LEITURA. Mapa de links (HTML autônomo, abre em qualquer navegador) das páginas do
macnicaglobal2 feitas pelo Bruno ou pelo Valter, FORA DO EDITOR (`.html?wcmmode=disabled`), em quatro raízes
de /americas/mai/en: solutions, products/boards-modules, products/semiconductors e services.

Pedido do Hazael (21–22/09/2026): filtrar por autor (Valter e Bruno) sem dizer o autor no HTML; o HTML é
estritamente do macnicaglobal2 — não cita o GWI. O GWI só é LIDO, para descartar cópia de teste (página sem
par lá). `technology` virou `solutions` no global2 em 22/09; no GWI e nos manifestos o nome continua
`technology` (tabela ANTIGO).

Só sai GET daqui: querybuilder dos dois lados e, com `--conferir`, o GET do próprio link.

Entra no mapa a página que:
  1. é NOSSA: `jcr:createdBy` é Bruno/Valter; ou o `cq:lastModifiedBy` é Bruno/Valter E a página era casca
     (`createdBy` = admin) ou é de família em que a maioria das páginas foi criada por nós (a raiz de
     `tq-systems` é do anil, a família é do Bruno); ou está nos manifestos do go-live (manifesto.jsonl e
     manifesto_direto.jsonl) como página criada/preenchida por nós — o `cq:lastModifiedBy` sozinho não basta:
     o rename de `technology` fez o `reference-adjustment-service` carimbar as landings que linkam filhas
     (imaging-and-vision, casca do admin, sumia da lista). Página da Anion em que o lote do Bruno encostou
     (`sony/…/sony-imx174llj-c`) NÃO entra;
  2. NÃO está soft-deleted (`deleted` no jcr:content — some do console, continua no JCR);
  3. TEM par no GWI: mesmo caminho relativo com o nome normalizado; se não casar, mesmo pai + mesmo
     `jcr:title`, desde que o par ainda não tenha página viva no global2 (o Bruno renomeou `ibase/…/mi991`).
     Sem par = cópia de teste (`tq-systems1/4/5`, `tq-systems-embedded`…) e fica de fora.

A raiz de cada ramo passa pelo MESMO filtro: `boards-modules` e `semiconductors` são da Anion e ficam como
cabeçalho sem link. Nó intermediário que não é nosso também aparece só como texto.

    python3 lista_links.py                   # gera dados/golive/global2_link_map.{html,json}
    python3 lista_links.py --conferir        # + GET em cada link, lista o que não deu 200
    python3 lista_links.py --raizes solutions services --nome outro_nome
"""
import argparse
import collections
import datetime
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
NOME_PADRAO = "global2_link_map"

MAI = "/content/macnicaglobal2/americas/mai/en"
GWI_MAI = "/content/macnicagwi/americas/mai/en"
RAIZES = ("solutions", "products/boards-modules", "products/semiconductors", "services")
NOMES = {"solutions": "Solutions", "products/boards-modules": "Boards & Modules",
         "products/semiconductors": "Semiconductors", "services": "Services"}
ANTIGO = {"solutions": "technology"}                              # nome da seção no GWI e nos manifestos
MANIFESTOS = (DADOS / "manifesto.jsonl", DADOS / "manifesto_direto.jsonl")
OPS_PAGINA = {"pagina-nova", "pagina-preenchida", "copy", "create"}   # o que nos manifestos é página nossa
NOSSOS = ("valter.toffolo@", "bruno.jaques@")
PROPS = ("jcr:path jcr:createdBy jcr:content/jcr:title jcr:content/cq:lastModifiedBy "
         "jcr:content/cq:lastModified jcr:content/deleted")

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
sessao, _auth = build_session(prompt_if_missing=False, verbose=False)


def url(path, sufixo=""):
    return BASE + quote(unquote(path), safe="/:") + sufixo


def paginas(raiz):
    """A raiz + todas as cq:Page abaixo dela. Só GET (o `path` do querybuilder não devolve a própria raiz)."""
    r = sessao.get(url(raiz, ".1.json"), timeout=90, allow_redirects=False)
    assert r.status_code == 200, (r.status_code, raiz)
    j = r.json()
    out = [{"jcr:path": raiz, "jcr:createdBy": j.get("jcr:createdBy"), "jcr:content": j.get("jcr:content", {})}]
    off, lote = 0, 1000
    while True:
        r = sessao.get(BASE + "/bin/querybuilder.json", timeout=180, allow_redirects=False, params={
            "path": raiz, "type": "cq:Page", "p.limit": str(lote), "p.offset": str(off),
            "p.hits": "selective", "p.properties": PROPS, "orderby": "path"})
        assert r.status_code == 200, (r.status_code, raiz)
        hits = r.json()["hits"]
        out += hits
        off += len(hits)
        if len(hits) < lote:
            return out


def norm(rel):
    return "/".join(re.sub(r"[^a-z0-9]+", "-", unquote(p).lower()).strip("-") for p in rel.split("/"))


def _nosso(usuario):
    return bool(usuario) and usuario.startswith(NOSSOS)


def _titulo(h):
    return re.sub(r"\s+", " ", h.get("jcr:content", {}).get("jcr:title") or "").strip()


def _familia(rel):
    p = rel.split("/")
    return "/".join(p[:3] if p[0] == "products" else p[:2])


def _troca_secao(rel, tabela):
    sec, _, resto = rel.partition("/")
    return tabela.get(sec, sec) + ("/" + resto if resto else "")


def _paginas_dos_manifestos():
    """Caminhos relativos (já com o nome atual da seção) das páginas que o go-live criou/preencheu."""
    atual = {v: k for k, v in ANTIGO.items()}
    out = set()
    for arq in MANIFESTOS:
        if not arq.exists():
            continue
        for linha in arq.read_text().splitlines():
            if not linha.strip():
                continue
            m = json.loads(linha)
            if m.get("op") not in OPS_PAGINA or m.get("status") not in (200, 201):
                continue
            d = m.get("destino") or ""
            if d.startswith(MAI + "/"):
                out.add(_troca_secao(d[len(MAI) + 1:].split("/jcr:content")[0], atual))
    return out


def escolher(raizes):
    """(escolhidas, fora): escolhidas = [{rel, path, titulo}] ordenadas por rel; fora = {motivo: [rel]}."""
    gwi, g2 = {}, []
    for raiz in raizes:
        raiz_gwi = f"{GWI_MAI}/{_troca_secao(raiz, ANTIGO)}"
        for h in paginas(raiz_gwi):
            gwi[norm(raiz + h["jcr:path"][len(raiz_gwi):])] = h        # chave já com o nome atual do global2
        g2 += paginas(f"{MAI}/{raiz}")

    criadas = collections.defaultdict(collections.Counter)      # família -> nossas x de outros (admin é casca: neutro)
    for h in g2:
        if h.get("jcr:createdBy") != "admin":
            criadas[_familia(h["jcr:path"][len(MAI) + 1:])][_nosso(h.get("jcr:createdBy"))] += 1
    do_manifesto = _paginas_dos_manifestos()

    def nossa(h, rel):
        if _nosso(h.get("jcr:createdBy")) or rel in do_manifesto:
            return True
        if not _nosso(h.get("jcr:content", {}).get("cq:lastModifiedBy")):
            return False
        c = criadas[_familia(rel)]
        return h.get("jcr:createdBy") == "admin" or c[True] > c[False]

    candidatas, fora = [], collections.defaultdict(list)
    for h in g2:
        rel = h["jcr:path"][len(MAI) + 1:]
        if not nossa(h, rel):
            fora["de outra pessoa"].append(rel)
            continue
        if h.get("jcr:content", {}).get("deleted"):
            fora["soft-deleted"].append(rel)
            continue
        candidatas.append((rel, h))

    # par do GWI já ocupado por página VIVA do global2, de quem for — a renomeada só casa com par livre
    casadas = {norm(h["jcr:path"][len(MAI) + 1:]) for h in g2 if not h.get("jcr:content", {}).get("deleted")} & set(gwi)
    escolhidas = []
    for rel, h in candidatas:
        par = gwi.get(norm(rel))
        if par is None:                                         # renomeada: mesmo pai, mesmo título, par livre
            pai = norm(rel).rsplit("/", 1)[0]
            achados = [k for k, g in gwi.items() if k.rsplit("/", 1)[0] == pai and k not in casadas
                       and _titulo(g) and _titulo(g).lower() == _titulo(h).lower()]
            if len(achados) == 1:
                par = gwi[achados[0]]
                casadas.add(achados[0])
        if par is None:
            fora["sem par no GWI"].append(rel)
            continue
        escolhidas.append({"rel": rel, "path": h["jcr:path"], "titulo": _titulo(h)})
    return sorted(escolhidas, key=lambda e: e["rel"]), fora


def link(path):
    return url(path, ".html") + "?wcmmode=disabled"


def conferir(itens):
    def um(e):
        try:
            r = sessao.get(link(e["path"]), timeout=180, allow_redirects=False)
            return e, r.status_code
        except Exception as ex:                                 # noqa: BLE001
            return e, repr(ex)
    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(um, itens))


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1f23;--mut:#6a6f78;--lin:#e4e1d8;--acc:#0b5cad;--vis:#6b3fa0;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#15171b;--fg:#e8e6e1;--mut:#9aa0aa;--lin:#2b2f36;--acc:#7db7f5;--vis:#c3a2ee;--card:#1c1f24}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 20px}
.barra{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--lin);z-index:2;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.barra input{flex:1 1 260px;padding:8px 10px;border:1px solid var(--lin);border-radius:6px;background:var(--card);color:var(--fg);font:inherit}
.barra nav a{margin-right:12px;white-space:nowrap}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}a:visited{color:var(--vis)}
h2{font-size:21px;margin:40px 0 6px;padding-top:8px;scroll-margin-top:64px}
h2 .n,summary .n{color:var(--mut);font-weight:400;font-size:14px;margin-left:6px}
.landing{margin:0 0 14px}
details{background:var(--card);border:1px solid var(--lin);border-radius:8px;margin:10px 0;padding:0 14px}
summary{cursor:pointer;padding:11px 0;font-weight:600;font-size:16px}
details[open]>summary{border-bottom:1px solid var(--lin)}
ul{list-style:none;margin:0;padding:0 0 0 18px}
details>ul{padding:8px 0 12px}
li{padding:3px 0}
li>ul{border-left:1px solid var(--lin);margin:2px 0 4px 4px}
.p{display:block;color:var(--mut);font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.sem{color:var(--mut);font-weight:600}
.oculto{display:none}
footer{margin-top:48px;color:var(--mut);font-size:13px;border-top:1px solid var(--lin);padding-top:12px}
"""

JS = """
const q=document.getElementById('q');
q.addEventListener('input',()=>{
  const t=q.value.trim().toLowerCase();
  document.querySelectorAll('li').forEach(li=>li.classList.remove('oculto'));
  if(!t){document.querySelectorAll('details').forEach(d=>{d.open=true});return}
  // de baixo para cima: o item fica se ele ou algum descendente casar
  [...document.querySelectorAll('li')].reverse().forEach(li=>{
    const proprio=(li.dataset.t||'').includes(t);
    const filho=li.querySelector('li:not(.oculto)');
    if(!proprio&&!filho)li.classList.add('oculto');
  });
  document.querySelectorAll('details').forEach(d=>{d.open=!!d.querySelector('li:not(.oculto)')});
});
"""


def _arvore(itens, prefixo):
    """Árvore {nome: {"_": item|None, filhos…}} a partir do caminho relativo depois de `prefixo`."""
    raiz = {}
    for e in itens:
        no = raiz
        for parte in e["rel"][len(prefixo) + 1:].split("/"):
            no = no.setdefault(parte, {})
        no["_"] = e
    return raiz


def _conta(no):
    return sum((1 if k == "_" else _conta(v)) for k, v in no.items())


def _n(n):
    return f"{n} page" + ("" if n == 1 else "s")


def _a(e, texto):
    return f'<a href="{html.escape(link(e["path"]), quote=True)}" target="_blank" rel="noopener">{html.escape(texto)}</a>'


def _ul(no, caminho):
    out = ["<ul>"]
    for nome in sorted(k for k in no if k != "_"):
        filho, rel = no[nome], f"{caminho}/{nome}"
        e = filho.get("_")
        busca = html.escape(f"{(e or {}).get('titulo', '')} {rel}".lower(), quote=True)
        out.append(f'<li data-t="{busca}">')
        if e:
            out.append(f'{_a(e, e["titulo"] or nome)}<span class="p">/{html.escape(rel)}</span>')
        else:
            out.append(f'<span class="sem">{html.escape(nome)}</span>')
        if any(k != "_" for k in filho):
            out.append(_ul(filho, rel))
        out.append("</li>")
    out.append("</ul>")
    return "".join(out)


def montar_html(escolhidas, raizes, quando):
    por = {e["rel"]: e for e in escolhidas}
    corpo, nav, nomes = [], [], []
    for raiz in raizes:
        nome = NOMES.get(raiz) or raiz.rsplit("/", 1)[-1].replace("-", " ").title()
        idr = raiz.replace("/", "-")
        itens = [e for e in escolhidas if e["rel"] == raiz or e["rel"].startswith(raiz + "/")]
        nav.append(f'<a href="#{idr}">{html.escape(nome)} ({len(itens)})</a>')
        nomes.append(nome)
        corpo.append(f'<h2 id="{idr}">{html.escape(nome)}<span class="n">{_n(len(itens))}</span></h2>')
        r = por.get(raiz)
        if r:                                                   # a raiz é nossa: link; senão só o caminho
            corpo.append(f'<p class="landing">{_a(r, r["titulo"] or nome)}<span class="p">/{html.escape(raiz)}</span></p>')
        else:
            corpo.append(f'<p class="landing"><span class="p">/{html.escape(raiz)}</span></p>')
        arv = _arvore([e for e in itens if e["rel"] != raiz], raiz)
        for cat in sorted(arv):
            no = arv[cat]
            corpo.append(f'<details open><summary>{html.escape(cat)}<span class="n">{_n(_conta(no))}</span></summary>')
            # a própria categoria é o 1º item da lista dela quando é página nossa
            corpo.append(_ul({cat: no} if "_" in no else {k: v for k, v in no.items() if k != "_"},
                             raiz if "_" in no else f"{raiz}/{cat}"))
            corpo.append("</details>")
    escopo = (", ".join(nomes[:-1]) + " and " + nomes[-1]) if len(nomes) > 1 else nomes[0]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macnica global2 — link map</title><style>{CSS}</style></head><body><main>
<h1>Macnica global2 — link map</h1>
<p class="sub">Americas / MAI / EN — {html.escape(escopo)}. {len(escolhidas)} pages. Links open the page as a visitor sees
it (outside the editor) in a new tab; you must be logged in to the AEM author. Generated {quando}.</p>
<div class="barra"><input id="q" type="search" placeholder="Filter by title or path…" autocomplete="off">
<nav>{''.join(nav)}</nav></div>
{''.join(corpo)}
<footer>Paths are relative to <code>{MAI}</code>. Solutions and Services are still being edited; the page set is final,
the content may change.</footer>
</main><script>{JS}</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conferir", action="store_true", help="GET em cada link; lista o que não deu 200")
    ap.add_argument("--raizes", nargs="+", default=RAIZES, metavar="REL",
                    help="raízes do mapa, relativas a /americas/mai/en (padrão: %(default)s)")
    ap.add_argument("--nome", default=NOME_PADRAO, help="nome dos arquivos de saída em dados/golive (sem extensão)")
    a = ap.parse_args()
    raizes = tuple(p.strip("/") for p in a.raizes)

    escolhidas, fora = escolher(raizes)
    quando = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    DADOS.mkdir(parents=True, exist_ok=True)
    saida_html, saida_json = DADOS / f"{a.nome}.html", DADOS / f"{a.nome}.json"
    saida_html.write_text(montar_html(escolhidas, raizes, quando), encoding="utf-8")
    saida_json.write_text(json.dumps({"quando": quando, "raizes": raizes, "paginas": escolhidas, "fora": fora},
                                     ensure_ascii=False, indent=1), encoding="utf-8")

    for raiz in raizes:
        itens = [e for e in escolhidas if e["rel"] == raiz or e["rel"].startswith(raiz + "/")]
        print(f"{raiz}: {len(itens)}" + ("" if raiz in {e['rel'] for e in itens} else "  (raiz não é nossa: sem link)"))
        for k, v in sorted(collections.Counter(_familia(e["rel"]) for e in itens if e["rel"] != raiz).items()):
            print(f"    {v:4d}  {k}")
    for motivo, rels in fora.items():
        print(f"\nfora — {motivo}: {len(rels)}")
        for k, v in sorted(collections.Counter(_familia(r) for r in rels).items()):
            print(f"    {v:4d}  {k}")
    print(f"\n{saida_html}\n{saida_json}")

    if a.conferir:
        ruins = [(e, st) for e, st in conferir(escolhidas) if st != 200]
        print(f"\nconferência: {len(escolhidas) - len(ruins)} com 200, {len(ruins)} sem")
        for e, st in ruins:
            print(f"    {st}  {e['rel']}")


if __name__ == "__main__":
    main()
