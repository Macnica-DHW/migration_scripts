#!/usr/bin/env python3
"""
relatorio_conteudo.py [COLETA_POS.json] — relatório HTML (em inglês, para mandar) do que o conteudo_faltando.py GRAVOU:
por página, o que estava errado/faltando, o que mudou, os arquivos copiados para o DAM, a conferência contra o backup e
recortes antes/depois do print; no fim, o que foi achado e NÃO mexido.

Lê os backups (dados/golive/backup_conteudo_*/: comparacao.json + prints) e os textos em inglês de conteudo_faltando.PAGINAS
(a importação faz GETs de leitura no author para montar a lista; nada é gravado). COLETA_POS = a coleta do links_vs_gwi
feita DEPOIS dos consertos, para dizer o que sobrou.

Pedido do Hazael (25/09/2026): "Also document those findings and what's being changed so that I can report it later".

    python3 relatorio_conteudo.py ../../dados/mapas/global2_links_vs_gwi_2026-09-25_pos3.json
"""
import base64
import html
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conteudo_faltando as CF  # noqa: E402
import links_vs_gwi as LV  # noqa: E402

M = CF.M
BACKUPS = sorted(CF.DADOS.glob("backup_conteudo_*"))
# recortes além do automático (topo da mudança): (tipo, y0, y1) em px do print de 1400; "depois" = só o print novo
JANELAS = {
    "products/boards-modules/tq-systems/tq-embedded-x86-modules": [("depois", 3300, 3900, "End of the product list and the contact buttons (items 47–54 include the 4 soft-deleted duplicates)")],
    "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing": [
        ("depois", 11880, 12700, "Surgical Monitors section (new)"),
        ("depois", 14780, 15500, "Second Ordering Information table, now the surgical monitors' one")],
    "products/boards-modules/ibase/embedded-computing/mb991": [("ambos", 2750, 3400, "Bottom of the page: the newsletter block replaces the two buttons")],
}
CURTO = {   # coluna "What was wrong" da tabela do topo
    "products": "The four category cards were blank; the banner was missing",
    "products/boards-modules/tq-systems/tq-embedded-x86-modules": "Wrong heading and product list (an unfinished copy of the Layerscape page); contact buttons missing",
    "products/boards-modules/tq-systems/tq-embedded-arm-modules": "Wrong heading (“TQ Embedded QorIQ® Layerscape”) — not on the pending list",
    "products/boards-modules/transcend": "“View Transcend's Memory Product Portfolio” button missing",
    "products/boards-modules/connect-tech": "“NVIDIA Jetson AGX Xavier” section missing",
    "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing": "“Fitness Panel PC” and “Surgical Monitors” sections missing; one ordering table was a duplicate",
    "products/boards-modules/ibase/embedded-computing/mb991": "Introduction, image and features of a different board (MI997); newsletter block missing",
    "products/boards-modules/tq-systems/tq-embedded-arm-modules/mba8mp-ras314-single-board-computer": "Whitepaper paragraph missing (PDF not in global2)",
    "solutions/robotics-amrs": "“Download … Robotics Solutions Brief” button missing (PDF not in global2)",
    "solutions/broadcast-proav-solutions/st-2110-at-scale-resources": "Second contact block (with “Request Evaluation Kit”) missing",
    "about-us/privacy-policy/privacy-policy-for-california-residents": "www.zipteam.com not linked (the domain is inside a heading)",
    "products/boards-modules": "Supplier grid (11 logos) missing; “Request a Quote” missing; contact button pointed to a hard-coded domain",
}
NOTAS = {   # conferência extra, feita à parte
    "solutions/robotics-amrs": "Compared with the page before any change: the only difference is the new download button (plus the "
                               "page's last-modified stamp); the Contact Us button is identical and in its original place.",
}
ACHADOS = [  # encontrado e NÃO mexido
    ("Soft-deleted pages show up in product lists",
     "The product list of a TQ family page lists every child page, including pages that were soft-deleted (hidden in the "
     "console, still in the repository). They appear as duplicates on the author: x86 modules 4 (items 47–54), ARM modules "
     "18, QorIQ Layerscape 3, Power modules 4. None of them has been published. Fix: delete those soft-deleted pages for good "
     "(they are duplicates with upper-case names), or make sure they are never published."),
    ("Embedded contact/newsletter blocks carry a second HTML document",
     "The two shared blocks (“Products-Contact block” and “SignUp and Contact”) are experience fragments of the ‘page’ type, "
     "so every page that embeds them gets the fragment's whole document inside its body, including a second canonical link "
     "(to the fragment). Nothing changes on screen. It was already the case on the ~66 pages that use these blocks; "
     "Boards & Modules and MB991 now use them too. The fix is on the two fragments (open decision)."),
    ("The download button's icon overlaps its last letter",
     "A button that points to a file gets the site's download design (smaller text, download icon); the icon is drawn over "
     "the end of the label (“Brie[f]”). The same happens on the Company Profile download buttons. Site CSS, not content."),
    ("Last editor changed on pages edited by Bruno",
     "Every save stamps the page with the account of the session used (Valter Toffolo): MB991 and MBa8MP-RAS314 were last "
     "edited by Bruno Jaques before these changes."),
]


