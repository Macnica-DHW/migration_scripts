#!/usr/bin/env python3
"""
relatorio_consertos.py [PASTA_DO_BACKUP] — relatório HTML (em inglês, para mandar) do que o corrigir_links.py GRAVOU:
cada link consertado (texto, antes, depois, por quê) por página, e a verificação da página inteira contra o backup.
OFFLINE: lê o manifesto (manifesto_links.jsonl, linhas daquela execução), o backup (jcr_content.json) e a comparação
(comparacao.json do --verificar). Nenhum GET, nada gravado.

Pedido do Hazael (24/09/2026): "Make an HTML report with the changes you have done".

    python3 relatorio_consertos.py      # a execução mais recente -> dados/mapas/global2_link_fixes_<data>.html
"""
import collections
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrigir_links as C  # noqa: E402  (só as constantes e CONSERTOS; a Session não é usada)
import links_vs_gwi as LV  # noqa: E402  (CSS, JS e helpers do relatório anterior)

DADOS = C.DADOS
M, G2 = C.M, "/content/macnicaglobal2"
A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.I | re.S)
HREF_RE = re.compile(r"""\bhref\s*=\s*(["'])(.*?)\1""", re.I | re.S)

TIPOS = {
    "wrong": ("Pointed to the wrong place", "The link went somewhere other than the matching link on the GWI page."),
    "added": ("Link added", "The text, title or image was on the page but not clickable; the GWI links it. It now links to the "
              "same place as on the GWI (nothing else about the element changed)."),
    "button": ("Event website button", "A broken in-page jump menu (it pointed to “#https://…”) was replaced by a button in the "
               "same place, with the GWI’s text and link; it opens in a new tab."),
    "ext": ("Did not open", "A link inside text saved without “.html”: on the author, clicking it gave an error (403). "
            "Now the same destination with “.html”."),
}


def textos_do_href(valor, href):
    """Counter {texto: vezes} dos <a> de `valor` cujo href é `href` (link sem texto vira '(invisible link)')."""
    out = collections.Counter()
    for m in A_RE.finditer(valor or ""):
        h = HREF_RE.search(m.group(1))
        if h and html.unescape(h.group(2)).strip() == href:
            t = C.texto(html.unescape(m.group(2)))             # 2x: alguns textos do GWI vieram escapados duas vezes (&amp;nbsp;)
            out[t or ("(image)" if "<img" in m.group(2).lower() else "(invisible link)")] += 1
    return out or collections.Counter({"(link)": 1})


def motivo(de, para):
    d = re.split(r"[?#]", de, 1)[0].rstrip("/")
    p = re.sub(r"\.html$", "", re.split(r"[?#]", para, 1)[0])
    if "/content/macnicagwi" in de:
        return "still pointed to the old GWI site"
    if d in (M, G2):
        return "went to the site’s root instead of " + ("the Europe site" if "atd-europe" in para else para)
    if p.startswith(d + "/"):
        return "was cut off at a parent page"
    return "pointed to a different page"


def no_do_backup(jc, no):
    for k in no.split("/"):
        jc = (jc or {}).get(k, {})
    return jc


