#!/usr/bin/env python3
"""
relatorio_final.py COLETA_FINAL.json — relatório final (em inglês, para mandar) de TUDO o que foi feito no global2 em
24–25/09/2026: a conferência final de todas as páginas, o conteúdo acrescentado/corrigido (com recortes antes/depois), os
links consertados (antes -> depois de cada um) e o que continua pendente (decisões, achados da varredura, conferidos sem ação).

Junta as peças dos outros relatórios — relatorio_conteudo.secoes(), relatorio_consertos.montar(),
pendencias_links.classificar_coleta() — com dados/golive/verificacao_final_<data>.json e varredura_pendencias_<data>.json.
Leitura só (a importação do conteudo_faltando faz GETs no author para montar a lista); nada gravado.

Pedido do Hazael (25/09/2026): "generate a report with all changes, before, after, what was done, and if you find other
pending pages, add them to the report".

    python3 relatorio_final.py ../../dados/mapas/global2_links_vs_gwi_2026-09-25_final.json
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links_vs_gwi as LV  # noqa: E402
import pendencias_links as PL  # noqa: E402
import relatorio_consertos as RC  # noqa: E402
import relatorio_conteudo as RT  # noqa: E402

M = RT.M
DADOS = RT.CF.DADOS
GRUPO = {"A": "links", "B": "links", "D": "links", "E": "links", "F": "links", "C-botao": "event button", "G": "content"}
SUGESTAO = {  # decisões em aberto: o que eu sugeri ao Hazael (25/09) — ele não decidiu ainda
    "about-us/news-events/news-archive/2016-02-16-macnica-demonstrates-video-transport-over-ip-interoperability-at":
        "Keep global2 as it is (the GWI link is clearly wrong: “macnica-na.com” is the Americas site).",
    "about-us/news-events/news-archive/2018-02-13-macnica-americas-expands-value-added-services-for-displays":
        "Keep global2 as it is (the GWI's destination does not exist; the Displays page is the closest live page).",
}
NOVOS = []  # achados da varredura final (varredura_pendencias.py + conferência à mão) ainda NÃO mexidos
RESOLVIDOS = [   # achados da varredura final de 25/09 já resolvidos: (página, o quê, detalhe, como)
    ("products/boards-modules/tq-systems", "Images served from the GWI",
     "The four tab images (Embedded Modules, Evaluation Kits, Single Board Computers, Box PCs) pointed to the GWI's DAM "
     "(/content/dam/macnicagwi/…/images/products/). They showed only because the GWI is still live.",
     "Fixed on 25/09 — see “Content added or corrected”. Every tab is pixel-identical to before."),
    ("about-us/news-events/news-archive/ienso-to-showcase-generative-ai-at-the-edge-ces2025", "Content missing",
     "The body of the press release was missing: global2 only had the “Request a Demo” invitation and “About iENSO” "
     "(1,101 characters of text against 3,987 on the GWI).",
     "Fixed on 25/09 — see “Content added or corrected”."),
    ("products/boards-modules/terasic/terasic-apollo-agilex-som", "Empty image (cleanup)",
     "In the “Layout” block there was an empty image component between the two layout images. It showed nothing on the "
     "page (the GWI has the same two images), so nothing was missing.",
     "Fixed by hand by Hazael on 25/09 (checked: the empty image is gone; the block has its title and the two layout images)."),
]
JS = LV.JS.replace("document.querySelectorAll('.lk')", "document.querySelectorAll('#links .lk')") \
          .replace("document.querySelectorAll('details.pg')", "document.querySelectorAll('#links details.pg')") \
          .replace("document.querySelectorAll('section.sec')", "document.querySelectorAll('#links section.sec')")
assert JS.count("#links") == 3, "o JS do filtro mudou: conferir os seletores"


def curto(u):
    """Caminho sem o prefixo fixo do site: /content/macnicaglobal2/americas/mai/en.html -> /americas/mai/en.html."""
    return re.sub(r"^/content/macnica(?:global2|gwi)", "", u or "")


def titulo_de(b, pag):
    jc = (b["jcr"].get(f"{M}/{pag}") if pag else b["jcr"].get(M)) or {}
    return re.sub(r"\s+", " ", jc.get("pageTitle") or jc.get("jcr:title") or pag.rsplit("/", 1)[-1] or "Home").strip()


def celula(b, idx, pag):
    """Célula da página: título, caminho e os 3 links para revisar à mão (global2, o par no GWI, editor)."""
    g2 = f"{M}/{pag}" if pag else M
    return (f'<span class="t">{html.escape(titulo_de(b, pag))}</span><div class="p">/{html.escape(pag)}</div>'
            f'<div class="abre">{LV._revisar(g2, idx.par(g2))}</div>')


def main():
    col = Path(sys.argv[1])
    rel, b, idx, por, fora = PL.classificar_coleta(col)
    ver = json.loads(sorted(DADOS.glob("verificacao_final_*.json"))[-1].read_text(encoding="utf-8"))
    varr = json.loads(sorted(DADOS.glob("varredura_pendencias_*.json"))[-1].read_text(encoding="utf-8"))
    ct = RT.secoes(json.loads(col.read_text(encoding="utf-8")))
    lk = RC.montar()

    # ---- 1. conferência final
    sim, nao, nd = '<span class="y">✓</span>', '<span class="x">✗</span>', '<span class="na">–</span>'
    linhas_v, n_ok = [], 0
    for pag, r in sorted(ver["paginas"].items(), key=lambda kv: (not kv[1]["ok"], kv[0])):
        n_ok += r["ok"]
        grupos = sorted({GRUPO.get(g, g) for g in r["grupos"]})
        tela = r.get("tela")
        prob = "; ".join(r["no_lugar"] + [f"changed outside the fix: {x}" for x in r["fora_do_declarado"]]
                         + [f"link not in page: {x}" for x in r["links_fora_do_html"]] + r["alvos_mortos"])
        linhas_v.append(
            f'<tr><td>{celula(b, idx, pag)}'
            + (f'<div class="nota">{html.escape(prob)}</div>' if prob else "") + f'</td><td>{", ".join(grupos)}</td>'
            f'<td class="c">{nao if r["no_lugar"] else sim}</td><td class="c">{nao if r["fora_do_declarado"] else sim}</td>'
            f'<td class="c">{nao if r["editada_depois"] else sim}</td>'
            f'<td class="c">{nao if (r["links_fora_do_html"] or r["alvos_mortos"]) else sim}</td>'
            f'<td class="c">{nd if not tela else (sim if tela["igual"] and not tela["imagens_quebradas"] else nao)}</td></tr>')
    n_assets_ok = sum(a["ok"] for a in ver["assets"])
    q = ver["quando"]
    quando_ver = f"{q[8:10]}/{q[5:7]} {q[11:13]}:{q[13:15]}"

    # ---- 4. pendências
    dec = []
    for pag, its in sorted(por.get("decide", {}).items()):
        for it in its:
            dec.append(f'<tr><td>{celula(b, idx, pag)}</td>'
                       f'<td>“{html.escape(it["txt"][:70])}”<div class="p">global2 now: {html.escape(curto(it["agora"]) or "(not a link)")}'
                       f'<br>GWI: {html.escape(curto(it["gwi"] or ""))}</div></td>'
                       f'<td>{html.escape(it.get("nota", ""))}</td><td>{html.escape(SUGESTAO.get(pag, ""))}</td></tr>')
    outros = [c for c in PL.CATS if c not in ("decide", "fora") and por.get(c)]
    novos = "".join(f'<tr><td>{celula(b, idx, p)}</td>'
                    f'<td><span class="tag">{html.escape(t)}</span></td><td>{html.escape(d)}</td><td>{html.escape(como)}</td></tr>'
                    for p, t, d, como in [(p, t, d, "Not changed.") for p, t, d in NOVOS] + RESOLVIDOS)
    listas = "".join(f'<tr><td>{celula(b, idx, p)}</td>'
                     f'<td>{html.escape(re.sub(r"^[^:]*: ", "", d))}</td></tr>' for p, d in varr["achados"].get("lista_deletadas", []))
    fora_html = "".join(f"<li>/{html.escape(p)} — “{html.escape(it['txt'][:70])}”: {html.escape(it['nota'])}"
                        f'<div class="abre">{LV._revisar(f"{M}/{p}", idx.par(f"{M}/{p}"))}</div></li>'
                        for p, it in sorted(fora, key=lambda x: x[0]))
    achados = [a for a in RT.ACHADOS if not a[0].startswith("Soft-deleted")]
    n_pend = len({p for p in por.get("decide", {})} | {p for p, _, _ in NOVOS}
                 | {p for p, _ in varr["achados"].get("lista_deletadas", [])})

    css = LV.CSS + RC.CSS_EXTRA + RT.CSS + """