def img64(im, largura=700):
    from PIL import Image
    if im.width > largura:
        im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def recorte(png, y0, y1):
    from PIL import Image
    im = Image.open(png)
    y0, y1 = max(0, y0), min(im.height, y1)
    return im.crop((0, y0, min(im.width, 1400), y1)) if y1 > y0 else None


def passadas():
    """{pagina: [(pasta, item da comparacao)]} em ordem de execução."""
    out = {}
    for b in BACKUPS:
        f = b / "comparacao.json"
        if f.exists():
            for c in json.loads(f.read_text(encoding="utf-8")):
                out.setdefault(c["pagina"], []).append((b, c))
    return out


def entradas_de(pag):
    return [(ch, cfg) for ch, cfg in CF.PAGINAS.items() if cfg.get("pagina", ch) == pag]


def figura(titulo, antes, depois):
    cel = lambda rot, im: (f'<figure><figcaption>{rot}</figcaption><img src="{img64(im)}" alt="{rot}: {html.escape(titulo)}" '
                           f'loading="lazy"></figure>' if im is not None else "")
    return (f'<div class="fig"><p class="ft">{html.escape(titulo)}</p><div class="par">{cel("Before", antes)}'
            f'{cel("After", depois)}</div></div>')


def secoes(pos=None):
    """Peças do relatório: seções por página (com recortes), linhas da tabela do topo, nº de arquivos, páginas e o parágrafo
    do que sobrou na coleta `pos` — também usadas pelo relatorio_final.py."""
    ps = passadas()
    b = LV.CACHE.exists() and __import__("pickle").loads(LV.CACHE.read_bytes())
    corpo, linhas, n_assets = [], [], 0
    ordem = [p for p in dict.fromkeys(cfg.get("pagina", ch) for ch, cfg in CF.PAGINAS.items()) if p in ps]
    for pag in ordem:
        ents = entradas_de(pag)
        principal = ents[0][1]
        pas = ps[pag]
        arq = pag.replace("/", "__") or "raiz"
        (b0, c0), (bn, cn) = pas[0], pas[-1]
        titulo = re.sub(r"\s+", " ", ((b and b["jcr"].get(f"{M}/{pag}")) or {}).get("pageTitle")
                        or ((b and b["jcr"].get(f"{M}/{pag}")) or {}).get("jcr:title") or pag.rsplit("/", 1)[-1])
        assets = [d for _, cfg in ents for _, d in cfg.get("assets", [])]
        n_assets += len(assets)
        # conferência de todas as passadas
        conf = []
        for n, (bk, c) in enumerate(pas, 1):
            rr, pr = c["render"], c["prints"]
            desl = pr["altura"][1] - pr["altura"][0]
            itens = [f"Content: {'only the planned components changed' if not c['jcr_fora'] else 'UNEXPECTED: ' + ', '.join(c['jcr_fora'])}"
                     " (plus the page's last-modified stamp)."]
            if rr["links_entrou"] or rr["links_saiu"]:
                ent = [u for u in rr["links_entrou"] if not re.search(r"/icons/|/experience-fragments/", u)]
                itens.append("Links added: " + (", ".join(f"<code>{html.escape(u.replace(M, '…'))}</code>" for u in ent) or "none")
                             + (("; removed: " + ", ".join(f"<code>{html.escape(u)}</code>" for u in rr["links_saiu"])) if rr["links_saiu"] else ""))
            itens.append(f"Screenshot (1400px): identical above the change (first {pr['igual_no_topo_ate']} px); "
                         f"the page is {abs(desl)} px {'longer' if desl >= 0 else 'shorter'}.")
            d_, h_ = bk.name.replace("backup_conteudo_", "").split("_")
            conf.append(f"<li><b>{'Pass ' + str(n) + ' · ' if len(pas) > 1 else ''}{d_[8:10]}/{d_[5:7]} {h_[:2]}:{h_[2:4]}</b><ul>"
                        + "".join(f"<li>{i}</li>" for i in itens) + "</ul></li>")
        if pag in NOTAS:
            conf.append(f"<li><b>Net result</b><ul><li>{html.escape(NOTAS[pag])}</li></ul></li>")
        # recortes
        figs = []
        t = c0["prints"]["igual_no_topo_ate"]
        a_png, d_png = b0 / "prints_antes" / f"{arq}.png", bn / "prints_depois" / f"{arq}.png"
        if a_png.exists() and d_png.exists():
            figs.append(figura("Where the change starts", recorte(a_png, t - 150, t + 650), recorte(d_png, t - 150, t + 950)))
            for tipo, y0, y1, rot in JANELAS.get(pag, []):
                figs.append(figura(rot, recorte(a_png, y0, y1) if tipo == "ambos" else None, recorte(d_png, y0, y1)))
        w = principal.get("gwi")
        mud = "".join(f"<p>{html.escape(cfg['mudanca'])}</p>" for _, cfg in ents if cfg.get("mudanca"))
        corpo.append(
            f'<details class="pg" open id="{html.escape(arq)}"><summary>{html.escape(titulo)}'
            f'<span class="n">{len(pas)} pass{"es" if len(pas) > 1 else ""}</span></summary>'
            f'<div class="abre">{LV._alink(f"{M}/{pag}.html?wcmmode=disabled", "global2 page")}'
            + (LV._alink(f"{w}.html?wcmmode=disabled", "GWI page") if w else "")
            + f'<span class="p">/{html.escape(pag)}</span></div>'
            f'<h4>What was wrong</h4><p>{html.escape(principal.get("achado", ""))}</p>'
            f'<h4>What was changed</h4>{mud}'
            + (f'<h4>Files copied from the GWI into the global2 DAM</h4><ul>' + "".join(
                f"<li><code>{html.escape(d.replace(CF.G2_DAM, '…'))}</code></li>" for d in assets) + "</ul>" if assets else "")
            + f'<h4>How it was checked</h4><ul class="conf">{"".join(conf)}</ul>{"".join(figs)}</details>')
        linhas.append(f'<tr><td><a href="#{html.escape(arq)}">{html.escape(titulo)}</a></td>'
                      f'<td>{html.escape(CURTO.get(pag, principal.get("achado", "")))}</td></tr>')

    sobra = ""
    if pos:
        rel = [r for r in pos["paginas"] if r["g2"][len(M) + 1:] in ordem]
        falt = sum(len(r["faltando"]) for r in rel)
        sobra = (f"<p>A fresh comparison of the {len(pos['paginas'])} map pages with their GWI pages after these changes "
                 f"({html.escape(pos['quando'])}) finds <b>{falt}</b> GWI link{'s' if falt != 1 else ''} still missing on "
                 f"these pages" + (": " + "; ".join(f"/{html.escape(r['g2'][len(M) + 1:])} “{html.escape(x['txt'][:60])}”"
                                                    for r in rel for x in r["faltando"]) if falt else "") + ".</p>")
    return {"corpo": corpo, "linhas": linhas, "n_assets": n_assets, "ordem": ordem, "sobra": sobra}