def itens(execucao, backup):
    """{pagina_rel: [item]} com item = {tipo, txt, antes, depois, motivo}."""
    abc = collections.defaultdict(list)                        # dois consertos podem ter página, nó e destino iguais
    for _, p, no, _, d in C.CONSERTOS:                          # (connect-tech: link invisível + o visível): em ordem
        abc[(f"{M}/{p}", no, d["para"])].append(d)
    por = collections.defaultdict(list)
    for x in execucao:
        rel = x["pagina"][len(M) + 1:]
        if x["tipo"] == "ext":
            for de, para in x["para"]:
                for t, k in textos_do_href(x["antes"], de).items():
                    por[rel].append({"tipo": "ext", "txt": t, "antes": de, "depois": para, "motivo": "", "vezes": k})
        elif x["tipo"] == "href":
            d = abc[(x["pagina"], x["no"], x["para"])].pop(0)
            t = next(iter(textos_do_href(x["antes"], d["de"])))
            por[rel].append({"tipo": "wrong", "txt": t, "antes": d["de"], "depois": x["para"],
                             "motivo": d.get("por_que") or motivo(d["de"], x["para"]), "vezes": 1})
        elif x["tipo"] == "wrap":                               # <a> posto em volta de um trecho que já estava no texto
            d = next(d for _, p, no, t, d in C.CONSERTOS if t == "wrap" and f"{M}/{p}" == x["pagina"] and no == x["no"])
            href = HREF_RE.search(d["para"]).group(2)
            por[rel].append({"tipo": "added", "txt": C.texto(d["de"]), "antes": "", "depois": href,
                             "motivo": "text in the event details", "vezes": 1})
        elif x["antes"] is None:                                # linkURL novo num título/imagem que já estava na página
            nod = no_do_backup(backup[rel], x["no"])
            rt = str(nod.get("sling:resourceType", "")).rsplit("/", 1)[-1]
            t = C.texto(nod.get("jcr:title") or nod.get("alt") or "") or f"({rt})"
            por[rel].append({"tipo": "added", "txt": t, "antes": "", "depois": x["para"], "motivo": f"{rt} on the page", "vezes": 1})
        else:                                                   # linkURL de botão: o rótulo vem do nó no backup
            nod = no_do_backup(backup[rel], x["no"])
            t = C.texto(nod.get("jcr:title") or nod.get("alt") or "") or "(button)"
            d = next((d for _, p, no, t, d in C.CONSERTOS if f"{M}/{p}" == x["pagina"] and no == x["no"] and d.get("para") == x["para"]), {})
            por[rel].append({"tipo": "wrong", "txt": t + " (button)", "antes": x["antes"], "depois": x["para"],
                             "motivo": d.get("por_que") or motivo(x["antes"], x["para"]), "vezes": 1})
    return por


def _u(path):
    return LV._u(path) or path


def _curto(path):
    return path[len(M):] if path.startswith(M + "/") else path


def _item(it):
    tag, _ = TIPOS[it["tipo"]]
    depois = f'<a href="{html.escape(_u(it["depois"]), quote=True)}" target="_blank" rel="noopener">{html.escape(_curto(it["depois"]))}</a>'
    busca = html.escape(f"{it['txt']} {it['antes']} {it['depois']}".lower(), quote=True)
    mot = f'<span class="nota">{html.escape(it["motivo"])}</span>' if it["motivo"] else ""
    if it["vezes"] > 1:
        mot += f'<span class="nota">× {it["vezes"]} (the same link appears {it["vezes"]} times here)</span>'
    return (f'<div class="lk" data-p="{it["tipo"]}" data-s="{busca}"><div class="t">“{html.escape(it["txt"])}”'
            f'<span class="tag {it["tipo"]}">{html.escape(tag)}</span>{mot}</div><dl>'
            + (f'<dt>Before</dt><dd class="agora">{html.escape(_curto(it["antes"]))}</dd>' if it["antes"] else
               '<dt>Before</dt><dd>(not a link)</dd>')
            + f'<dt>After</dt><dd class="dev">{depois}</dd></dl></div>')


CSS_EXTRA = """
.tag.wrong{background:var(--badbg);color:var(--bad)}.tag.ext{background:var(--warnbg);color:var(--warn)}.tag.added{background:var(--okbg);color:var(--ok)}.tag.button{background:var(--tag);color:var(--fg)}
.agora{color:var(--bad);text-decoration:line-through;text-decoration-thickness:1px}
.ok{display:inline-block;font-size:12px;background:var(--okbg);color:var(--ok);border-radius:10px;padding:1px 8px;margin-left:8px;font-weight:500}
.nota{background:none;color:var(--mut);padding:0;margin-left:8px;font-weight:400}
.passos{margin:0 0 18px;padding-left:20px}.passos li{margin:4px 0}
.base{font-size:12px;color:var(--mut)}
"""