.y{color:var(--ok);font-weight:700}.x{color:var(--bad);font-weight:700}.na{color:var(--mut)}
td.c{text-align:center;white-space:nowrap}.t{font-weight:600}td .abre,.fora .abre{margin:3px 0 0;line-height:1.7}.abre a{white-space:nowrap}.tabv td{vertical-align:top}.tabv td:first-child{min-width:220px}
.tabela{overflow-x:auto;margin:0 0 12px}.tabela table{min-width:640px}
nav.toc{margin:4px 0 18px;display:flex;flex-wrap:wrap;gap:4px 16px}nav.toc a{white-space:nowrap}
h2{scroll-margin-top:12px}#links h2,#links h3{scroll-margin-top:160px}
"""
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>global2 fixes report</title><style>{css}</style></head><body><main>
<h1>global2 fixes — final report</h1>
<p class="sub">Everything changed on the macnicaglobal2 pages of the link map (Americas / MAI / EN) on 24–25/09/2026, the final
verification of all of it, and what is still pending. Only the AEM author was changed: nothing was published and nothing was
written to the GWI (the old site), which was only read. Every change followed the same steps: back up the whole page (stored
content, rendered HTML, and for layout changes a 1400px screenshot), make the change, then compare the whole page with the backup.
Every page listed has three links for reviewing it by hand: <b>global2 page</b> (as visitors see it), <b>GWI page</b> (the
same page on the old site — open the two side by side) and <b>global2 editor</b>. Links open in the AEM author; you must be
logged in.</p>
<div class="resumo">
<div><b>{len(ver["paginas"])}</b><span>pages changed</span></div>
<div><b>{sum(lk["n"].values())}</b><span>links corrected on {len(lk["por"])} pages (24/09)</span></div>
<div><b>{len(ct["ordem"])}</b><span>pages with content added or corrected (24–25/09)</span></div>
<div><b>{ct["n_assets"] + 2}</b><span>files copied from the GWI into the global2 DAM</span></div>
<div><b>{n_ok}/{len(ver["paginas"])}</b><span>pages pass every check of the final verification ({quando_ver})</span></div>
<div><b>{n_pend}</b><span>pages still need something (see “Still pending”)</span></div></div>
<nav class="toc"><a href="#verificacao">1. Final verification</a><a href="#conteudo">2. Content added or corrected</a>
<a href="#links">3. Links corrected</a><a href="#pendente">4. Still pending</a><a href="#achados">5. Found, not changed</a></nav>

<h2 id="verificacao">1. Final verification<span class="n">{quando_ver}, {n_ok} of {len(ver["paginas"])} pages OK</span></h2>
<p class="intro">Every page changed on 24–25/09 was checked again at the end, against the backups. This table is also the
review list: all {len(ver["paginas"])} pages, each with its global2, GWI and editor links.</p>
<ul class="passos">
<li><b>In place</b> — each recorded change is still there (link, button, text, table, image, component added/removed/moved).</li>
<li><b>Nothing else changed</b> — the page's stored content now differs from the backup taken before its first change of the day
only in the components that were changed (and AEM's “last modified” stamp).</li>
<li><b>Not edited since</b> — nobody edited the page after the last change.</li>
<li><b>Links</b> — the new links are in the rendered page and every internal destination and file opens (HTTP 200); in-page
anchors have their target. External destinations are the GWI's own and were not opened.</li>
<li><b>Screen</b> — for pages whose layout changed (content and event buttons): a new 1400px screenshot is identical to the one
taken right after the change, and every image loads. “–” = no layout change on that page.</li>
<li><b>Files</b> — {n_assets_ok} of {len(ver["assets"])} files copied from the GWI are identical to the originals (same checksum)
and processed by the DAM.</li></ul>
<div class="tabela"><table class="tabv"><thead><tr><th>Page</th><th>Changed</th><th>In place</th><th>Nothing else changed</th>
<th>Not edited since</th><th>Links</th><th>Screen</th></tr></thead><tbody>{"".join(linhas_v)}</tbody></table></div>

<h2 id="conteudo">2. Content added or corrected<span class="n">{len(ct["ordem"])} pages</span></h2>
<p class="intro">What the GWI shows and the global2 page did not have (or had wrong), what was done, and before/after screenshots
of the changed area. Grids follow the Suppliers/Partners grid of the Imaging &amp; Vision page.</p>
<div class="tabela"><table><thead><tr><th>Page</th><th>What was wrong</th></tr></thead><tbody>{"".join(ct["linhas"])}</tbody></table></div>
{"".join(ct["corpo"])}

<section id="links">
<h2>3. Links corrected<span class="n">{sum(lk["n"].values())} links on {len(lk["por"])} pages</span></h2>
<p class="intro">Each change set where an existing link, text, title, image or button goes (before → after), except on
{len(lk["com_botao"])} event pages, where a broken jump menu was replaced by a button in the same place.</p>
<div class="barra"><input id="q" type="search" placeholder="Filter the links by text or path…" autocomplete="off"> {lk["caixas"]}
<nav><b>Sections</b> {" ".join(lk["nav"])}</nav></div>
{"".join(lk["corpo"])}
</section>

<h2 id="pendente">4. Still pending</h2>
<h3>4.1 Needs a decision<span class="n">{len(dec)} links</span></h3>
<p class="intro">The GWI link is wrong, dead or points to a test page; copying it would copy the error.</p>
<div class="tabela"><table class="tabv"><thead><tr><th>Page</th><th>Link</th><th>Situation</th><th>Suggestion</th></tr></thead>
<tbody>{"".join(dec)}</tbody></table></div>
{"" if not outros else "<p><b>Other link problems:</b> " + ", ".join(f"{html.escape(PL.CATS[c][0])} ({sum(len(v) for v in por[c].values())})" for c in outros) + "</p>"}
<h3>4.2 Found in the final check<span class="n">{len(NOVOS) + len(RESOLVIDOS)} pages, {len(NOVOS)} still open</span></h3>
<p class="intro">Not visible to the link comparison; found by a sweep of all {len(rel["paginas"])} map pages (images, empty
components, lists, tabs, amount of text against the GWI) and checked by hand.{" All of them have since been fixed." if not NOVOS else ""}</p>
<div class="tabela"><table class="tabv"><thead><tr><th>Page</th><th>What</th><th>Detail</th><th>Status</th></tr></thead><tbody>{novos}</tbody></table></div>
<h3>4.3 Product lists that show soft-deleted pages<span class="n">{len(varr["achados"].get("lista_deletadas", []))} pages</span></h3>
<p class="intro">A product list shows every child page, including pages that were soft-deleted (hidden in the console, still in
the repository) — they appear as duplicates on the author. None of them has been published. Fix: delete the soft-deleted pages
for good (they are duplicates with upper-case names), or make sure they are never published.</p>
<div class="tabela"><table><thead><tr><th>Page</th><th>Soft-deleted pages in its list</th></tr></thead><tbody>{listas}</tbody></table></div>
<h3>4.4 Checked, no action needed<span class="n">{len(fora)}</span></h3>
<p class="intro">Differences from the GWI that are right as they are (or were decided to stay).</p>
<ul class="fora">{fora_html}</ul>

<h2 id="achados">5. Found, not changed</h2>
<ul class="achado">{"".join(f"<li><b>{html.escape(t)}.</b> {html.escape(d)}</li>" for t, d in achados)}</ul>
<footer><p>Paths are relative to <code>{M}</code>. Comparison with the GWI: {html.escape(rel["quando"])} (all {len(rel["paginas"])}
pages of the link map). Tools: corrigir_links.py, botao_evento.py, copiar_asset_gwi.py, conteudo_faltando.py,
verificacao_final.py, varredura_pendencias.py; backups in dados/golive/backup_links_*, backup_botoes_*, backup_conteudo_*.</p></footer>
</main><script>{JS}</script></body></html>
"""
    saida = LV.MAPAS / f"global2_fixes_final_report_{rel['quando'][:10]}.html"
    saida.write_text(pagina, encoding="utf-8")
    print(f"{len(ver['paginas'])} páginas ({n_ok} OK), {sum(lk['n'].values())} links, {len(ct['ordem'])} de conteúdo, "
          f"{len(dec)} decisões, {len(NOVOS)} novos -> {saida} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