CSS = """
h4{font-size:14px;margin:14px 0 4px;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
details.pg p{margin:4px 0 8px;overflow-wrap:anywhere}.achado li,.conf li{overflow-wrap:anywhere}.conf{margin:4px 0 10px;padding-left:20px;font-size:14px}.conf ul{padding-left:18px}
code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.fig{margin:12px 0 16px}.ft{font-weight:600;font-size:14px;margin:0 0 6px}
.par{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}
figure{margin:0}figcaption{font-size:12px;color:var(--mut);margin:0 0 3px}
figure img{width:100%;height:auto;border:1px solid var(--lin);border-radius:4px;display:block}
.achado li{margin:0 0 10px}
"""


def main():
    pos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else None
    d = secoes(pos)
    corpo, linhas, n_assets, ordem, sobra = d["corpo"], d["linhas"], d["n_assets"], d["ordem"], d["sobra"]
    css = LV.CSS + CSS
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>global2 content fixes</title><style>{css}</style></head><body><main>
<h1>global2 content fixes</h1>
<p class="sub">Content that the GWI pages show and the global2 pages of the link map (Americas / MAI / EN) did not have —
the “Content missing from the page” items of global2_links_pending_2026-09-25.html — plus wrong content found on the same
pages. Changed on the AEM author on 24–25/09/2026 (nothing was published). Before each change the whole page was backed up
(content, HTML and a 1400px screenshot); after it, the whole page was compared with the backup. Grids follow the
Suppliers/Partners grid of the Imaging &amp; Vision page. Links open in the AEM author; you must be logged in.</p>
<div class="resumo">
<div><b>{len(ordem)}</b><span>pages changed</span></div>
<div><b>{n_assets}</b><span>files copied from the GWI into the global2 DAM</span></div>
<div><b>{len(ACHADOS)}</b><span>issues found and not changed (see the end)</span></div></div>
{sobra}
<table><thead><tr><th>Page</th><th>What was wrong</th></tr></thead><tbody>{''.join(linhas)}</tbody></table>
<h2>Pages</h2>
{''.join(corpo)}
<h2 id="found">Found, not changed</h2>
<ul class="achado">{''.join(f'<li><b>{html.escape(t)}.</b> {html.escape(d)}</li>' for t, d in ACHADOS)}</ul>
<footer><p>Paths are relative to <code>{M}</code>. Tool: conteudo_faltando.py; backups in dados/golive/backup_conteudo_*.</p></footer>
</main></body></html>
"""
    data = (pos or {}).get("quando", "")[:10] or BACKUPS[-1].name.split("_")[2]
    saida = LV.MAPAS / f"global2_content_fixes_{data}.html"
    saida.write_text(pagina, encoding="utf-8")
    print(f"{len(ordem)} páginas, {n_assets} arquivos, {len(ACHADOS)} achados -> {saida} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