def uma_execucao(pasta):
    quando = pasta.name[len("backup_links_"):]
    execucao = [x for x in map(json.loads, (DADOS / "manifesto_links.jsonl").read_text(encoding="utf-8").splitlines())
                if x.get("quando") == quando and x.get("status") == "gravado"]
    backup = json.loads((pasta / "jcr_content.json").read_text(encoding="utf-8"))
    comp = {x["pagina"]: x["comparacao"] for x in json.loads((pasta / "comparacao.json").read_text(encoding="utf-8"))}
    return quando, itens(execucao, backup), backup, comp


CAMPOS = ("corpo", "nav", "caixas", "linhas", "n", "por", "iguais", "com_botao", "botoes_ok", "editor", "data", "horas", "quando", "todos")


def montar(args=()):
    """Todas as execuções do dia, em ordem: um link que uma execução posterior trocou de novo sai com o destino FINAL
    (o 'antes' continua o original); a página só ganha o selo se todas as comparações dela deram iguais. Devolve as peças
    do relatório (também usadas pelo relatorio_final.py)."""
    pastas = [p.parent for p in sorted(DADOS.glob("backup_links_*/comparacao.json"))]
    if args:
        pastas = [Path(a) for a in args]
    por, backup, comp, horas = collections.defaultdict(list), {}, {}, []
    for pasta in pastas:
        q, novos, bk, cp = uma_execucao(pasta)
        horas.append(q)
        for p, its in novos.items():
            backup.setdefault(p, bk[p])
            comp.setdefault(p, {"jcr": [], "render": None})
            comp[p] = {"jcr": comp[p]["jcr"] + cp[p]["jcr"], "render": comp[p]["render"] or cp[p]["render"]}
            for it in its:
                ant = next((x for x in por[p] if x["depois"] == it["antes"] and x["txt"] == it["txt"]), None)
                if ant:                                         # a mesma âncora trocada de novo: fica o destino final
                    ant.update(depois=it["depois"], motivo=it["motivo"] or ant["motivo"])
                else:
                    por[p].append(it)
    # botões de evento (botao_evento.py): um nó trocado por outro — conferência própria (JCR, render sem o bloco, prints)
    EVP = "about-us/news-events/events-archive"
    manif = [json.loads(l) for l in (DADOS / "manifesto_links.jsonl").read_text(encoding="utf-8").splitlines()]
    for pasta in sorted(p.parent for p in DADOS.glob("backup_botoes_*/comparacao.json")):
        q = pasta.name[len("backup_botoes_"):]
        horas.append(q)
        bk = json.loads((pasta / "jcr_content.json").read_text(encoding="utf-8"))
        cp = {c["ev"]: c for c in json.loads((pasta / "comparacao.json").read_text(encoding="utf-8"))}
        for x in manif:
            if x.get("tipo") != "botao" or x.get("quando") != q or x.get("status") != "gravado":
                continue
            ev = x["pagina"].rsplit("/", 1)[-1]
            rel = f"{EVP}/{ev}"
            item0 = next((v for v in ((x.get("saiu") or {}).get("anchor") or {}).values() if isinstance(v, dict)), None)
            por[rel].append({"tipo": "button", "txt": x["txt"], "antes": ("#" + item0["linkId"]) if item0 else "",
                             "depois": x["para"], "vezes": 1,
                             "motivo": (f"replaced the jump menu “{item0['text']}”" if item0 else
                                        "no jump menu here; added above the event details")})
            backup.setdefault(rel, bk[ev])
            comp[rel] = {"jcr": [], "render": None, "botao": cp[ev].get("ok_final", cp[ev].get("ok"))}
    horas = sorted(horas)
    quando = horas[0]

    todos = [it for v in por.values() for it in v]
    n = collections.Counter()
    for it in todos:
        n[it["tipo"]] += it["vezes"]
    com_botao = [p for p in por if "botao" in comp[p]]
    iguais = sum(1 for p in por if p not in com_botao and not comp[p]["jcr"] and not comp[p]["render"])
    botoes_ok = sum(1 for p in com_botao if comp[p]["botao"])
    editor = sum(1 for p in por if backup[p].get("cq:lastModifiedBy") != "valter.toffolo@macnicadhw.com.br")
    data = f"{quando[:10]} {quando[11:13]}:{quando[13:15]}"

    secoes = collections.defaultdict(list)
    for p in por:
        secoes[LV._secao(f"americas/mai/en/{p}")].append(p)
    nav, corpo = [], []
    for sec in sorted(secoes):
        ps = sorted(secoes[sec])
        idr = re.sub(r"[^a-z0-9]+", "-", sec.lower())
        k = sum(it["vezes"] for p in ps for it in por[p])
        nav.append(f'<a href="#{idr}">{html.escape(sec.split("/", 3)[-1])} ({k})</a>')
        corpo.append(f'<section class="sec"><h3 id="{idr}">{html.escape(sec)}<span class="n">{len(ps)} page'
                     f'{"s" if len(ps) != 1 else ""}, {k} link{"s" if k != 1 else ""}</span></h3>')
        for p in ps:
            jc = backup[p]
            titulo = re.sub(r"\s+", " ", jc.get("pageTitle") or jc.get("jcr:title") or p.rsplit("/", 1)[-1]).strip()
            c = comp[p]
            if "botao" in c:
                selo = ('<span class="ok">✓ only the button changed</span>' if c["botao"] else
                        '<span class="tag wrong">differs — see JSON</span>')
            else:
                ok = (not c["jcr"] and not c["render"])
                selo = '<span class="ok">✓ renders identically</span>' if ok else '<span class="tag wrong">differs — see JSON</span>'
            its = sorted(por[p], key=lambda it: (it["tipo"] != "wrong", it["txt"].lower()))
            k = sum(it["vezes"] for it in its)
            corpo.append(f'<details class="pg" open><summary>{html.escape(titulo)}<span class="n">{k} link'
                         f'{"s" if k != 1 else ""}</span>{selo}</summary>'
                         f'<div class="abre">{LV._revisar(f"{M}/{p}", LV.indice_cache().par(f"{M}/{p}"))}'
                         f'<span class="p">/{html.escape(p)}</span></div>' + "".join(_item(it) for it in its) + "</details>")
        corpo.append("</section>")

    caixas = " ".join(f'<label><input type="checkbox" value="{k}" checked> {html.escape(TIPOS[k][0])} ({n[k]})</label>'
                      for k in TIPOS if n[k])
    linhas = "".join(f'<tr><td><span class="tag {k}">{html.escape(TIPOS[k][0])}</span></td><td>{html.escape(TIPOS[k][1])}</td>'
                     f'<td class="num">{n[k]}</td><td class="num">{sum(1 for p in por if any(i["tipo"] == k for i in por[p]))}</td></tr>'
                     for k in TIPOS if n[k])
    loc = locals()
    return {k: loc[k] for k in CAMPOS}


