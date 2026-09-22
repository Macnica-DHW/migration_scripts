"""
mapa_links.py — SOMENTE LEITURA. Mapa de links (HTML autônomo, abre em qualquer navegador) de TODAS as
cq:Page abaixo de uma raiz qualquer do AEM, sem filtro de autor — para abrir e conferir página por página.
Só sai GET daqui: `.1.json` da raiz, querybuilder e, com `--conferir`, o GET do próprio link.

Pedido do Hazael (22/09/2026): mapa de /content/copia-teste/americas/mai/en/about-us para abrir e checar
todas as páginas e subpáginas. Diferente do golive/lista_links.py (global2, filtro de autor, sem citar o
GWI), aqui entra TUDO e cada página ganha três links: a página fora do editor (`.html?wcmmode=disabled`),
o editor (`/editor.html`) e, quando há origem, a página de origem (`--origem`; para raiz em
/content/copia-teste/… a origem é o mesmo caminho em /content/macnicagwi/…, casada pelo caminho relativo
normalizado). Nó do meio que não é cq:Page (sling:Folder) aparece como texto — "folder, no page here" —
e, se a origem tem página nesse ponto, o link dela. Página soft-deleted (`deleted` no jcr:content: some
do console, continua no JCR) vai para uma seção própria. Página da origem sem par aqui vai para a seção
"Only in the origin".

    python3 mapa_links.py /content/copia-teste/americas/mai/en/about-us              # dados/mapas/copia-teste_about-us.{html,json}
    python3 mapa_links.py RAIZ --conferir                                              # + GET em cada link; lista o que não deu 200
    python3 mapa_links.py RAIZ --origem /content/macnicagwi/americas/mai/en/about-us   # origem explícita
    python3 mapa_links.py RAIZ --origem ''                                             # sem coluna de origem
    python3 mapa_links.py RAIZ --nome outro_nome
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

sys.path.insert(0, str(Path(__file__).resolve().parent / "golive"))
import lista_links as ll  # noqa: E402  — CSS/JS, url(), link(), norm(), sessão: só GET

DADOS = Path(__file__).resolve().parents[1] / "dados" / "mapas"
ORIGEM_AUTO = {"copia-teste": "macnicagwi"}               # /content/copia-teste/… -> /content/macnicagwi/…
PROPS = ("jcr:path jcr:createdBy jcr:content/jcr:title jcr:content/cq:lastModifiedBy jcr:content/cq:lastModified "
         "jcr:content/deleted jcr:content/cq:redirectTarget jcr:content/cq:template")


def _titulo(c):
    return re.sub(r"\s+", " ", (c or {}).get("jcr:title") or "").strip()


def _item(h, raiz):
    c = h.get("jcr:content") or {}
    return {"rel": h["jcr:path"][len(raiz) + 1:], "path": h["jcr:path"], "titulo": _titulo(c),
            "criador": h.get("jcr:createdBy"), "editor": c.get("cq:lastModifiedBy"), "modificado": c.get("cq:lastModified"),
            "template": (c.get("cq:template") or "").rsplit("/", 1)[-1], "redirect": c.get("cq:redirectTarget"),
            "deleted": bool(c.get("deleted"))}


def ler_arvore(raiz):
    """(raiz, páginas): a raiz (página ou não) e todas as cq:Page abaixo dela. Só GET."""
    r = ll.sessao.get(ll.url(raiz, ".1.json"), timeout=90, allow_redirects=False)
    assert r.status_code == 200, (r.status_code, raiz)
    j = r.json()
    info = {"path": raiz, "tipo": j.get("jcr:primaryType"), "pagina": j.get("jcr:primaryType") == "cq:Page" and "jcr:content" in j,
            "titulo": _titulo(j.get("jcr:content")), "criador": j.get("jcr:createdBy"),
            "editor": (j.get("jcr:content") or {}).get("cq:lastModifiedBy")}
    hits, off, lote = [], 0, 1000
    while True:
        r = ll.sessao.get(ll.BASE + "/bin/querybuilder.json", timeout=180, allow_redirects=False, params={
            "path": raiz, "type": "cq:Page", "p.limit": str(lote), "p.offset": str(off),
            "p.hits": "selective", "p.properties": PROPS, "orderby": "path"})
        assert r.status_code == 200, (r.status_code, raiz)
        h = r.json()["hits"]
        hits += h
        off += len(h)
        if len(h) < lote:
            break
    return info, sorted((_item(h, raiz) for h in hits), key=lambda e: e["rel"])


def origem_padrao(raiz):
    partes = raiz.split("/")
    site = partes[2] if len(partes) > 2 and partes[1] == "content" else None
    return "/".join(partes[:2] + [ORIGEM_AUTO[site]] + partes[3:]) if site in ORIGEM_AUTO else None


def _arvore(itens):
    raiz = {}
    for e in itens:
        no = raiz
        for parte in e["rel"].split("/"):
            no = no.setdefault(parte, {})
        no["_"] = e
    return raiz


def _conta(no):
    return sum((1 if k == "_" else _conta(v)) for k, v in no.items())


def _n(n):
    return f"{n} page" + ("" if n == 1 else "s")


def editor(path):
    return ll.BASE + "/editor.html" + quote(unquote(path), safe="/:") + ".html"


def _host(u):
    m = re.match(r"^https?://([^/]+)", u or "")
    return m.group(1) if m else (u or "")


def _a(href, texto, cls=None):
    c = f' class="{cls}"' if cls else ""
    return f'<a{c} href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{html.escape(texto)}</a>'


def _abrir(n):
    """Link que abre em novas abas todas as páginas (a.pg) do grupo: o <details> quando está no <summary>, o <li> senão."""
    return f'<a class="abrir" href="#" title="Open every page of this group in a new tab (visible ones only, when filtering)">open all {n} in new tabs</a>'


def conferir(itens):
    def um(e):
        try:
            r = ll.sessao.get(ll.link(e["path"]), timeout=180, allow_redirects=False)
            return e, r.status_code
        except Exception as ex:                                 # noqa: BLE001
            return e, repr(ex)
    with ThreadPoolExecutor(4) as ex:
        return list(ex.map(um, itens))


# ---------------------------------------------------------------- HTML

CSS_EXTRA = """
.x{font-size:12px;color:var(--mut);margin-left:8px;white-space:nowrap}
.x a,.x a:visited{color:var(--mut);text-decoration:underline dotted}
.x .st{color:#b3261e;font-weight:600}
.raiz{margin:0 0 6px;font-size:17px}
.abrir{font-size:12px;font-weight:400;margin-left:10px;white-space:nowrap}
summary .abrir{margin-left:14px}
.aviso{font-size:12px;color:var(--mut);margin-left:8px}
.aviso.bloq{color:#b3261e}
"""

JS_EXTRA = """
document.addEventListener('click',ev=>{
  const a=ev.target.closest('a.abrir');if(!a)return;
  ev.preventDefault();ev.stopPropagation();
  const grupo=a.closest('summary')?a.closest('details'):a.closest('li');
  const links=[...grupo.querySelectorAll('a.pg')].filter(x=>!x.closest('.oculto'));
  let bloq=0;for(const x of links){if(!window.open(x.href,'_blank'))bloq++}
  let av=a.nextElementSibling;
  if(!av||!av.classList.contains('aviso')){av=document.createElement('span');av.className='aviso';a.after(av)}
  av.classList.toggle('bloq',bloq>0);
  av.textContent=bloq?`${bloq} of ${links.length} blocked — allow pop-ups for this page (icon at the right of the address bar) and click again`:`${links.length} opened`;
});
"""


class Mapa:
    def __init__(self, raiz, itens, origem, o_raiz, o_itens):
        self.raiz, self.itens, self.origem = raiz, itens, origem
        self.o_raiz, self.o_itens = o_raiz, o_itens
        self.o_por = {ll.norm(e["rel"]): e for e in o_itens}                           # origem, pelo rel normalizado
        for e in itens:
            e["origem"] = (self.o_por.get(ll.norm(e["rel"])) or {}).get("path")
            e["origem_redirect"] = (self.o_por.get(ll.norm(e["rel"])) or {}).get("redirect")
        aqui = {ll.norm(e["rel"]) for e in itens}
        self.so_na_origem = [e for e in o_itens if ll.norm(e["rel"]) not in aqui]
        self.vivas = [e for e in itens if not e["deleted"]]
        self.deletadas = [e for e in itens if e["deleted"]]
        pags = {e["rel"] for e in itens}
        self.pastas = sorted({"/".join(e["rel"].split("/")[:i]) for e in itens for i in range(1, e["rel"].count("/") + 1)} - pags)
        self.status = {}

    def _extras(self, e):
        partes = [_a(editor(e["path"]), "edit")]
        if self.origem:
            if e["origem"]:
                partes.append(_a(ll.link(e["origem"]), "origin")
                              + (f' (origin is a redirect to {html.escape(_host(e["origem_redirect"]))})' if e["origem_redirect"] else ""))
            else:
                partes.append("no origin page")
        st = self.status.get(e["path"])
        if st is not None and st != 200:
            partes.append(f'<span class="st">HTTP {html.escape(str(st))}</span>')
        return f'<span class="x">{" · ".join(partes)}</span>'

    def _pasta(self, rel):
        nota = "folder, no page here"
        o = self.o_por.get(ll.norm(rel)) if self.origem else None
        if o:
            nota += " · origin has a page: " + _a(ll.link(o["path"]), o["titulo"] or rel.rsplit("/", 1)[-1])
        return f'<span class="x">{nota}</span>'

    def _ul(self, no, caminho, abrir_topo=True):
        """abrir_topo=False: o 1º nível não ganha 'open all' (o <summary> do ramo já tem o mesmo link)."""
        out = ["<ul>"]
        for nome in sorted(k for k in no if k != "_"):
            filho, rel = no[nome], f"{caminho}/{nome}" if caminho else nome
            e = filho.get("_")
            busca = html.escape(f"{(e or {}).get('titulo', '')} {rel}".lower(), quote=True)
            out.append(f'<li data-t="{busca}">')
            tem_filhos = any(k != "_" for k in filho)
            grupo = _abrir(_conta(filho)) if tem_filhos and abrir_topo else ""
            if e:
                out.append(f'{_a(ll.link(e["path"]), e["titulo"] or nome, "pg")}{self._extras(e)}{grupo}<span class="p">/{html.escape(rel)}</span>')
            else:
                out.append(f'<span class="sem">{html.escape(nome)}</span>{self._pasta(rel)}{grupo}<span class="p">/{html.escape(rel)}</span>')
            if tem_filhos:
                out.append(self._ul(filho, rel))
            out.append("</li>")
        out.append("</ul>")
        return "".join(out)

    def _lista(self, itens, links_origem=False):
        out = ["<ul>"]
        for e in itens:
            busca = html.escape(f"{e['titulo']} {e['rel']}".lower(), quote=True)
            if links_origem:
                extra = f'<span class="x">redirect to {html.escape(e["redirect"])}</span>' if e["redirect"] else ""
                out.append(f'<li data-t="{busca}">{_a(ll.link(e["path"]), e["titulo"] or e["rel"], "pg")}{extra}<span class="p">/{html.escape(e["rel"])}</span></li>')
            else:
                out.append(f'<li data-t="{busca}">{_a(ll.link(e["path"]), e["titulo"] or e["rel"], "pg")}{self._extras(e)}<span class="p">/{html.escape(e["rel"])}</span></li>')
        out.append("</ul>")
        return "".join(out)

    def html(self, quando):
        arv = _arvore(self.vivas)
        nome_raiz = self.raiz.rsplit("/", 1)[-1]
        soltas = {k: v for k, v in arv.items() if not any(x != "_" for x in v)}          # 1º nível sem filhos
        ramos = {k: v for k, v in arv.items() if k not in soltas}
        nav, corpo = [], []
        if soltas:
            n = len(soltas)
            nav.append(f'<a href="#nivel-raiz">Root level ({n})</a>')
            corpo.append(f'<details open id="nivel-raiz"><summary>Pages directly under /{html.escape(nome_raiz)}<span class="n">{_n(n)}</span>{_abrir(n)}</summary>')
            corpo.append(self._ul({k: v for k, v in soltas.items()}, ""))
            corpo.append("</details>")
        for nome in sorted(ramos):
            no, n = ramos[nome], _conta(ramos[nome])
            idr = "r-" + re.sub(r"[^a-z0-9]+", "-", nome.lower())
            nav.append(f'<a href="#{idr}">{html.escape(nome)} ({n})</a>')
            corpo.append(f'<details open id="{idr}"><summary>{html.escape(nome)}<span class="n">{_n(n)}</span>'
                         + ("" if "_" in no else ' <span class="n">(folder)</span>') + f"{_abrir(n)}</summary>")
            corpo.append(self._ul({nome: no}, "", abrir_topo=False))
            corpo.append("</details>")
        if self.deletadas:
            nav.append(f'<a href="#deletadas">Soft-deleted ({len(self.deletadas)})</a>')
            corpo.append(f'<details id="deletadas"><summary>Soft-deleted — hidden from the Sites console, still in the JCR'
                         f'<span class="n">{_n(len(self.deletadas))}</span>{_abrir(len(self.deletadas))}</summary>{self._lista(self.deletadas)}</details>')
        if self.origem and self.so_na_origem:
            nav.append(f'<a href="#so-origem">Only in the origin ({len(self.so_na_origem)})</a>')
            corpo.append(f'<details open id="so-origem"><summary>Only in the origin — no page here'
                         f'<span class="n">{_n(len(self.so_na_origem))}</span>{_abrir(len(self.so_na_origem))}</summary>{self._lista(self.so_na_origem, True)}</details>')

        if self.o_raiz and self.o_raiz["pagina"]:
            o = " · origin: " + _a(ll.link(self.o_raiz["path"]), self.o_raiz["titulo"] or nome_raiz)
        else:
            o = ""
        if self.raiz_info["pagina"]:
            linha = _a(ll.link(self.raiz), self.raiz_info["titulo"] or nome_raiz, "pg") + f'<span class="x">{_a(editor(self.raiz), "edit")}{o}</span>'
        else:
            linha = f'<span class="sem">{html.escape(nome_raiz)}</span><span class="x">{html.escape(self.raiz_info["tipo"] or "?")}, no page here{o}</span>'
        ruins = sum(1 for st in self.status.values() if st != 200)
        conf = (f" All {len(self.status)} page links were checked ({ruins} not returning HTTP 200)." if self.status else "")
        sub_origem = f' Origin pages are under <code>{html.escape(self.origem)}</code>.' if self.origem else ""
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(nome_raiz)} — link map</title><style>{ll.CSS}{CSS_EXTRA}</style></head><body><main>
<h1>{html.escape(nome_raiz)} — link map</h1>
<p class="sub"><code>{html.escape(self.raiz)}</code> — {_n(len(self.vivas))}{f", {len(self.deletadas)} soft-deleted" if self.deletadas else ""}.
Links open the page as a visitor sees it (outside the editor) in a new tab; <i>edit</i> opens the editor; <i>origin</i> opens the
page this one was migrated from; <i>open all</i> opens every page of a group in new tabs (the browser may ask you to allow
pop-ups the first time). You must be logged in to the AEM author.{conf} Generated {quando}.</p>
<div class="barra"><input id="q" type="search" placeholder="Filter by title or path…" autocomplete="off">
<nav>{''.join(nav)}</nav></div>
<p class="raiz">{linha}<span class="p">{html.escape(self.raiz)}</span></p>
{''.join(corpo)}
<footer>Paths are relative to <code>{html.escape(self.raiz)}</code>.{sub_origem} Every cq:Page under the root is listed, whoever made it.</footer>
</main><script>{ll.JS}{JS_EXTRA}</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", help="caminho JCR da raiz (ex.: /content/copia-teste/americas/mai/en/about-us)")
    ap.add_argument("--origem", default=None, metavar="PATH",
                    help="raiz de origem para o link 'origin' (padrão: copia-teste -> macnicagwi; '' = sem origem)")
    ap.add_argument("--conferir", action="store_true", help="GET em cada link da página; lista o que não deu 200")
    ap.add_argument("--nome", default=None, help="nome dos arquivos de saída em dados/mapas (padrão: <site>_<raiz>)")
    a = ap.parse_args()
    raiz = "/" + a.raiz.strip("/")
    origem = origem_padrao(raiz) if a.origem is None else (("/" + a.origem.strip("/")) if a.origem.strip() else None)
    nome = a.nome or f"{raiz.split('/')[2]}_{raiz.rsplit('/', 1)[-1]}"

    raiz_info, itens = ler_arvore(raiz)
    o_raiz, o_itens = ler_arvore(origem) if origem else (None, [])
    m = Mapa(raiz, itens, origem, o_raiz, o_itens)
    m.raiz_info = raiz_info
    if a.conferir:
        m.status = {e["path"]: st for e, st in conferir(m.vivas)}

    quando = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    DADOS.mkdir(parents=True, exist_ok=True)
    saida_html, saida_json = DADOS / f"{nome}.html", DADOS / f"{nome}.json"
    saida_html.write_text(m.html(quando), encoding="utf-8")
    saida_json.write_text(json.dumps({
        "quando": quando, "raiz": raiz_info, "origem": origem, "origem_raiz": o_raiz, "paginas": itens, "pastas": m.pastas,
        "so_na_origem": m.so_na_origem, "conferencia": m.status}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{raiz}: {'página' if raiz_info['pagina'] else (raiz_info['tipo'] or '?') + ' (não é página)'}"
          f" — {len(m.vivas)} páginas vivas, {len(m.deletadas)} soft-deleted, {len(m.pastas)} nós do meio que não são página")
    for k, v in sorted(collections.Counter(e["rel"].split("/")[0] for e in m.vivas).items()):
        print(f"    {v:4d}  {k}")
    if m.pastas:
        print("pastas (não são cq:Page):", ", ".join(m.pastas))
    print("criador:", dict(collections.Counter(e["criador"] for e in itens)))
    print("último editor:", dict(collections.Counter(e["editor"] for e in itens)))
    tortos = [e["rel"] for e in itens if e["rel"] != ll.norm(e["rel"])]
    if tortos:
        print(f"nome de nó fora do normalizado ({len(tortos)}):", ", ".join(tortos))
    if origem:
        print(f"\norigem {origem}: {len(o_itens)} páginas; {sum(1 for e in itens if e['origem'])} daqui têm par lá, "
              f"{sum(1 for e in itens if not e['origem'])} sem par; {len(m.so_na_origem)} só lá")
        for e in m.so_na_origem:
            print(f"    só na origem  {e['rel']}  | {e['titulo']}" + (f"  | redirect -> {e['redirect']}" if e["redirect"] else ""))
        for e in itens:
            if e["origem_redirect"]:
                print(f"    origem é redirect  {e['rel']}  -> {e['origem_redirect']}")
    if a.conferir:
        ruins = [(p, st) for p, st in m.status.items() if st != 200]
        print(f"\nconferência: {len(m.status) - len(ruins)} com 200, {len(ruins)} sem")
        for p, st in ruins:
            print(f"    {st}  {p}")
    print(f"\n{saida_html}\n{saida_json}")


if __name__ == "__main__":
    main()