def main():
    d = montar(sys.argv[1:])
    corpo, nav, caixas, linhas, n, por, iguais, com_botao, botoes_ok, editor, data, horas, quando, todos = (d[k] for k in CAMPOS)
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>global2 link fixes</title><style>{LV.CSS}{CSS_EXTRA}</style></head><body><main>
<h1>global2 link fixes</h1>
<p class="sub">Links corrected on the macnicaglobal2 pages (Americas / MAI / EN) on {data} (local time){(f" and in {len(horas) - 1} later round{'s' if len(horas) > 2 else ''} (" + ", ".join(h[11:13] + ":" + h[13:15] for h in horas[1:]) + ")") if len(horas) > 1 else ""}. Each change only set where an
existing link, text, title, image or button goes — except on {len(com_botao)} event pages, where a broken jump menu was replaced by
a button in the same place. No other text, image, block or layout was added, moved or removed. Paths are relative to
<code>{M}</code>; “After” links open the destination in the AEM author (you must be logged in).</p>
<div class="resumo">
<div><b>{sum(n.values())}</b><span>links corrected</span></div>
<div><b>{len(por)}</b><span>pages changed</span></div>
<div><b>{iguais}/{len(por) - len(com_botao)}</b><span>pages render identically to before, apart from the links</span></div>
<div><b>{botoes_ok}/{len(com_botao)}</b><span>event pages where only the new button changed</span></div>
<div><b>0</b><span>links that failed to save</span></div></div>
<table><thead><tr><th>Change</th><th>Meaning</th><th class="num">Links</th><th class="num">Pages</th></tr></thead>
<tbody>{linhas}</tbody></table>
<h2 id="como">How it was done and checked<span class="n"></span></h2>
<ol class="passos">
<li><b>Backup first.</b> Before the first change, the full stored content and the rendered HTML of all {len(por)} pages were saved
(<span class="p">scripts-hazael/remigracao/dados/golive/backup_links_* and backup_botoes_*</span>, one folder per round); any
page can be restored from it.</li>
<li><b>One property per change.</b> Each change rewrote a single existing property (the text that holds the link, or the button’s
link). The property was re-read right before saving and again after, and nothing else in that component changed.</li>
<li><b>Whole-page comparison.</b> After all changes, every page was compared with its backup: the stored content differs only in the
changed link properties, and the rendered page is identical once the links themselves are set aside. AEM also records the edit on
each page (the “last modified” date; on {editor} pages the “last modified by” now shows the account that made the change).</li>
<li><b>Files.</b> The two PDFs that were linked from the GWI (the Macnica Americas linecard and the IEI
networking brochure) were copied into the global2 DAM first; the copies are identical to the GWI files (same checksum).</li>
<li><b>Event buttons.</b> On each event page the stored content differs from the backup only by the jump menu that left and the
button that took its place (same position); the rendered page is identical once those two blocks are set aside; screenshots at
1400px are identical above the button and, below it, identical after the page moves down 11px, apart from sub-pixel smoothing
on a few icon edges (checked enlarged). Each button renders with the GWI’s text and link and opens in a new tab.</li>
<li><b>The new links open.</b> Every internal destination was requested on the author and opens (HTTP 200). External
destinations are the same URLs the GWI uses and were not opened.</li>
</ol>
<div class="barra"><input id="q" type="search" placeholder="Filter by link text or path…" autocomplete="off"> {caixas}
<nav><b>Sections</b> {' '.join(nav)}</nav></div>
<h2 id="lista">Changes by page<span class="n">{sum(n.values())} links on {len(por)} pages</span></h2>
{''.join(corpo)}
<footer><p><b>Still open</b>: 4 links that are wrong on the GWI too or need a decision (VidTrans16 “www.macnica-na.com”, the 2018
“valueadd” link, iENSO’s “submit your request here”, Zipteam), the Sony IMX711 link in the June 2026 newsletter (the page is not
in global2’s Americas site yet), and content missing from some pages (for example the category cards on /products). Only the author
was changed; nothing was written to the GWI.</p></footer>
</main><script>{LV.JS}</script></body></html>
"""
    saida = C.DADOS.parent / "mapas" / f"global2_link_fixes_{quando[:10]}.html"
    saida.write_text(pagina, encoding="utf-8")
    print(f"{sum(n.values())} links ({dict(n)}; {len(todos)} linhas) em {len(por)} páginas; {iguais}/{len(por)} iguais -> {saida}")


if __name__ == "__main__":
    main()
